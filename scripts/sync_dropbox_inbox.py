#!/usr/bin/env python3

import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
API_BASE_URL = "https://api.dropboxapi.com/2"
CONTENT_BASE_URL = "https://content.dropboxapi.com/2"
OAUTH_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download new Dropbox photos into a local staging inbox.",
    )
    parser.add_argument("--staging-dir", required=True, help="Local staging directory")
    parser.add_argument(
        "--dropbox-root",
        required=True,
        help="Dropbox inbox directory, for example /site-photo-inbox",
    )
    parser.add_argument(
        "--archive-root",
        default="/site-photo-archive",
        help="Dropbox archive directory for processed files",
    )
    return parser.parse_args()


def normalize_dropbox_path(path: str) -> PurePosixPath:
    cleaned = path.strip()
    if not cleaned:
        raise ValueError("Dropbox path cannot be empty")

    normalized = PurePosixPath(cleaned if cleaned.startswith("/") else f"/{cleaned}")
    if normalized == PurePosixPath("."):
        raise ValueError("Dropbox path cannot resolve to the current directory")
    return normalized


def is_supported_image(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in SUPPORTED_EXTENSIONS


def relative_dropbox_path(path: str, root: PurePosixPath) -> PurePosixPath:
    return normalize_dropbox_path(path).relative_to(root)


def archive_destination(
    source_path: str,
    inbox_root: PurePosixPath,
    archive_root: PurePosixPath,
) -> PurePosixPath:
    return archive_root / relative_dropbox_path(source_path, inbox_root)


def require_access_token() -> str:
    direct_token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    if direct_token:
        return direct_token

    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    app_key = os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_APP_SECRET")

    if not refresh_token or not app_key or not app_secret:
        raise RuntimeError(
            "Provide DROPBOX_ACCESS_TOKEN or the trio of DROPBOX_REFRESH_TOKEN, "
            "DROPBOX_APP_KEY, and DROPBOX_APP_SECRET."
        )

    credentials = base64.b64encode(f"{app_key}:{app_secret}".encode("utf-8")).decode(
        "ascii"
    )
    request = Request(
        OAUTH_TOKEN_URL,
        data=urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urlopen(request) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["access_token"]


def read_error_payload(error: HTTPError) -> str:
    body = error.read().decode("utf-8", errors="replace")
    if body:
        return body
    return str(error)


def dropbox_api_json(token: str, endpoint: str, payload: dict) -> dict:
    request = Request(
        f"{API_BASE_URL}/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(
            f"Dropbox API request failed for {endpoint}: {read_error_payload(error)}"
        ) from error


def ensure_remote_folder(token: str, folder: PurePosixPath) -> None:
    if folder in {PurePosixPath("/"), PurePosixPath(".")}:
        return

    parents = [
        parent for parent in reversed(folder.parents) if parent != PurePosixPath("/")
    ]
    for parent in parents:
        create_remote_folder(token, parent)
    create_remote_folder(token, folder)


def create_remote_folder(token: str, folder: PurePosixPath) -> None:
    try:
        dropbox_api_json(
            token,
            "files/create_folder_v2",
            {"path": folder.as_posix(), "autorename": False},
        )
    except RuntimeError as error:
        if "conflict" not in str(error):
            raise


def list_remote_images(token: str, inbox_root: PurePosixPath) -> list[dict]:
    payload = {
        "path": "" if inbox_root == PurePosixPath("/") else inbox_root.as_posix(),
        "recursive": True,
        "include_deleted": False,
    }
    response = dropbox_api_json(token, "files/list_folder", payload)
    entries = list(response.get("entries", []))

    while response.get("has_more"):
        response = dropbox_api_json(
            token,
            "files/list_folder/continue",
            {"cursor": response["cursor"]},
        )
        entries.extend(response.get("entries", []))

    files = [
        entry
        for entry in entries
        if entry.get(".tag") == "file"
        and is_supported_image(entry.get("path_display", ""))
    ]
    return sorted(files, key=lambda entry: entry["path_lower"])


def download_remote_file(token: str, source_path: str, destination: Path) -> None:
    request = Request(
        f"{CONTENT_BASE_URL}/files/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": source_path}),
        },
        method="POST",
    )

    try:
        with urlopen(request) as response:
            contents = response.read()
    except HTTPError as error:
        raise RuntimeError(
            f"Dropbox download failed for {source_path}: {read_error_payload(error)}"
        ) from error

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)


def move_remote_file(
    token: str, source_path: str, destination_path: PurePosixPath
) -> None:
    ensure_remote_folder(token, destination_path.parent)
    dropbox_api_json(
        token,
        "files/move_v2",
        {
            "from_path": source_path,
            "to_path": destination_path.as_posix(),
            "autorename": True,
        },
    )


def sync_dropbox_inbox(
    staging_dir: Path,
    inbox_root: PurePosixPath,
    archive_root: PurePosixPath,
) -> int:
    if archive_root == inbox_root or archive_root.is_relative_to(inbox_root):
        raise ValueError("Archive path must live outside the Dropbox inbox path")

    staging_dir.mkdir(parents=True, exist_ok=True)

    token = require_access_token()
    files = list_remote_images(token, inbox_root)

    if not files:
        print(f"No Dropbox images found in {inbox_root.as_posix()}")
        return 0

    downloaded = 0
    for entry in files:
        source_path = entry["path_display"]
        relative_path = relative_dropbox_path(source_path, inbox_root)
        destination = staging_dir.joinpath(*relative_path.parts)
        archived_path = archive_destination(source_path, inbox_root, archive_root)

        download_remote_file(token, source_path, destination)
        move_remote_file(token, source_path, archived_path)

        downloaded += 1
        print(f"Staged {source_path} -> {destination}")
        print(f"Archived {source_path} -> {archived_path.as_posix()}")

    print(f"Done. Downloaded: {downloaded}")
    return downloaded


def main() -> int:
    args = parse_args()
    staging_dir = Path(args.staging_dir).resolve()
    inbox_root = normalize_dropbox_path(args.dropbox_root)
    archive_root = normalize_dropbox_path(args.archive_root)

    sync_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=inbox_root,
        archive_root=archive_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
