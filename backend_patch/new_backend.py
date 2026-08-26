"""
FMCSA Flask API — same DB/table as original project.
Copy to run.py and backend.py. Start: python run.py
Port 5000. Routes: /all, /filter/, /export, /export/drive
"""
from flask import Flask, jsonify, request, Response
import mysql.connector
from flask_cors import CORS
from datetime import datetime, timedelta
import csv
import io
import os
import re
import time

# Original project settings (from working history)
config = {
    "user": "root",
    "password": "root",
    "host": "localhost",
    "database": "fmcsaaa",
}

SELECT_COLS = (
    "ACT_STAT,ADDDATE,AVG_TLD,CARSHIP,COMPANY_REP1,COMPANY_REP2,"
    "DOT_NUMBER,FAX_NUM,FLEETSIZE,NAME,EMAILADDRESS,PHY_CITY,"
    "PHY_CNTY,PHY_NATN,PHY_ST,PHY_STR,PHY_ZIP,TEL_NUM,created_at"
)
TABLE = "carrierinformation_csv"
# Stable row order for export ranges (row 100001 = 100001st matching record)
EXPORT_ORDER_BY = "DOT_NUMBER"

# If user picks street/city/etc. but types a 2-letter state code, use PHY_ST
GEO_MISTAKES = {
    "PHY_STR",
    "PHY_CITY",
    "PHY_CNTY",
    "PHY_NATN",
    "PHY_ZIP",
    "COMPANY_REP1",
    "COMPANY_REP2",
    "NAME",
    "EMAILADDRESS",
    "TEL_NUM",
    "FAX_NUM",
}

_cached_total = None
_cached_at = 0.0

app = Flask(__name__)
CORS(app)


def get_connection():
    try:
        return mysql.connector.connect(**config)
    except mysql.connector.Error as err:
        print("DB connect error:", err, flush=True)
        return None


def rows_to_dicts(cursor, data):
    cols = [c[0] for c in cursor.description]
    out = []
    for row in data:
        d = {}
        for i, name in enumerate(cols):
            d[name] = "" if row[i] is None else row[i]
        out.append(d)
    return out


def page_args():
    page = max(1, int(request.args.get("page", 1) or 1))
    per_page = int(request.args.get("per_page") or 1000)
    per_page = min(1000, max(1, per_page))
    return page, per_page, (page - 1) * per_page


def filter_args():
    filterkey = request.args.get("filterkey") or request.args.get("filter_key")
    filtervalue = request.args.get("filtervalue") or request.args.get("filter_value")
    if filtervalue is not None:
        filtervalue = str(filtervalue).strip()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    return filterkey, filtervalue, start_date, end_date


def normalize_filter(filterkey, filtervalue):
    """
    Old UI often: value=TN + wrong header (PHY_STR).
    State codes are always PHY_ST.
    """
    if not filterkey or filtervalue is None:
        return filterkey, filtervalue, None
    note = None
    fv = str(filtervalue).strip()
    fk = str(filterkey).strip()
    if re.match(r"^[A-Za-z]{2}$", fv) and fk.upper() != "PHY_ST":
        if fk.upper() in GEO_MISTAKES or fk.upper().startswith("PHY_"):
            note = f"Auto-fixed header {fk} -> PHY_ST for state code {fv.upper()}"
            print(note, flush=True)
            fk = "PHY_ST"
            fv = fv.upper()
    if fk.upper() == "PHY_ST":
        fv = fv.upper()
    return fk, fv, note


def build_where(filterkey, filtervalue, start_date, end_date):
    if filterkey and not re.match(r"^[A-Za-z0-9_]+$", str(filterkey)):
        raise ValueError("invalid filterkey")

    if start_date or end_date:
        if not end_date or start_date == end_date:
            try:
                d = datetime.strptime(start_date, "%Y-%m-%d")
                end_date = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                end_date = start_date
        if filterkey and filterkey != "created_at" and filtervalue:
            return (
                f"`{filterkey}` = %s AND created_at >= DATE(%s) "
                f"AND created_at <= DATE(%s)",
                [filtervalue, start_date, end_date],
            )
        return (
            "created_at >= DATE(%s) AND created_at <= DATE(%s)",
            [start_date, end_date],
        )

    if filterkey and filtervalue:
        # Index-friendly equality (same idea as old API, without UPPER(CAST))
        return f"`{filterkey}` = %s", [filtervalue]
    return "1=1", []


