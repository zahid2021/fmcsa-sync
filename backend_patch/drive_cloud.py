"""
Upload FMCSA export chunks straight to Google Drive (cloud).

One-time setup on RDP (same Gmail as Drive web):
  1. Put credentials.json next to run.py  (see SETUP_DRIVE_CLOUD.txt)
  2. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
  3. python drive_auth_once.py   → browser login → saves token.json
  4. Restart python run.py
  5. Export File → files appear in Drive → FMCSA → {slug}
"""
import os
from typing import Any, Dict, List, Optional

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
ROOT_FOLDER_NAME = "FMCSA"


def _q_escape(name: str) -> str:
    return (name or "").replace("\\", "\\\\").replace("'", "\\'")


def _backend_dir():
    return os.path.dirname(os.path.abspath(__file__))


def credentials_path():
    return os.environ.get("FMCSA_DRIVE_CREDENTIALS") or os.path.join(
        _backend_dir(), "credentials.json"
    )


def token_path():
    return os.environ.get("FMCSA_DRIVE_TOKEN") or os.path.join(
        _backend_dir(), "token.json"
    )


def drive_api_ready():
    return os.path.isfile(credentials_path()) and os.path.isfile(token_path())


def get_drive_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    tp = token_path()
    cp = credentials_path()
    if os.path.isfile(tp):
        creds = Credentials.from_authorized_user_file(tp, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.isfile(cp):
                raise FileNotFoundError(
                    f"Missing {cp}. Follow SETUP_DRIVE_CLOUD.txt"
                )
            flow = InstalledAppFlow.from_client_secrets_file(cp, SCOPES)
            # local server works on RDP when browser can open
            creds = flow.run_local_server(port=0)
        with open(tp, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_child_folder(service, name, parent_id=None):
    # type: (Any, str, Optional[str]) -> Optional[str]
    safe = _q_escape(name)
    q = (
        "name = '%s' and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false" % safe
    )
    if parent_id:
        q += " and '%s' in parents" % parent_id
    else:
        q += " and 'root' in parents"
    res = (
        service.files()
        .list(q=q, spaces="drive", fields="files(id, name)", pageSize=10)
        .execute()
    )
    files = res.get("files") or []
    return files[0]["id"] if files else None


def _ensure_folder(service, name, parent_id=None):
    # type: (Any, str, Optional[str]) -> str
    existing = _find_child_folder(service, name, parent_id)
    if existing:
        return existing
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }  # type: Dict[str, Any]
    if parent_id:
        meta["parents"] = [parent_id]
    created = service.files().create(body=meta, fields="id").execute()
    return created["id"]


def ensure_export_folder(service, slug):
    # type: (Any, str) -> tuple
    root_id = _ensure_folder(service, ROOT_FOLDER_NAME, None)
    slug_id = _ensure_folder(service, slug, root_id)
    return root_id, slug_id


def upload_file(service, local_path, folder_id, name=None):
    # type: (Any, str, str, Optional[str]) -> Dict[str, Any]
    from googleapiclient.http import MediaFileUpload

    fname = name or os.path.basename(local_path)
    q = "name = '%s' and '%s' in parents and trashed = false" % (
        _q_escape(fname),
        folder_id,
    )
    old = (
        service.files()
        .list(q=q, spaces="drive", fields="files(id)", pageSize=5)
        .execute()
        .get("files")
        or []
    )
    media = MediaFileUpload(local_path, resumable=True)
    if old:
        updated = (
            service.files()
            .update(
                fileId=old[0]["id"],
                media_body=media,
                fields="id, name, webViewLink",
            )
            .execute()
        )
        return updated
    meta = {"name": fname, "parents": [folder_id]}
    created = (
        service.files()
        .create(body=meta, media_body=media, fields="id, name, webViewLink")
        .execute()
    )
    return created


def upload_chunks_to_drive(local_paths, slug):
    # type: (List[str], str) -> Dict[str, Any]
    """
    Upload list of local chunk files to Drive / FMCSA / {slug}/
    Returns metadata for API response.
    """
    service = get_drive_service()
    _root_id, slug_id = ensure_export_folder(service, slug)
    uploaded = []
    for path in local_paths:
        info = upload_file(service, path, slug_id)
        uploaded.append({
            "name": info.get("name"),
            "id": info.get("id"),
            "webViewLink": info.get("webViewLink"),
        })
        print(f"[drive_cloud] uploaded {info.get('name')} id={info.get('id')}", flush=True)
    return {
        "ok": True,
        "mode": "google_drive_api",
        "drive_path": f"My Drive / {ROOT_FOLDER_NAME} / {slug}",
        "folder_id": slug_id,
        "files": uploaded,
    }


def status_info() -> dict:
    return {
        "credentials": os.path.isfile(credentials_path()),
        "credentials_path": credentials_path(),
        "token": os.path.isfile(token_path()),
        "token_path": token_path(),
        "api_ready": drive_api_ready(),
        "root_folder": ROOT_FOLDER_NAME,
    }
