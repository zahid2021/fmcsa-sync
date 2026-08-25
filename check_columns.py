#!/usr/bin/env python3
"""Check census API fields vs DB column fill rates."""
import requests
import mysql.connector

ALIASES = {
    "STATUS_CODE": "ACT_STAT",
    "STATUS": "ACT_STAT",
    "LEGAL_NAME": "NAME",
    "CARRIER_NAME": "NAME",
    "DBA_NAME": "NAME_DBA",
    "DUN_BRADSTREET_NO": "DBNUM",
    "PHY_COUNTRY": "PHY_NATN",
    "PHY_STREET": "PHY_STR",
    "PHY_STATE": "PHY_ST",
    "PHY_ZIPCODE": "PHY_ZIP",
    "PHY_ZIP_CODE": "PHY_ZIP",
    "PHY_COUNTY": "PHY_CNTY",
    "MAIL_COUNTRY": "MAI_NATN",
    "MAIL_STREET": "MAI_STR",
    "MAIL_CITY": "MAI_CITY",
    "MAIL_STATE": "MAI_ST",
    "MAIL_ZIP": "MAI_ZIP",
    "MAIL_ZIPCODE": "MAI_ZIP",
    "TELEPHONE": "TEL_NUM",
    "PHONE": "TEL_NUM",
    "FAX": "FAX_NUM",
    "EMAIL_ADDRESS": "EMAILADDRESS",
    "EMAIL": "EMAILADDRESS",
    "CARRIER_OPERATION": "CRRINTER",
    "ADD_DATE": "ADDDATE",
    "CHG_DATE": "CHGNDATE",
    "CHANGE_DATE": "CHGNDATE",
    "MCS150_DATE": "MCS_150_DATE",
    "MCS150_MILEAGE": "MLG150",
    "MCS151_MILEAGE": "MLG151",
    "MCS150_MILEAGE_YEAR": "MCS150MILEAGEYEAR",
    "TOTAL_DRIVERS": "TOT_DRS",
    "NBR_DRIVERS": "TOT_DRS",
    "TOTAL_POWER_UNITS": "TOT_PWR",
    "POWER_UNITS": "TOT_PWR",
    "NBR_POWER_UNIT": "TOT_PWR",
    "TOTAL_TRUCKS": "TOT_TRUCKS",
    "TOTAL_BUSES": "TOT_BUSES",
    "TOTAL_CARS": "TOT_CARS",
    "FLEET_SIZE": "FLEETSIZE",
    "SAFETY_RATING": "RATING",
    "RATING_DATE": "RATEDATE",
    "COMPANY_OFFICER_1": "COMPANY_REP1",
    "COMPANY_OFFICER_2": "COMPANY_REP2",
    "PRIOR_REVOKE_FLAG": "USDOT_REVOKED_FLAG",
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
    "CLASSDEF": "classdef",
    "BUSINESS_ORG_ID": "BUSINESS_ORG_ID",
    "MCS150_UPDATE_CODE_ID": "MCS150_UPDATE_CODE_ID",
}


def norm(h: str) -> str:
    return (h or "").strip().upper().replace(" ", "_").replace("-", "_")


def mapc(h: str, db_lower: dict) -> str:
    n = norm(h)
    col = ALIASES.get(n, n)
    return db_lower.get(col.lower(), col)


def main() -> None:
    row = requests.get(
        "https://data.transportation.gov/resource/az4n-8mr2.json",
        params={"$limit": 1},
        timeout=120,
    ).json()[0]
    api_keys = list(row.keys())
    print("API_FIELDS", len(api_keys))
    print("API_KEYS", ",".join(api_keys))

    cn = mysql.connector.connect(
        host="127.0.0.1", user="root", password="root", database="fmcsaaa"
    )
    cur = cn.cursor()
    cur.execute("SHOW COLUMNS FROM carrierinformation_csv")
    db = [r[0] for r in cur.fetchall()]
    dbset = set(db)
    db_lower = {c.lower(): c for c in db}

    mapped = []
    unmapped = []
    for k in api_keys:
        c = mapc(k, db_lower)
        if c in dbset and c not in ("created_at", "API_RAW_JSON"):
            mapped.append((k, c))
        else:
            unmapped.append(k)

    print("MAPPED_TO_DB", len(mapped))
    print("MAPPED", ",".join(f"{a}->{b}" for a, b in mapped))
    print("NOT_IN_DB_OR_SKIP", len(unmapped))
    print("UNMAPPED", ",".join(unmapped) if unmapped else "NONE")

    cols = sorted({b for _, b in mapped})
    parts = ",".join(
        f"SUM(`{c}` IS NOT NULL AND `{c}`<>'') AS `{c}`" for c in cols
    )
    cur.execute(f"SELECT COUNT(*) AS total, {parts} FROM carrierinformation_csv")
    names = [d[0] for d in cur.description]
    vals = cur.fetchone()
    total = vals[0]
    print("TOTAL", total)
    low = []
    for n, v in zip(names[1:], vals[1:]):
        pct = 100.0 * int(v) / total if total else 0
        print(f"FILL {n}: {v} ({pct:.1f}%)")
        if pct < 50:
            low.append(n)
    print("LOW_FILL_<50pct", ",".join(low) if low else "NONE")
    cur.close()
    cn.close()


if __name__ == "__main__":
    main()