def ensure_indexes(conn):
    cur = conn.cursor()
    # TEXT columns need prefix length (from project history)
    for sql in (
        f"CREATE INDEX idx_phy_st ON {TABLE} (PHY_ST(2))",
        f"CREATE INDEX idx_dot_number ON {TABLE} (DOT_NUMBER(16))",
        f"CREATE INDEX idx_act_stat ON {TABLE} (ACT_STAT(8))",
        f"CREATE INDEX idx_name ON {TABLE} (NAME(64))",
        f"CREATE INDEX idx_phy_city ON {TABLE} (PHY_CITY(64))",
        f"CREATE INDEX idx_company_rep1 ON {TABLE} (COMPANY_REP1(64))",
    ):
        try:
            cur.execute(sql)
            conn.commit()
            print("Index:", sql, flush=True)
        except mysql.connector.Error as err:
            # Duplicate / exists is fine
            if err.errno != 1061:
                print("Index skip:", err, flush=True)
    cur.close()


def full_count(cursor):
    """Prefer cache; first hit uses fast approximate table rows (instant)."""
    global _cached_total, _cached_at
    now = time.time()
    if _cached_total is not None and now - _cached_at < 600:
        return _cached_total
    try:
        cursor.execute(f"SHOW TABLE STATUS LIKE '{TABLE}'")
        status = cursor.fetchone()
        # Rows column index = 4 in SHOW TABLE STATUS
        approx = int(status[4]) if status and status[4] is not None else 0
        if approx > 0:
            _cached_total = approx
            _cached_at = now
            return approx
    except mysql.connector.Error as err:
        print("approx count skip:", err, flush=True)
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
    _cached_total = cursor.fetchone()[0]
    _cached_at = now
    return _cached_total


@app.route("/", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/all", methods=["GET"])
def all_rows():
    t0 = time.time()
    conn = get_connection()
    if conn is None:
        return jsonify({"error": "db connection failed"}), 500
    page, per_page, offset = page_args()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT {SELECT_COLS} FROM {TABLE} LIMIT %s OFFSET %s",
            (per_page, offset),
        )
        rows = rows_to_dicts(cur, cur.fetchall())
        total = full_count(cur)
    except mysql.connector.Error as err:
        print("SQL /all:", err, flush=True)
        return jsonify({"error": str(err)}), 500
    finally:
        cur.close()
        conn.close()
    print(f"[all] rows={len(rows)} total={total} {time.time()-t0:.2f}s", flush=True)
    return jsonify({"data": rows, "total_count": total})


@app.route("/filter/", methods=["GET"])
def get_filter():
    t0 = time.time()
    conn = get_connection()
    if conn is None:
        return jsonify({"error": "db connection failed"}), 500

    page, per_page, offset = page_args()
    filterkey, filtervalue, start_date, end_date = filter_args()
    filterkey, filtervalue, note = normalize_filter(filterkey, filtervalue)
    print("FILTER raw", dict(request.args), "->", filterkey, filtervalue, flush=True)

    try:
        where, params = build_where(filterkey, filtervalue, start_date, end_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE {where}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"SELECT {SELECT_COLS} FROM {TABLE} WHERE {where} "
            f"LIMIT %s OFFSET %s",
            [*params, per_page, offset],
        )
        rows = rows_to_dicts(cur, cur.fetchall())
    except mysql.connector.Error as err:
        print("SQL /filter/:", err, flush=True)
        return jsonify({"error": str(err), "data": [], "total_count": 0}), 500
    finally:
        cur.close()
        conn.close()

    print(
        f"[filter] {where} {params} total={total} rows={len(rows)} "
        f"{time.time()-t0:.2f}s",
        flush=True,
    )
    payload = {"data": rows, "total_count": total}
    if note:
        payload["note"] = note
    return jsonify(payload)


