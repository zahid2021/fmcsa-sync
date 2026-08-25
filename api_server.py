#!/usr/bin/env python3
"""Fast API: 1000 rows/page + one-file export. Slim cols = fast after big backup."""
from __future__ import annotations

import csv
import io
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

app = FastAPI(title="FMCSA Carriers API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only these columns in the UI table (full 150+ cols freezes browser)
LIST_COLS = [
    "DOT_NUMBER",
    "NAME",
    "NAME_DBA",
    "ACT_STAT",
    "EMAILADDRESS",
    "TEL_NUM",
    "PHY_STR",
    "PHY_CITY",
    "PHY_ST",
    "PHY_ZIP",
    "PHY_NATN",
    "FLEETSIZE",
    "TOT_PWR",
    "TOT_DRS",
]

_cols_cache: Optional[List[str]] = None
_total_cache: Dict[str, Tuple[int, float]] = {}
TOTAL_TTL = 60.0


def db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "root"),
        database=os.getenv("MYSQL_DATABASE", "fmcsaaa"),
        connection_timeout=10,
    )


def table_name() -> str:
    return os.getenv("MYSQL_TABLE", "carrierinformation_csv")


def build_where(phy_st, start_date, end_date, date_col="ADDDATE"):
    clauses: List[str] = []
    params: List[Any] = []
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


def list_cols(cur) -> List[str]:
    global _cols_cache
    if _cols_cache is not None:
        return _cols_cache
    cur.execute(f"SHOW COLUMNS FROM `{table_name()}`")
    have = {r[0] for r in cur.fetchall()}
    cols = [c for c in LIST_COLS if c in have]
    _cols_cache = cols or sorted(list(have))[:12]
    return _cols_cache


def fast_total(cur, where, params) -> int:
    key = where + "|" + ",".join(str(p) for p in params)
    now = time.time()
    hit = _total_cache.get(key)
    if hit and hit[1] > now:
        return hit[0]

    if where == "1=1" and not params:
        cur.execute(
            "SELECT TABLE_ROWS FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (os.getenv("MYSQL_DATABASE", "fmcsaaa"), table_name()),
        )
        row = cur.fetchone()
        total = int(row[0] or 0)
    else:
        cur.execute(
            f"SELECT COUNT(*) FROM `{table_name()}` WHERE {where}", params
        )
        total = int(cur.fetchone()[0])

    _total_cache[key] = (total, now + TOTAL_TTL)
    return total


@app.get("/health")
def health():
    return {"ok": True, "version": "1.2.0"}


@app.get("/api/carriers")
def carriers(
    phy_st: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(1000, ge=1, le=1000),
) -> Dict[str, Any]:
    t0 = time.time()
    where, params = build_where(phy_st, start_date, end_date)
    if page > 500:
        page = 500
    conn = db()
    cur = conn.cursor()
    try:
        cols = list_cols(cur)
        col_sql = ", ".join(f"`{c}`" for c in cols)
        total = fast_total(cur, where, params)
        offset = (page - 1) * limit
        cur.execute(
            f"SELECT {col_sql} FROM `{table_name()}` WHERE {where} "
            f"LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        items = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "items": items,
            "columns": cols,
            "ms": int((time.time() - t0) * 1000),
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/carriers/export")
def export_one_file(
    phy_st: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    where, params = build_where(phy_st, start_date, end_date)
    conn = db()
    cur = conn.cursor()
    cur.execute(f"SHOW COLUMNS FROM `{table_name()}`")
    cols = [r[0] for r in cur.fetchall() if r[0] != "API_RAW_JSON"]
    col_sql = ", ".join(f"`{c}`" for c in cols)
    cur.execute(f"SELECT {col_sql} FROM `{table_name()}` WHERE {where}", params)
    stem = "carriers" + (f"_{phy_st.upper()}" if phy_st else "_ALL")
    filename = f"{stem}.csv"

    def generate():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        try:
            while True:
                batch = cur.fetchmany(2000)
                if not batch:
                    break
                for row in batch:
                    w.writerow(row)
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)
        finally:
            cur.close()
            conn.close()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", "8000")))
