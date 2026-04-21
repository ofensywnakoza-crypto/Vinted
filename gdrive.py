"""
Google Drive integration for Vinted Pipeline.

Uses a service account — no browser OAuth flow needed.

Setup (one-time, ~5 minutes):
  1. Go to https://console.cloud.google.com
  2. New project → Enable "Google Drive API"
  3. IAM & Admin → Service accounts → Create service account
  4. Keys → Add key → JSON → Download file
  5. Open your Google Drive folder → Share → paste service account email → Editor
  6. Copy the folder URL ID (the part after /folders/ in the URL)
  7. Paste JSON content into the app sidebar
"""

import io
import json
from pathlib import Path
from typing import Optional

# Optional — import only when needed so missing dep doesn't crash the whole app
def _build_service(credentials_info: dict):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def test_connection(folder_id: str, credentials_info: dict) -> tuple[bool, str]:
    """
    Verify that the service account can access the given Drive folder.
    Returns (success, message).
    """
    try:
        service = _build_service(credentials_info)
        meta = service.files().get(fileId=folder_id, fields="name,id").execute()
        return True, f"Połączono z folderem: {meta.get('name', folder_id)}"
    except Exception as e:
        return False, str(e)


def _get_or_create_subfolder(service, name: str, parent_id: str) -> str:
    """Return existing subfolder ID or create a new one."""
    query = (
        f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id,name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def upload_folder(
    local_folder: str,
    drive_parent_id: str,
    credentials_info: dict,
    progress_callback=None,
) -> tuple[bool, str]:
    """
    Upload all files in local_folder to a new subfolder in drive_parent_id.

    Returns (success, url_or_error_message).
    """
    from googleapiclient.http import MediaFileUpload

    try:
        service = _build_service(credentials_info)
        folder_name = Path(local_folder).name

        if progress_callback:
            progress_callback(f"Tworzę folder na Drive: {folder_name}")

        subfolder_id = _get_or_create_subfolder(service, folder_name, drive_parent_id)

        files = [f for f in Path(local_folder).iterdir() if f.is_file()]
        for i, fpath in enumerate(files, 1):
            if progress_callback:
                progress_callback(f"Wysyłam {i}/{len(files)}: {fpath.name}")

            mime = _guess_mime(fpath.suffix.lower())
            media = MediaFileUpload(str(fpath), mimetype=mime, resumable=False)
            file_meta = {"name": fpath.name, "parents": [subfolder_id]}
            service.files().create(body=file_meta, media_body=media).execute()

        url = f"https://drive.google.com/drive/folders/{subfolder_id}"
        return True, url

    except Exception as e:
        return False, str(e)


def upload_all_results(
    result_folders: list[str],
    drive_parent_id: str,
    credentials_info: dict,
    progress_callback=None,
) -> list[tuple[str, bool, str]]:
    """
    Upload multiple product result folders to Google Drive.
    Returns list of (folder_name, success, url_or_error).
    """
    outcomes = []
    for folder in result_folders:
        name = Path(folder).name
        ok, url = upload_folder(folder, drive_parent_id, credentials_info, progress_callback)
        outcomes.append((name, ok, url))
    return outcomes


def _guess_mime(ext: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".txt": "text/plain",
        ".json": "application/json",
        ".zip": "application/zip",
    }.get(ext, "application/octet-stream")
