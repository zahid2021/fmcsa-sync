#!/usr/bin/env python3
"""
Client video ask #1: backup project + MySQL BEFORE any UI/export changes,
then send on Slack / email.

Creates:
  backups/fmcsa_project_YYYYMMDD_HHMMSS.zip
  backups/fmcsaaa_YYYYMMDD_HHMMSS.sql   (via mysqldump if available)
  backups/MANIFEST.txt

Usage (on Anthony / VPS):
  python backup_for_client.py
  python backup_for_client.py --project-dir C:\\path\\to\\fmcsa-frontend
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".wenv",
    ".stenv",
    "backups",
    "exports",
    "video_frames",
    "video_frames_0824",
    "video_frames_0824b",
    "v0824",
    "vkey",
}


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def zip_project(src: Path, dest_zip: Path) -> int:
    n = 0
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
            for name in files:
                if name.endswith((".wav", ".mp4", ".zip")) and name.startswith(
                    ("video_", "bandicam")
                ):
                    continue
                full = Path(root) / name
                rel = full.relative_to(src)
                zf.write(full, arcname=str(rel))
                n += 1
    return n


def mysqldump_to(path: Path) -> tuple[bool, str]:
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "root")
    database = os.getenv("MYSQL_DATABASE", "fmcsaaa")

    dump = shutil.which("mysqldump")
    if not dump:
        return False, "mysqldump not found on PATH — use MySQL Workbench Export"

    cmd = [
        dump,
        f"-h{host}",
        f"-P{port}",
        f"-u{user}",
        f"-p{password}",
        "--single-transaction",
        "--routines",
        "--triggers",
        database,
    ]
    try:
        with path.open("wb") as f:
            proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")[:500]
            if path.exists():
                path.unlink(missing_ok=True)
            return False, err or f"mysqldump exit {proc.returncode}"
        return True, f"OK ({path.stat().st_size} bytes)"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> None:
    p = argparse.ArgumentParser(description="Backup FMCSA project + DB for client")
    p.add_argument(
        "--project-dir",
        default=None,
        help="Extra folder to zip (e.g. frontend on Anthony). Default: this repo.",
    )
    p.add_argument("--out", default="backups", help="Output folder")
    args = p.parse_args()

    here = Path(__file__).resolve().parent
    out = Path(args.out)
    if not out.is_absolute():
        out = here / out
    out.mkdir(parents=True, exist_ok=True)

    ts = stamp()
    project_zip = out / f"fmcsa_project_{ts}.zip"
    db_sql = out / f"fmcsaaa_{ts}.sql"
    manifest = out / f"MANIFEST_{ts}.txt"

    print(f"1) Zipping project → {project_zip}")
    n = zip_project(here, project_zip)
    print(f"   {n} files")

    extra_note = ""
    if args.project_dir:
        extra = Path(args.project_dir)
        if extra.is_dir():
            extra_zip = out / f"fmcsa_frontend_{ts}.zip"
            print(f"1b) Zipping frontend → {extra_zip}")
            n2 = zip_project(extra, extra_zip)
            print(f"   {n2} files")
            extra_note = f"frontend_zip={extra_zip}\n"
        else:
            extra_note = f"WARNING: --project-dir not found: {extra}\n"

    print(f"2) MySQL dump → {db_sql}")
    ok, msg = mysqldump_to(db_sql)
    print(f"   {msg}")
    if not ok:
        print(
            "\nWorkbench fallback:\n"
            "  Server → Data Export → select database fmcsaaa → Export to Self-Contained File\n"
            f"  Save as: {db_sql}"
        )

    lines = [
        f"created_at={datetime.now().isoformat()}",
        f"project_zip={project_zip} size={project_zip.stat().st_size}",
        f"db_sql={db_sql if ok else 'MISSING — use Workbench'} {msg}",
        extra_note.strip(),
        "",
        "SEND TO CLIENT:",
        "  1) Attach both zip + .sql on Slack",
        "  2) Also email the same files",
        "  3) Only AFTER client confirms backup → change pagination/export UI",
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"3) Manifest → {manifest}")
    print("\nDone. Send backups on Slack + email BEFORE UI changes.")


if __name__ == "__main__":
    main()
