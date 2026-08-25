#!/usr/bin/env python3
"""
FMCSA QCMobile → fmcsaaa.carrierinformation_csv

Safety (client: do not lose existing data):
  - Never TRUNCATE / DELETE other rows
  - Upsert ONLY by DOT_NUMBER
  - ON DUPLICATE KEY UPDATE uses COALESCE so NULL/empty API
    values never wipe existing census columns
  - Columns not returned by API are left untouched

Also maps all QCMobile Quick Start elements + stores full JSON
(carrier + basics) in API_RAW_JSON.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any

import mysql.connector
import requests
from dotenv import load_dotenv

load_dotenv()

FMCSA_BASE = "https://mobile.fmcsa.dot.gov/qc/services/carriers"
ZYTE_URL = "https://api.zyte.com/v1/extract"

# Columns we may write. created_at never touched.
UPSERT_COLS = [
    "ACT_STAT",
    "CARSHIP",
    "DOT_NUMBER",
    "NAME",
    "NAME_DBA",
    "DBNUM",
    "PHY_NATN",
    "PHY_STR",
    "PHY_CITY",
    "PHY_CNTY",
    "PHY_ST",
    "PHY_ZIP",
    "UNDELIV_PHY",
    "TEL_NUM",
    "CELL_NUM",
    "FAX_NUM",
    "MAI_NATN",
    "MAI_STR",
    "MAI_CITY",
    "MAI_CNTY",
    "MAI_ST",
    "MAI_ZIP",
    "UNDELIV_MAI",
    "ICC_DOCKET_1_PREFIX",
    "ICC1",
    "class",
    "classdef",
    "CRRINTER",
    "CRRHMINTRA",
    "CRRINTRA",
    "PASSENGERS",
    "HM_IND",
    "OWNCOACH",
    "OWNBUS_16",
    "OWNVAN_1_8",
    "OWNVAN_9_15",
    "OWNLIMO_1_8",
    "OWNLIMO_9_15",
    "OWNLIMO_16",
    "OWNSCHOOL_1_8",
    "OWNSCHOOL_9_15",
    "OWNSCHOOL_16",
    "TOT_TRUCKS",
    "TOT_BUSES",
    "TOT_PWR",
    "FLEETSIZE",
    "TOT_DRS",
    "CDL_DRS",
    "REVTYPE",
    "REVDATE",
    "ACC_RATE",
    "MLG150",
    "MLG151",
    "RATING",
    "RATEDATE",
    "MCS150MILEAGEYEAR",
    "ADDDATE",
    "MCS_150_DATE",
    "EMAILADDRESS",
    "USDOT_REVOKED_FLAG",
    "USDOT_REVOKED_NUMBER",
    "COMPANY_REP1",
    "COMPANY_REP2",
    "API_RAW_JSON",
]


def env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise SystemExit(f"Missing required env: {name}")
    return v


def s(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "Y" if value else "N"
    text = str(value).strip()
    return text if text else None


def yn(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "Y" if value else "N"
    t = str(value).strip().upper()
    if t in ("Y", "YES", "TRUE", "1"):
        return "Y"
    if t in ("N", "NO", "FALSE", "0"):
        return "N"
    return s(value)


def fetch_json(url: str) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "CDL-Carrier-Verifier/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=45)
        if r.status_code == 200:
            return r.json()
        print(f"Direct FMCSA HTTP {r.status_code}", file=sys.stderr)
        if not os.getenv("ZYTE_API_KEY"):
            r.raise_for_status()
    except requests.RequestException as exc:
        print(f"Direct FMCSA error: {exc}", file=sys.stderr)
        if not os.getenv("ZYTE_API_KEY"):
            raise

    zyte_key = os.getenv("ZYTE_API_KEY", "").strip()
    if not zyte_key:
        raise SystemExit("FMCSA failed and ZYTE_API_KEY not set")

    zr = requests.post(
        ZYTE_URL,
        auth=(zyte_key, ""),
        json={
            "url": url,
            "httpResponseBody": True,
            "customHttpRequestHeaders": [
                {"name": "Accept", "value": "application/json"},
            ],
        },
        timeout=90,
    )
    zr.raise_for_status()
    body = zr.json()
    status = body.get("statusCode")
    raw = base64.b64decode(body["httpResponseBody"])
    if status and int(status) >= 400:
        raise SystemExit(f"Zyte→FMCSA HTTP {status}: {raw[:300]!r}")
    return json.loads(raw)


def extract_carriers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    content = payload.get("content", payload)
    if isinstance(content, list):
        items = content
    elif isinstance(content, dict):
        items = [content]
    else:
        return []

    carriers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        carrier = item.get("carrier", item)
        if isinstance(carrier, dict) and carrier.get("dotNumber") is not None:
            carriers.append(dict(carrier))
    return carriers


def _op_code(c: dict[str, Any]) -> str | None:
    op = c.get("carrierOperation") or {}
    if isinstance(op, dict):
        return s(
            op.get("carrierOperationCode")
            or op.get("code")
            or op.get("carrierOperationDesc")
        )
    return s(op)


def _mc_parts(c: dict[str, Any]) -> tuple[str | None, str | None]:
    """Docs: mcNumber → ICC prefix + number."""
    for key in ("mcNumber", "docketNumber", "mxNumber", "ffNumber", "docket"):
        raw = c.get(key)
        if raw is None:
            continue
        text = str(raw).strip().upper().replace(" ", "")
        if not text:
            continue
        for prefix in ("MC", "MX", "FF"):
            if text.startswith(prefix):
                return prefix, text[len(prefix) :].lstrip("-")
        if text.isdigit():
            return "MC", text
    return None, None


def map_carrier(
    c: dict[str, Any],
    raw_payload: dict[str, Any] | None = None,
    basics: Any = None,
) -> dict[str, str | None]:
    """Map QCMobile docs elements + extras → census columns."""
    prefix, icc1 = _mc_parts(c)

    # Docs vehicle elements
    bus_v = s(c.get("busVehicle") or c.get("schoolBusVehicle"))
    limo_v = s(c.get("limoVehicle"))
    mini_v = s(c.get("miniBusVehicle"))
    coach_v = s(c.get("motorCoachVehicle"))
    van_v = s(c.get("vanVehicle"))
    pass_v = s(c.get("passengerVehicle"))

    tot_drs = s(c.get("totalDrivers") or c.get("driverTotal"))
    tot_pwr = s(c.get("totalPowerUnits") or c.get("powerUnitTotal") or pass_v)
    tot_buses = s(c.get("totalBuses")) or bus_v
    tot_trucks = s(c.get("totalTrucks"))

    mlg = s(c.get("mcs150Mileage") or c.get("mileage"))
    mlg_year = s(c.get("mcs150MileageYear") or c.get("mcs150Year"))

    crash_total = c.get("crashTotal")
    acc_rate = s(crash_total)
    if crash_total is not None:
        parts = [f"total={crash_total}"]
        for k, label in (
            ("fatalCrash", "fatal"),
            ("injCrash", "inj"),
            ("towawayCrash", "tow"),
        ):
            if c.get(k) is not None:
                parts.append(f"{label}={c.get(k)}")
        acc_rate = ";".join(parts)

    # Docs: allowToOperate Y/N; census ACT_STAT often A/I — prefer statusCode
    allow = yn(c.get("allowToOperate") or c.get("allowedToOperate"))
    oos = yn(c.get("outOfService"))
    act = s(c.get("statusCode"))
    if not act:
        if oos == "Y":
            act = "I"
        elif allow:
            act = "A" if allow == "Y" else "I"
        else:
            act = allow

    # Passenger carrier flag if any passenger vehicles
    passengers_flag = None
    for v in (bus_v, limo_v, mini_v, coach_v, van_v, pass_v):
        if v is not None:
            try:
                if float(v) > 0:
                    passengers_flag = "Y"
                    break
            except ValueError:
                passengers_flag = "Y"
                break

    fleet = None
    try:
        if tot_pwr is not None:
            n = int(float(tot_pwr))
            fleet = "1" if n <= 1 else "2-6" if n <= 6 else "7-20" if n <= 20 else "21+"
    except (TypeError, ValueError):
        fleet = tot_pwr

    # complaintCount / oosDate have no census column — kept in API_RAW_JSON
    complaint = s(c.get("complaintCount"))
    oos_date = s(c.get("outOfServiceDate") or c.get("oosDate"))

    row: dict[str, str | None] = {
        "DOT_NUMBER": s(c.get("dotNumber")),
        "NAME": s(c.get("legalName")),
        "NAME_DBA": s(c.get("dbaName")),
        "ACT_STAT": act,
        "CARSHIP": s(c.get("carrierOperationDesc") or _op_code(c)),
        "DBNUM": s(c.get("ein") or c.get("taxId")),
        "PHY_STR": s(c.get("phyStreet") or c.get("phyStreet1")),
        "PHY_CITY": s(c.get("phyCity")),
        "PHY_CNTY": s(c.get("phyCounty") or c.get("phyCnty")),
        "PHY_ST": s(c.get("phyState")),
        "PHY_ZIP": s(c.get("phyZipcode") or c.get("phyZip") or c.get("phyZipCode")),
        "PHY_NATN": s(c.get("phyCountry")),
        "UNDELIV_PHY": yn(c.get("undeliverablePhy")),
        "TEL_NUM": s(c.get("telephone") or c.get("phone")),
        "CELL_NUM": s(c.get("cellPhone") or c.get("mobilePhone")),
        "FAX_NUM": s(c.get("fax") or c.get("faxNumber")),
        "MAI_STR": s(c.get("mailingStreet")),
        "MAI_CITY": s(c.get("mailingCity")),
        "MAI_CNTY": s(c.get("mailingCounty")),
        "MAI_ST": s(c.get("mailingState")),
        "MAI_ZIP": s(c.get("mailingZipcode") or c.get("mailingZip")),
        "MAI_NATN": s(c.get("mailingCountry")),
        "UNDELIV_MAI": yn(c.get("undeliverableMailing")),
        "ICC_DOCKET_1_PREFIX": prefix,
        "ICC1": icc1,
        "class": s(c.get("class") or c.get("carrierClass")),
        "classdef": s(c.get("classDef") or c.get("classdef")),
        "CRRINTER": _op_code(c),
        "CRRHMINTRA": yn(c.get("hmFlag") or c.get("hazmatFlag")),
        "CRRINTRA": yn(c.get("intrastate")),
        "PASSENGERS": passengers_flag,
        "HM_IND": yn(c.get("hmFlag") or c.get("hazmatFlag")),
        "OWNCOACH": coach_v,
        "OWNBUS_16": bus_v,
        "OWNVAN_9_15": van_v or mini_v,
        "OWNVAN_1_8": mini_v if van_v else None,
        "OWNLIMO_16": limo_v,
        "OWNSCHOOL_16": bus_v,
        "TOT_TRUCKS": tot_trucks,
        "TOT_BUSES": tot_buses,
        "TOT_PWR": tot_pwr,
        "FLEETSIZE": fleet,
        "TOT_DRS": tot_drs,
        "CDL_DRS": s(c.get("cdlDrivers")),
        "REVTYPE": s(c.get("reviewType")),
        "REVDATE": s(c.get("reviewDate")),
        "ACC_RATE": acc_rate,
        "MLG150": mlg,
        "MLG151": s(c.get("mcs150Mileage2")),
        "RATING": s(c.get("safetyRating") or c.get("rating")),
        "RATEDATE": s(c.get("safetyRatingDate") or c.get("ratingDate")),
        "MCS150MILEAGEYEAR": mlg_year,
        "ADDDATE": s(c.get("addDate")),
        "MCS_150_DATE": s(c.get("mcs150Date")),
        "EMAILADDRESS": s(c.get("emailAddress") or c.get("email")),
        "USDOT_REVOKED_FLAG": yn(c.get("usdotRevoked") or c.get("dotRevoked")),
        "USDOT_REVOKED_NUMBER": s(c.get("usdotRevokedNumber")),
        "COMPANY_REP1": s(c.get("companyRep1") or c.get("officer1")),
        "COMPANY_REP2": s(c.get("companyRep2")),
    }

    snapshot = {
        "carrier": c,
        "docs_extras": {
            "allowToOperate": allow,
            "outOfService": oos,
            "outOfServiceDate": oos_date,
            "complaintCount": complaint,
            "mcNumber": s(c.get("mcNumber")),
            "busVehicle": bus_v,
            "limoVehicle": limo_v,
            "miniBusVehicle": mini_v,
            "motorCoachVehicle": coach_v,
            "vanVehicle": van_v,
            "passengerVehicle": pass_v,
        },
        "basics": basics,
        "response": raw_payload,
    }
    row["API_RAW_JSON"] = json.dumps(snapshot, ensure_ascii=False, default=str)
    return row


def table_columns(conn, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = {r[0] for r in cur.fetchall()}
    cur.close()
    return cols


def upsert(conn, table: str, row: dict[str, str | None], existing_cols: set[str]) -> None:
    """Insert/update only provided fields; COALESCE keeps old value if new is NULL."""
    cols = [
        c
        for c in UPSERT_COLS
        if c in existing_cols and c in row and row[c] is not None
    ]
    if "DOT_NUMBER" not in cols:
        raise ValueError("DOT_NUMBER required")

    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(f"`{c}`" for c in cols)
    # Preserve existing data: never replace a filled census cell with NULL
    updates = ", ".join(
        f"`{c}`=COALESCE(VALUES(`{c}`), `{c}`)" for c in cols if c != "DOT_NUMBER"
    )
    sql = (
        f"INSERT INTO `{table}` ({col_sql}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    cur = conn.cursor()
    cur.execute(sql, [row[c] for c in cols])
    conn.commit()
    action = (
        "inserted"
        if cur.rowcount == 1
        else "updated"
        if cur.rowcount == 2
        else f"ok({cur.rowcount})"
    )
    print(f"DOT {row['DOT_NUMBER']}: {action} — {row.get('NAME')} [{len(cols)} cols]")
    cur.close()


def mysql_connect():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=env("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "fmcsaaa"),
    )


def fetch_basics(dot: str, webkey: str) -> Any:
    url = f"{FMCSA_BASE}/{dot}/basics?webKey={webkey}"
    try:
        return fetch_json(url)
    except Exception as exc:
        print(f"BASICS skip for {dot}: {exc}", file=sys.stderr)
        return None


def sync_dot(dot: str) -> None:
    webkey = env("FMCSA_WEBKEY")
    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")
    url = f"{FMCSA_BASE}/{dot}?webKey={webkey}"
    payload = fetch_json(url)
    carriers = extract_carriers(payload)
    if not carriers:
        raise SystemExit(f"No carrier in response for DOT {dot}: {json.dumps(payload)[:400]}")

    basics = fetch_basics(dot, webkey)
    conn = mysql_connect()
    try:
        # Safety check: never wipe table
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        before = cur.fetchone()[0]
        cur.close()
        print(f"Rows before sync: {before} (will not truncate)")

        existing = table_columns(conn, table)
        for c in carriers:
            upsert(conn, table, map_carrier(c, payload, basics), existing)

        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        after = cur.fetchone()[0]
        cur.close()
        print(f"Rows after sync: {after}")
        if after < before:
            raise SystemExit("ERROR: row count dropped — abort mindset, check DB")
    finally:
        conn.close()


def sync_name(name: str, limit: int = 20) -> None:
    webkey = env("FMCSA_WEBKEY")
    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")
    url = f"{FMCSA_BASE}/name/{requests.utils.quote(name)}?webKey={webkey}"
    payload = fetch_json(url)
    carriers = extract_carriers(payload)[:limit]
    if not carriers:
        raise SystemExit(f"No carriers for name={name!r}")

    conn = mysql_connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        before = cur.fetchone()[0]
        cur.close()
        print(f"Rows before sync: {before} (will not truncate)")

        existing = table_columns(conn, table)
        for c in carriers:
            dot = str(c.get("dotNumber"))
            basics = fetch_basics(dot, webkey)
            upsert(conn, table, map_carrier(c, payload, basics), existing)

        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        after = cur.fetchone()[0]
        cur.close()
        print(f"Done: {len(carriers)} carrier(s). Rows after: {after}")
        if after < before:
            raise SystemExit("ERROR: row count dropped")
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="FMCSA → MySQL safe upsert")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("dot", nargs="?", help="USDOT number, e.g. 44110")
    g.add_argument("--name", help="Search by carrier name")
    p.add_argument("--limit", type=int, default=20, help="Max rows for --name")
    args = p.parse_args()

    if args.name:
        sync_name(args.name, args.limit)
    else:
        sync_dot(str(args.dot).strip())


if __name__ == "__main__":
    main()
