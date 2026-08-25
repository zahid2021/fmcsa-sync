#!/usr/bin/env python3
"""
ONE-file export (client video 2026-08-24).

Client ask: remove Chunks — download ALL filtered rows in a single Excel/CSV
without browser timeout. Stream from MySQL in batches.

Usage:
  python export_one_file.py --phy-st TN
  python export_one_file.py --phy-st TN --format csv
  python export_one_file.py --phy-st TN --out C:\\fmcsa_sync\\exports
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import List, Optional, Sequence

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

try:
    from openpyxl import Workbook

    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

BATCH = 2000


def db_connect():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=os.getenv("MYSQL_DATABASE", "fmcsaaa"),
    )


def table_columns(cur, table: str) -> List[str]:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return [r[0] for r in cur.fetchall()]


def build_where(
    phy_st: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    date_col: str,
) -> tuple[str, list]:
    clauses: List[str] = []
    params: list = []
    if phy_st:
        clauses.append("PHY_ST = %s")
        params.append(phy_st.strip().upper())
    if start_date:
        clauses.append(f"`{date_col}` >= %s")
        params.append(start_date.replace("-", ""))
    if end_date:
        clauses.append(f"`{date_col}` <= %s")
        params.append(end_date.replace("-", ""))
    if not clauses:
        return "1=1", []
    return " AND ".join(clauses), params


def export_xlsx(path: Path, headers: Sequence[str], cur, sql: str, params: list) -> int:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("carriers")
    ws.append(list(headers))
    n = 0
    cur.execute(sql, params)
    while True:
        rows = cur.fetchmany(BATCH)
        if not rows:
            break
        for row in rows:
            ws.append(list(row))
            n += 1
        print(f"  … {n} rows", flush=True)
    wb.save(path)
    return n


def export_csv(path: Path, headers: Sequence[str], cur, sql: str, params: list) -> int:
    n = 0
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        cur.execute(sql, params)
        while True:
            rows = cur.fetchmany(BATCH)
            if not rows:
                break
            w.writerows(rows)
            n += len(rows)
            print(f"  … {n} rows", flush=True)
    return n


def main() -> None:
    p = argparse.ArgumentParser(
        description="Export ALL matching carriers to ONE file (no chunks)"
    )
    p.add_argument("--phy-st", default=None, help="Filter PHY_ST e.g. TN")
    p.add_argument("--start-date", default=None, help="yyyy-mm-dd on ADDDATE")
    p.add_argument("--end-date", default=None, help="yyyy-mm-dd on ADDDATE")
    p.add_argument("--out", default="exports", help="Output folder")
    p.add_argument(
        "--format",
        choices=("xlsx", "csv", "auto"),
        default="auto",
        help="xlsx needs openpyxl; csv always works and opens in Excel",
    )
    p.add_argument(
        "--date-col",
        default="ADDDATE",
        help="Column used for date filter (default ADDDATE)",
    )
    args = p.parse_args()

    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    where, params = build_where(
        args.phy_st, args.start_date, args.end_date, args.date_col
    )

    conn = db_connect()
    # SSCursor streams from server — avoids loading 80k+ rows into RAM at once
    cur = conn.cursor(buffered=False)
    cols = [c for c in table_columns(cur, table) if c != "API_RAW_JSON"]
    col_sql = ", ".join(f"`{c}`" for c in cols)

    cur.execute(f"SELECT COUNT(*) FROM `{table}` WHERE {where}", params)
    total = int(cur.fetchone()[0])
    print(f"Total Items: {total} (filter: {where} {params})")
    if total == 0:
        raise SystemExit("No rows match filter")

    stem = "carriers"
    if args.phy_st:
        stem += f"_{args.phy_st.upper()}"
    stem += "_ALL"

    fmt = args.format
    if fmt == "auto":
        fmt = "xlsx" if HAS_XLSX else "csv"
    if fmt == "xlsx" and not HAS_XLSX:
        print("openpyxl missing — falling back to CSV")
        fmt = "csv"

    sql = (
        f"SELECT {col_sql} FROM `{table}` WHERE {where} ORDER BY DOT_NUMBER"
    )
    path = out_dir / f"{stem}.{fmt}"
    print(f"Writing ONE file → {path.resolve()}")

    if fmt == "xlsx":
        n = export_xlsx(path, cols, cur, sql, params)
    else:
        n = export_csv(path, cols, cur, sql, params)

    cur.close()
    conn.close()
    print(f"Done. {n} rows in {path.name} (single file, no chunks).")


if __name__ == "__main__":
    main()
