#!/usr/bin/env python3
"""
Chunked Excel export — matches client UI (Chunks 1–N + EXPORT TO EXCEL).

Video (bandicam 2026-08-24): client filtered PHY_ST=TN, Total Items ~79621,
opened Chunks dropdown, hovered EXPORT TO EXCEL.

Usage (VPS):
  python export_excel_chunks.py --phy-st TN --chunks 8
  python export_excel_chunks.py --phy-st TN --chunks 4 --out C:\\exports
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
from typing import List, Optional, Sequence

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# Prefer openpyxl when available; otherwise write CSV that Excel opens.
try:
    from openpyxl import Workbook

    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False


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


def write_xlsx(path: Path, headers: Sequence[str], rows: Sequence[Sequence]) -> None:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("carriers")
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    wb.save(path)


def write_csv(path: Path, headers: Sequence[str], rows: Sequence[Sequence]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Export carriers in N Excel chunks")
    p.add_argument("--phy-st", default=None, help="Filter PHY_ST e.g. TN")
    p.add_argument("--start-date", default=None, help="yyyy-mm-dd on ADDDATE")
    p.add_argument("--end-date", default=None, help="yyyy-mm-dd on ADDDATE")
    p.add_argument("--chunks", type=int, default=8, help="1–8 like the UI")
    p.add_argument("--out", default="exports", help="Output folder")
    p.add_argument(
        "--date-col",
        default="ADDDATE",
        help="Column used for date filter (default ADDDATE)",
    )
    args = p.parse_args()

    chunks = max(1, min(8, int(args.chunks)))
    table = os.getenv("MYSQL_TABLE", "carrierinformation_csv")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    where, params = build_where(
        args.phy_st, args.start_date, args.end_date, args.date_col
    )

    conn = db_connect()
    cur = conn.cursor()
    cols = [c for c in table_columns(cur, table) if c != "API_RAW_JSON"]
    col_sql = ", ".join(f"`{c}`" for c in cols)

    cur.execute(f"SELECT COUNT(*) FROM `{table}` WHERE {where}", params)
    total = int(cur.fetchone()[0])
    print(f"Total Items: {total} (filter: {where} {params})")
    if total == 0:
        raise SystemExit("No rows match filter")

    per = math.ceil(total / chunks)
    print(f"Exporting {chunks} chunk(s) × ~{per} rows → {out_dir.resolve()}")
    if not HAS_XLSX:
        print("openpyxl not installed — writing .csv (Excel opens these). pip install openpyxl")

    for i in range(chunks):
        offset = i * per
        cur.execute(
            f"SELECT {col_sql} FROM `{table}` WHERE {where} "
            f"ORDER BY DOT_NUMBER LIMIT %s OFFSET %s",
            [*params, per, offset],
        )
        rows = cur.fetchall()
        if not rows:
            break
        stem = f"carriers"
        if args.phy_st:
            stem += f"_{args.phy_st.upper()}"
        stem += f"_chunk{i + 1}of{chunks}"
        if HAS_XLSX:
            path = out_dir / f"{stem}.xlsx"
            write_xlsx(path, cols, rows)
        else:
            path = out_dir / f"{stem}.csv"
            write_csv(path, cols, rows)
        print(f"  wrote {path.name} ({len(rows)} rows)")

    cur.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