@app.route("/export", methods=["GET"])
@app.route("/export/", methods=["GET"])
def export_one_file():
    filterkey, filtervalue, start_date, end_date = filter_args()
    filterkey, filtervalue, _note = normalize_filter(filterkey, filtervalue)
    try:
        where, params = build_where(filterkey, filtervalue, start_date, end_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    conn = get_connection()
    if conn is None:
        return jsonify({"error": "db connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT {SELECT_COLS} FROM {TABLE} WHERE {where}", params)
    except mysql.connector.Error as err:
        cur.close()
        conn.close()
        return jsonify({"error": str(err)}), 500

    cols = [c.strip() for c in SELECT_COLS.split(",")]
    stem = "carriers"
    if filterkey and filtervalue:
        safe = re.sub(r"[^\w\-]+", "_", str(filtervalue))[:40]
        stem = f"carriers_{filterkey}_{safe}"
    filename = f"{stem}_ALL.csv"

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
                    w.writerow(["" if v is None else v for v in row])
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)
        finally:
            cur.close()
            conn.close()

    return Response(
        generate(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


CHUNK_SIZE = 10000
EXPORT_API_VERSION = 3  # 3 = start_number + row_count slice (max CHUNK_SIZE per file)

try:
    from openpyxl import Workbook

    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

try:
    import drive_cloud

    HAS_DRIVE_CLOUD = True
except ImportError:
    drive_cloud = None
    HAS_DRIVE_CLOUD = False


def resolve_drive_root():
    """
    Google Drive for desktop sync folder: .../My Drive/FMCSA
    Set FMCSA_DRIVE_ROOT on RDP if auto-detect fails.
    Prefer cloud API upload when token.json exists (see drive_cloud.py).
    """
    env = (os.environ.get("FMCSA_DRIVE_ROOT") or "").strip()
    if env:
        return env
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Google Drive", "My Drive", "FMCSA"),
        os.path.join(home, "My Drive", "FMCSA"),
        os.path.join(home, "GoogleDrive", "My Drive", "FMCSA"),
        r"G:\My Drive\FMCSA",
        r"C:\Users\Administrator\Google Drive\My Drive\FMCSA",
        r"C:\Users\Administrator\My Drive\FMCSA",
        r"C:\Users\Administrator\Desktop\Google Drive\My Drive\FMCSA",
        os.path.join(home, "Desktop", "FMCSA_Drive", "FMCSA"),
        r"C:\Users\Administrator\Desktop\FMCSA_Drive\FMCSA",
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
        parent = os.path.dirname(path)
        if os.path.isdir(parent):
            return path
    return candidates[0]


def use_cloud_drive():
    return bool(HAS_DRIVE_CLOUD and drive_cloud.drive_api_ready())


def write_chunk_xlsx(path, cols, batch):
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("carriers")
    ws.append(list(cols))
    for row in batch:
        ws.append(["" if v is None else v for v in row])
    wb.save(path)


def write_chunk_csv(path, cols, batch):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for row in batch:
            w.writerow(["" if v is None else v for v in row])


def safe_slug(raw):
    s = re.sub(r"[^\w\- ]+", "", str(raw or "").strip())
    s = re.sub(r"\s+", "_", s).strip("._-")
    return (s or "export")[:80]


def parse_export_range(total_count):
    """
    Pick any slice of filtered rows (1-based positions).

    Client: start_number + row_count
      e.g. start 100001, count 20000 -> rows 100001..120000
      e.g. start 400001, count 50000 -> rows 400001..450000

    Also accepts end_number (legacy): end must be >= start.
    """
    raw_start = (request.args.get("start_number") or request.args.get("start") or "").strip()
    raw_count = (
        request.args.get("row_count")
        or request.args.get("count")
        or request.args.get("number_of_rows")
        or ""
    ).strip()
    raw_end = (request.args.get("end_number") or request.args.get("end") or "").strip()

    if not raw_start:
        raise ValueError("start_number is required for Export File")
    try:
        start_num = int(raw_start)
    except ValueError:
        raise ValueError("start_number must be an integer")

    row_count = None
    if raw_count:
        try:
            row_count = int(raw_count)
        except ValueError:
            raise ValueError("row_count must be an integer")
    elif raw_end:
        try:
            end_num = int(raw_end)
        except ValueError:
            raise ValueError("end_number must be an integer")
        if end_num < start_num:
            raise ValueError("end_number must be >= start_number")
        row_count = end_num - start_num + 1
    else:
        raise ValueError("row_count is required (how many rows to export from start)")

    if start_num < 1:
        raise ValueError("start_number must be at least 1")
    if row_count < 1:
        raise ValueError("row_count must be at least 1")
    if total_count > 0 and start_num > total_count:
        raise ValueError(
            f"start_number ({start_num}) exceeds filtered total ({total_count})"
        )

    end_num = start_num + row_count - 1
    if total_count > 0 and end_num > total_count:
        raise ValueError(
            f"Range {start_num}-{end_num} exceeds filtered total ({total_count}). "
            f"Max row_count from this start: {total_count - start_num + 1}"
        )

    offset = start_num - 1
    return start_num, end_num, row_count, offset


@app.route("/export/drive", methods=["GET"])
@app.route("/export/drive/", methods=["GET"])
def export_to_drive():
    """
    Client: slug + start_number + row_count + Export File →
    Google Drive / FMCSA / {slug} / chunk_{from}_{to}.xlsx (10k rows per file max).

    Exports only the chosen slice from filtered results (any start, any count).
    """
    import shutil
    import tempfile

    raw_slug = (request.args.get("slug") or "").strip()
    if not raw_slug:
        return jsonify({"error": "slug name is required"}), 400
    slug = safe_slug(raw_slug)

    filterkey, filtervalue, start_date, end_date = filter_args()
    filterkey, filtervalue, _note = normalize_filter(filterkey, filtervalue)
    try:
        where, params = build_where(filterkey, filtervalue, start_date, end_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if where == "1=1":
        return jsonify({"error": "Apply a filter before Export File"}), 400

    conn = get_connection()
    if conn is None:
        return jsonify({"error": "db connection failed"}), 500

    cols = [c.strip() for c in SELECT_COLS.split(",")]
    cloud = use_cloud_drive()
    temp_dir = None
    start_num = end_num = None
    if cloud:
        temp_dir = tempfile.mkdtemp(prefix="fmcsa_drive_")
        folder = temp_dir
        drive_root = "Google Drive (cloud API)"
    else:
        drive_root = resolve_drive_root()
        folder = os.path.join(drive_root, slug)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as err:
            conn.close()
            return jsonify({
                "error": (
                    f"Cannot create folder: {folder} ({err}). "
                    "Install Google Drive for desktop, set FMCSA_DRIVE_ROOT "
                    "to My Drive\\FMCSA, or add credentials.json and run drive_auth_once.py."
                ),
            }), 500

    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE {where}", params)
        total = int(cur.fetchone()[0] or 0)
        if total < 1:
            cur.close()
            conn.close()
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({"error": "No rows match this filter."}), 400
        try:
            start_num, end_num, row_count, offset = parse_export_range(total)
        except ValueError as e:
            cur.close()
            conn.close()
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({"error": str(e)}), 400
        query_params = list(params) + [int(row_count), int(offset)]
        print(
            f"[export/drive] slice start={start_num} count={row_count} "
            f"offset={offset} filter_total={total}",
            flush=True,
        )
        cur.execute(
            f"SELECT {SELECT_COLS} FROM {TABLE} WHERE {where} "
            f"ORDER BY {EXPORT_ORDER_BY} LIMIT %s OFFSET %s",
            query_params,
        )
    except mysql.connector.Error as err:
        cur.close()
        conn.close()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": str(err)}), 500

    use_xlsx = HAS_XLSX
    ext = "xlsx" if use_xlsx else "csv"
    files = []
    local_paths = []
    written = 0
    try:
        while written < row_count:
            need = min(CHUNK_SIZE, row_count - written)
            batch = cur.fetchmany(need)
            if not batch:
                break
            if len(batch) > need:
                batch = batch[:need]
            chunk_from = start_num + written
            chunk_to = chunk_from + len(batch) - 1
            name = f"chunk_{chunk_from}_{chunk_to}.{ext}"
            path = os.path.join(folder, name)
            if use_xlsx:
                write_chunk_xlsx(path, cols, batch)
            else:
                write_chunk_csv(path, cols, batch)
            written += len(batch)
            local_paths.append(path)
            files.append({
                "name": name,
                "path": path,
                "rows": len(batch),
                "from_row": chunk_from,
                "to_row": chunk_to,
            })
            print(
                f"[export/drive] wrote {name} rows={len(batch)} "
                f"total_written={written}/{row_count}",
                flush=True,
            )
    finally:
        cur.close()
        conn.close()

    upload_meta = None
    if cloud:
        try:
            upload_meta = drive_cloud.upload_chunks_to_drive(local_paths, slug)
        except Exception as err:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({
                "error": f"Google Drive upload failed: {err}",
                "hint": "Re-run: python drive_auth_once.py",
            }), 500
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        files = [
            {
                "name": f.get("name"),
                "id": f.get("id"),
                "webViewLink": f.get("webViewLink"),
                "rows": files[i]["rows"] if i < len(files) else None,
            }
            for i, f in enumerate(upload_meta.get("files") or [])
        ]

    note = None
    if not use_xlsx:
        note = "openpyxl missing — wrote CSV. Run: pip install openpyxl"
    elif cloud:
        note = f"Uploaded to Google Drive: My Drive / FMCSA / {slug}"
    else:
        note = (
            "Saved to Google Drive sync folder (FMCSA_DRIVE_ROOT). "
            "Confirm Drive for desktop is syncing, or use credentials.json + drive_auth_once.py."
        )

    return jsonify({
        "ok": True,
        "api_version": EXPORT_API_VERSION,
        "slug": slug,
        "start_number": start_num,
        "end_number": end_num,
        "row_count": row_count,
        "range_rows": written,
        "folder": (
            upload_meta.get("drive_path")
            if upload_meta
            else folder
        ),
        "drive_root": drive_root,
        "mode": "google_drive_api" if cloud else "local_folder",
        "format": ext,
        "total_rows": written,
        "total_count": total,
        "chunks": len(files),
        "chunk_size": CHUNK_SIZE,
        "files": files,
        "note": note,
    })


@app.route("/export/drive/status", methods=["GET"])
@app.route("/export/drive/status/", methods=["GET"])
def export_drive_status():
    root = resolve_drive_root()
    exists = os.path.isdir(root)
    cloud_info = drive_cloud.status_info() if HAS_DRIVE_CLOUD else {
        "api_ready": False,
        "hint": "drive_cloud.py missing",
    }
    return jsonify({
        "drive_root": root,
        "local_folder_exists": exists,
        "openpyxl": HAS_XLSX,
        "chunk_size": CHUNK_SIZE,
        "env_FMCSA_DRIVE_ROOT": (os.environ.get("FMCSA_DRIVE_ROOT") or "").strip() or None,
        "drive_api": cloud_info,
        "export_api_version": EXPORT_API_VERSION,
        "will_upload_to_cloud": use_cloud_drive(),
        "hint": (
            "OK — Export File uploads to Google Drive cloud (FMCSA/{slug})"
            if use_cloud_drive()
            else (
                "Using local Drive sync folder. Optional API upload: "
                "credentials.json + python drive_auth_once.py"
            )
        ),
    })


if __name__ == "__main__":
    c = get_connection()
    if c:
        ensure_indexes(c)
        c.close()
    print("ROUTES:", sorted(str(r) for r in app.url_map.iter_rules()), flush=True)
    print(
        "Drive cloud:", use_cloud_drive(),
        "local:", resolve_drive_root(),
        "xlsx=", HAS_XLSX,
        flush=True,
    )
    print("Listen http://127.0.0.1:5000", flush=True)
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
