"""
One-time Google Drive login on RDP.
Run from fmsca_backend folder AFTER credentials.json is in place:

  python drive_auth_once.py

Browser opens → login with client Gmail (same as Drive web) → Allow → token.json saved.
Then restart: python run.py
"""
import os
import sys

# same folder as this script / run.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drive_cloud import credentials_path, get_drive_service, status_info, upload_chunks_to_drive


def main():
    print("Drive status:", status_info(), flush=True)
    cp = credentials_path()
    if not os.path.isfile(cp):
        print("ERROR: missing credentials.json")
        print("Put OAuth Desktop client JSON next to run.py as credentials.json")
        print("See SETUP_DRIVE_CLOUD.txt")
        sys.exit(1)
    print("Opening browser for Google login…", flush=True)
    service = get_drive_service()
    about = service.about().get(fields="user").execute()
    user = (about.get("user") or {}).get("emailAddress")
    print("OK — logged in as:", user, flush=True)
    print("token.json saved. Restart Flask: python run.py", flush=True)
    print("Export File will upload to: My Drive / FMCSA / {slug}", flush=True)


if __name__ == "__main__":
    main()
