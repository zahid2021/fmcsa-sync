#!/usr/bin/env python3
"""Compare DB counts vs official FMCSA Company Census (SODA)."""

from __future__ import annotations

import os
import sys

import mysql.connector
import requests
from dotenv import load_dotenv

load_dotenv()

SODA = "https://data.transportation.gov/resource/az4n-8mr2.json"


def soda_count(where: str | None = None) -> int:
    params = {"$select": "count(*)"}
    if where:
        params["$where"] = where
    r = requests.get(SODA, params=params, timeout=60)
    r.raise_for_status()
    return int(r.json()[0]["count"])


def main() -> None:
    states = sys.argv[1:] or ["TN"]
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=os.getenv("MYSQL_DATABASE", "fmcsaaa"),
    )
    cur = conn.cursor()
    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")

    soda_all = soda_count()
    cur.execute(f"SELECT COUNT(*) FROM `{table}`")
    db_all = int(cur.fetchone()[0])
    print(f"ALL USA  SODA={soda_all:,}  DB={db_all:,}  gap={soda_all - db_all:,}")

    for st in states:
        st = st.upper()
        s = soda_count(f"phy_state='{st}'")
        cur.execute(f"SELECT COUNT(*) FROM `{table}` WHERE PHY_ST=%s", (st,))
        d = int(cur.fetchone()[0])
        print(f"{st:4}     SODA={s:,}  DB={d:,}  gap={s - d:,}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
