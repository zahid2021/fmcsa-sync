#!/usr/bin/env python3
"""
Import FMCSA Company Census CSV → fmcsaaa.carrierinformation_csv

Client rules:
  - Never TRUNCATE / DELETE
  - Upsert only by DOT_NUMBER (unique key)
  - Blank CSV cells do not wipe existing values
  - Only columns that exist on the table are written

Source (official bulk — QCMobile API cannot dump all carriers):
  https://data.transportation.gov/Trucking-and-Motorcoaches/Company-Census-File/az4n-8mr2
  CSV: https://data.transportation.gov/api/views/az4n-8mr2/rows.csv?accessType=DOWNLOAD

Usage (VPS):
  python import_census.py --download
  python import_census.py C:\\fmcsa_sync\\census.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import mysql.connector
import requests
from dotenv import load_dotenv

load_dotenv()

CENSUS_CSV_URL = (
    "https://data.transportation.gov/api/views/az4n-8mr2/rows.csv"
    "?accessType=DOWNLOAD"
)

# Skip system / API-only columns
SKIP_COLS = {"created_at", "API_RAW_JSON"}

# Normalize census / MOTUS / legacy header names → DB column names
HEADER_ALIASES: Dict[str, str] = {
    "STATUS_CODE": "ACT_STAT",
    "STATUS": "ACT_STAT",
    "CARRIER_STATUS_CODE": "ACT_STAT",
    "LEGAL_NAME": "NAME",
    "CARRIER_NAME": "NAME",
    "COMPANY_NAME": "NAME",
    "NAME_LEGAL": "NAME",
    "DBA_NAME": "NAME_DBA",
    "DOING_BUSINESS_AS": "NAME_DBA",
    "DOING_BUSINESS_AS_NAME": "NAME_DBA",
    "DUN_BRADSTREET_NO": "DBNUM",
    "DUNS_NUMBER": "DBNUM",
    "PHY_COUNTRY": "PHY_NATN",
    "PHY_NATION": "PHY_NATN",
    "PHY_STREET": "PHY_STR",
    "PHY_ADDRESS": "PHY_STR",
    "PHY_STATE": "PHY_ST",
    "PHY_ZIPCODE": "PHY_ZIP",
    "PHY_ZIP_CODE": "PHY_ZIP",
    "PHY_COUNTY": "PHY_CNTY",
    "MAI_COUNTRY": "MAI_NATN",
    "MAIL_COUNTRY": "MAI_NATN",
    "MAIL_STREET": "MAI_STR",
    "MAIL_CITY": "MAI_CITY",
    "MAIL_STATE": "MAI_ST",
    "MAIL_ZIP": "MAI_ZIP",
    "MAIL_ZIPCODE": "MAI_ZIP",
    "MAIL_COUNTY": "MAI_CNTY",
    "TELEPHONE": "TEL_NUM",
    "PHONE": "TEL_NUM",
    "PHONE_NUMBER": "TEL_NUM",
    "CELL_PHONE": "CELL_NUM",
    "FAX": "FAX_NUM",
    "FAX_NUMBER": "FAX_NUM",
    "EMAIL_ADDRESS": "EMAILADDRESS",
    "EMAIL": "EMAILADDRESS",
    "CARRIER_OPERATION": "CRRINTER",
    "CARRIER_OPERATION_CODE": "CRRINTER",
    "ADD_DATE": "ADDDATE",
    "CHG_DATE": "CHGNDATE",
    "CHANGE_DATE": "CHGNDATE",
    "DEL_DATE": "DELDATE",
    "MCS150_DATE": "MCS_150_DATE",
    "MCS_150_DATE": "MCS_150_DATE",
    "MCS150_MILEAGE": "MLG150",
    "MCS151_MILEAGE": "MLG151",
    "MCS150_MILEAGE_YEAR": "MCS150MILEAGEYEAR",
    "TOTAL_DRIVERS": "TOT_DRS",
    "NBR_DRIVERS": "TOT_DRS",
    "DRIVER_TOTAL": "TOT_DRS",
    "TOTAL_POWER_UNITS": "TOT_PWR",
    "POWER_UNITS": "TOT_PWR",
    "NBR_POWER_UNIT": "TOT_PWR",
    "NBR_POWER_UNITS": "TOT_PWR",
    "TOTAL_TRUCKS": "TOT_TRUCKS",
    "TOTAL_BUSES": "TOT_BUSES",
    "TOTAL_CARS": "TOT_CARS",
    "FLEET_SIZE": "FLEETSIZE",
    "SAFETY_RATING": "RATING",
    "RATING_DATE": "RATEDATE",
    "REVIEW_TYPE": "REVTYPE",
    "REVIEW_DATE": "REVDATE",
    "COMPANY_OFFICER_1": "COMPANY_REP1",
    "COMPANY_REP_1": "COMPANY_REP1",
    "COMPANY_OFFICER_2": "COMPANY_REP2",
    "COMPANY_REP_2": "COMPANY_REP2",
    "USDOT_REVOKED": "USDOT_REVOKED_FLAG",
    "PRIOR_REVOKE_FLAG": "USDOT_REVOKED_FLAG",
    "CLASS_CODE": "class",
    "CLASS_DEFINITION": "classdef",
    "CLASSDEF": "classdef",
    # SODA / MOTUS field names seen in live API
    "TRUCK_UNITS": "TOT_TRUCKS",
    "BUS_UNITS": "TOT_BUSES",
    "DRIVER_INTER_TOTAL": "INTER_DRS",
    "TOTAL_INTRASTATE_DRIVERS": "INTRA_DRS",
    "CARRIER_MAILING_STREET": "MAI_STR",
    "CARRIER_MAILING_CITY": "MAI_CITY",
    "CARRIER_MAILING_STATE": "MAI_ST",
    "CARRIER_MAILING_ZIP": "MAI_ZIP",
    "CARRIER_MAILING_COUNTRY": "MAI_NATN",
    "CARRIER_MAILING_CNTY": "MAI_CNTY",
    "BUSINESS_ORG_DESC": "ORG",
    "PHY_OMC_REGION": "REG",
    "SAFETY_INV_TERR": "TERR",
    "BUSINESS_ORG_ID": "BUSINESS_ORG_ID",
    "MCS150_UPDATE_CODE_ID": "MCS150_UPDATE_CODE_ID",
}


def norm_header(h: str) -> str:
    return (
        (h or "")
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def map_header(h: str, db_cols_lower: Dict[str, str] | None = None) -> str:
    n = norm_header(h)
    col = HEADER_ALIASES.get(n, n)
    # MySQL column names may be mixed-case (e.g. classdef)
    if db_cols_lower is not None:
        return db_cols_lower.get(col.lower(), col)
    return col


def db_connect():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=os.getenv("MYSQL_DATABASE", "fmcsaaa"),
        charset="utf8mb4",
        autocommit=False,
    )


def table_columns(cur, table: str) -> List[str]:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return [r[0] for r in cur.fetchall()]


def count_rows(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM `{table}`")
    return int(cur.fetchone()[0])


SODA_JSON_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"


def download_census(dest: str) -> str:
    print(f"Downloading Company Census → {dest}")
    print("(File is large — may take 10–60+ minutes depending on network)")
    with requests.get(CENSUS_CSV_URL, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last_print = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if done - last_print >= 25 * 1024 * 1024 or (
                    total and done >= total
                ):
                    if total:
                        print(f"  {done/1e6:.1f} / {total/1e6:.1f} MB")
                    else:
                        print(f"  {done/1e6:.1f} MB")
                    last_print = done
    print(f"Download complete: {dest} ({os.path.getsize(dest)/1e6:.1f} MB)")
    return dest


def import_from_soda_api(
    batch_size: int = 500,
    page_size: int = 50000,
    max_rows: Optional[int] = None,
    start_offset: int = 0,
    phy_st: Optional[str] = None,
) -> None:
    """
    Pull Company Census rows via Socrata API pagination (no giant CSV needed).
    Still upsert-only — never truncates.

    Official universe (~4.5M). Resume with --start-offset after interruption.
    Optional --phy-st TN to fill one state only.
    """
    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")
    conn = db_connect()
    cur = conn.cursor()
    before = count_rows(cur, table)
    db_cols = table_columns(cur, table)
    print(f"Table `{table}` — before: {before} rows")
    where = None
    if phy_st:
        phy_st = phy_st.strip().upper()
        where = f"phy_state='{phy_st}'"
        print(f"SODA filter: {where}")
    print(f"SODA API page_size={page_size} start_offset={start_offset}")

    # Official totals for progress (best-effort)
    try:
        cparams: Dict[str, str] = {"$select": "count(*)"}
        if where:
            cparams["$where"] = where
        cr = requests.get(SODA_JSON_URL, params=cparams, timeout=60)
        cr.raise_for_status()
        target = int(cr.json()[0].get("count", 0))
        print(f"SODA target count ≈ {target}")
    except Exception as exc:  # noqa: BLE001
        target = 0
        print(f"(could not read SODA count: {exc})")

    offset = max(0, int(start_offset))
    upsert_n = 0
    skip_n = 0
    plan_cols: Optional[List[str]] = None
    sql = ""
    t0 = time.time()

    while True:
        if max_rows is not None and upsert_n >= max_rows:
            break
        params: Dict[str, Any] = {
            "$limit": page_size,
            "$offset": offset,
            "$order": "dot_number",
        }
        if where:
            params["$where"] = where
        print(f"  fetching offset={offset} ...")
        r = requests.get(SODA_JSON_URL, params=params, timeout=180)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break

        if plan_cols is None:
            headers = list(rows[0].keys())
            plan_cols, _ = build_column_plan(headers, db_cols)
            print(f"Mapped {len(plan_cols)} fields: {plan_cols[:15]} ...")
            print(f"All mapped: {plan_cols}")
            sql = make_upsert_sql(table, plan_cols)

        db_lower = {c.lower(): c for c in db_cols}
        batch: List[List[Optional[str]]] = []
        for obj in rows:
            if max_rows is not None and upsert_n + len(batch) >= max_rows:
                break
            raw_map = {map_header(k, db_lower): obj.get(k) for k in obj}
            vals: List[Optional[str]] = []
            for c in plan_cols:
                v = raw_map.get(c)
                if v is None:
                    vals.append(None)
                else:
                    s = str(v).strip()
                    vals.append(s if s != "" else None)
            di = plan_cols.index("DOT_NUMBER")
            dot = vals[di]
            if not dot:
                skip_n += 1
                continue
            if isinstance(dot, str) and _looks_float_int(dot):
                vals[di] = str(int(float(dot)))
            else:
                vals[di] = str(dot)
            batch.append(vals)
            if len(batch) >= batch_size:
                cur.executemany(sql, batch)
                conn.commit()
                upsert_n += len(batch)
                batch.clear()

        if batch:
            cur.executemany(sql, batch)
            conn.commit()
            upsert_n += len(batch)

        elapsed = time.time() - t0
        done_at = offset + len(rows)
        pct = f" {100.0 * done_at / target:.1f}%" if target else ""
        print(
            f"  upserted={upsert_n} skip={skip_n} "
            f"next_offset={offset + page_size}{pct} "
            f"({upsert_n / max(elapsed, 0.1):.0f}/s)"
        )
        if len(rows) < page_size:
            break
        offset += page_size

    after = count_rows(cur, table)
    cur.close()
    conn.close()
    print(
        f"\nDone API import. upserted={upsert_n} skipped={skip_n}\n"
        f"DB rows before={before} after={after} (+{after - before})\n"
        f"Resume tip: python import_census.py --from-api --start-offset {offset}"
    )
    if after < before:
        print("WARNING: row count dropped")
        sys.exit(2)


def build_column_plan(
    csv_headers: Sequence[str], db_cols: Sequence[str]
) -> Tuple[List[str], List[int]]:
    """Return (db_col_names_in_order, csv_index_per_db_col)."""
    db_set = set(db_cols)
    db_lower = {c.lower(): c for c in db_cols}
    plan_cols: List[str] = []
    plan_idx: List[int] = []
    seen = set()
    for i, h in enumerate(csv_headers):
        col = map_header(h, db_lower)
        if col in SKIP_COLS or col not in db_set or col in seen:
            continue
        seen.add(col)
        plan_cols.append(col)
        plan_idx.append(i)
    if "DOT_NUMBER" not in plan_cols:
        raise SystemExit(
            "CSV has no DOT_NUMBER column after mapping. "
            f"Headers sample: {list(csv_headers)[:20]}"
        )
    return plan_cols, plan_idx


def make_upsert_sql(table: str, cols: Sequence[str]) -> str:
    col_sql = ", ".join(f"`{c}`" for c in cols)
    ph = ", ".join(["%s"] * len(cols))
    # Blank/NULL from CSV must not wipe existing cells
    updates = ", ".join(
        f"`{c}`=IF(VALUES(`{c}`) IS NULL OR VALUES(`{c}`)='', `{c}`, VALUES(`{c}`))"
        for c in cols
        if c != "DOT_NUMBER"
    )
    return (
        f"INSERT INTO `{table}` ({col_sql}) VALUES ({ph}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )


def row_values(
    raw: Sequence[str], plan_idx: Sequence[int], plan_cols: Sequence[str]
) -> Optional[List[Optional[str]]]:
    vals: List[Optional[str]] = []
    for i in plan_idx:
        v = raw[i] if i < len(raw) else ""
        if v is None:
            vals.append(None)
        else:
            s = str(v).strip()
            vals.append(s if s != "" else None)
    # Require DOT
    try:
        di = plan_cols.index("DOT_NUMBER")
    except ValueError:
        return None
    dot = vals[di]
    if not dot:
        return None
    # Normalize numeric DOT from Socrata (e.g. 44110.0)
    if isinstance(dot, str) and dot.endswith(".0") and dot.replace(".", "", 1).isdigit():
        vals[di] = dot[:-2]
    else:
        vals[di] = str(int(float(dot))) if _looks_float_int(dot) else str(dot)
    return vals


def _looks_float_int(s: str) -> bool:
    try:
        f = float(s)
        return f == int(f)
    except Exception:
        return False


def import_csv(
    path: str,
    batch_size: int = 500,
    max_rows: Optional[int] = None,
) -> None:
    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")
    conn = db_connect()
    cur = conn.cursor()
    before = count_rows(cur, table)
    db_cols = table_columns(cur, table)
    print(f"Table `{table}` — before: {before} rows, {len(db_cols)} columns")

    # utf-8-sig handles BOM from Windows exports
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            raise SystemExit("CSV is empty")

        plan_cols, plan_idx = build_column_plan(headers, db_cols)
        print(
            f"Mapped {len(plan_cols)} CSV columns → DB "
            f"(DOT at index {plan_cols.index('DOT_NUMBER')})"
        )
        print(f"Sample mapped: {plan_cols[:12]} ...")

        sql = make_upsert_sql(table, plan_cols)
        batch: List[List[Optional[str]]] = []
        read_n = 0
        upsert_n = 0
        skip_n = 0
        t0 = time.time()

        for raw in reader:
            if max_rows is not None and read_n >= max_rows:
                break
            read_n += 1
            vals = row_values(raw, plan_idx, plan_cols)
            if not vals:
                skip_n += 1
                continue
            batch.append(vals)
            if len(batch) >= batch_size:
                cur.executemany(sql, batch)
                conn.commit()
                upsert_n += len(batch)
                batch.clear()
                if upsert_n % 10000 == 0 or upsert_n < batch_size:
                    elapsed = time.time() - t0
                    print(
                        f"  upserted {upsert_n} "
                        f"({upsert_n / max(elapsed, 0.1):.0f}/s) "
                        f"read={read_n} skip={skip_n}"
                    )

        if batch:
            cur.executemany(sql, batch)
            conn.commit()
            upsert_n += len(batch)

    after = count_rows(cur, table)
    cur.close()
    conn.close()
    print(
        f"\nDone. read={read_n} upserted={upsert_n} skipped={skip_n}\n"
        f"DB rows before={before} after={after} "
        f"(+{after - before} net new DOT numbers)"
    )
    if after < before:
        print("WARNING: row count dropped — investigate immediately")
        sys.exit(2)


def main() -> None:
    p = argparse.ArgumentParser(description="Import FMCSA Company Census CSV")
    p.add_argument(
        "csv_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__) or ".", "census.csv"),
        help="Path to census CSV",
    )
    p.add_argument(
        "--download",
        action="store_true",
        help="Download official Company Census CSV first",
    )
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional limit for a test run",
    )
    p.add_argument(
        "--from-api",
        action="store_true",
        help="Import ALL rows via Socrata API pagination (recommended on VPS)",
    )
    p.add_argument(
        "--start-offset",
        type=int,
        default=0,
        help="Resume SODA pagination at this offset (after crash)",
    )
    p.add_argument(
        "--phy-st",
        default=None,
        help="Optional state only, e.g. TN (fills that state from SODA)",
    )
    args = p.parse_args()

    if args.from_api:
        import_from_soda_api(
            batch_size=args.batch_size,
            max_rows=args.max_rows,
            start_offset=args.start_offset,
            phy_st=args.phy_st,
        )
        return

    path = args.csv_path
    if args.download:
        path = download_census(path)

    if not os.path.isfile(path):
        raise SystemExit(
            f"File not found: {path}\n"
            f"Preferred: python import_census.py --from-api\n"
            f"Or: python import_census.py --download\n"
            f"CSV URL:\n{CENSUS_CSV_URL}"
        )

    import_csv(path, batch_size=args.batch_size, max_rows=args.max_rows)


if __name__ == "__main__":
    main()
