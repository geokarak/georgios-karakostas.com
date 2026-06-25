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
        description="Download Dropbox photos for ingest, then archive them later.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser(
        "download",
        help="Download Dropbox inbox files into a local staging directory.",
    )
    download_parser.add_argument(
        "--staging-dir", required=True, help="Local staging directory"
    )
    download_parser.add_argument(
        "--dropbox-root",
        required=True,
        help="Dropbox inbox directory, for example /site-photo-inbox",
    )
    download_parser.add_argument(
        "--archive-root",
        default="/site-photo-archive",
        help="Dropbox archive directory for processed files",
    )
    download_parser.add_argument(
        "--manifest",
        required=True,
        help="JSON file that records which Dropbox files should be archived later",
    )

    archive_parser = subparsers.add_parser(
        "archive",
        help="Archive Dropbox files listed in a manifest created earlier.",
    )
    archive_parser.add_argument(
        "--manifest",
        required=True,
        help="JSON file created by the download step",
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


def validate_archive_root(
    inbox_root: PurePosixPath, archive_root: PurePosixPath
) -> None:
    if archive_root == inbox_root or archive_root.is_relative_to(inbox_root):
        raise ValueError("Archive path must live outside the Dropbox inbox path")


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


def write_archive_manifest(manifest_file: Path, entries: list[dict[str, str]]) -> None:
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def read_archive_manifest(manifest_file: Path) -> list[dict[str, str]]:
    if not manifest_file.exists():
        return []

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Invalid archive manifest format: {manifest_file}")
    return payload


def download_dropbox_inbox(
    staging_dir: Path,
    inbox_root: PurePosixPath,
    archive_root: PurePosixPath,
    manifest_file: Path,
) -> int:
    # The archive folder must sit outside the inbox so files do not get picked up
    # again on the next Dropbox scan.
    validate_archive_root(inbox_root, archive_root)

    staging_dir.mkdir(parents=True, exist_ok=True)

    token = require_access_token()
    files = list_remote_images(token, inbox_root)

    if not files:
        write_archive_manifest(manifest_file, [])
        print(f"No Dropbox images found in {inbox_root.as_posix()}")
        return 0

    downloaded = 0
    manifest_entries = []
    for entry in files:
        source_path = entry["path_display"]
        relative_path = relative_dropbox_path(source_path, inbox_root)
        destination = staging_dir.joinpath(*relative_path.parts)
        archived_path = archive_destination(source_path, inbox_root, archive_root)

        # Phase 1 only stages files locally and records where they should be
        # archived later. The actual Dropbox move is delayed until the whole
        # workflow has succeeded.
        download_remote_file(token, source_path, destination)
        manifest_entries.append(
            {
                "source_path": source_path,
                "archive_path": archived_path.as_posix(),
            }
        )

        downloaded += 1
        print(f"Staged {source_path} -> {destination}")

    write_archive_manifest(manifest_file, manifest_entries)
    print(f"Wrote archive manifest -> {manifest_file}")

    print(f"Done. Downloaded: {downloaded}")
    return downloaded


def archive_dropbox_inbox(manifest_file: Path) -> int:
    manifest_entries = read_archive_manifest(manifest_file)
    if not manifest_entries:
        print(f"No Dropbox files to archive from {manifest_file}")
        return 0

    token = require_access_token()

    archived = 0
    for entry in manifest_entries:
        source_path = entry["source_path"]
        archive_path = normalize_dropbox_path(entry["archive_path"])

        move_remote_file(token, source_path, archive_path)

        archived += 1
        print(f"Archived {source_path} -> {archive_path.as_posix()}")

    print(f"Done. Archived: {archived}")
    return archived


def main() -> int:
    args = parse_args()

    # Step 1: decide which phase of the Dropbox workflow we are running.
    #
    # This script has two separate jobs:
    # - `download`: fetch files from the Dropbox inbox into a local staging folder
    # - `archive`: move already-processed Dropbox files into the archive folder
    #
    # Keeping these phases separate makes the overall workflow safer because the
    # Dropbox move only happens after the rest of the pipeline has succeeded.
    if args.command == "download":
        # Step 2: resolve the download inputs.
        #
        # `staging_dir` is the temporary local folder that will receive the files.
        # `inbox_root` is the Dropbox folder we scan for new uploads.
        # `archive_root` is where those files should eventually be moved.
        # `manifest_file` is the small JSON file that remembers what should be
        # archived later if the workflow reaches the end successfully.
        staging_dir = Path(args.staging_dir).resolve()
        inbox_root = normalize_dropbox_path(args.dropbox_root)
        archive_root = normalize_dropbox_path(args.archive_root)
        manifest_file = Path(args.manifest).resolve()

        # Step 3: run the download phase.
        #
        # This only stages files locally and writes the manifest. It does not
        # archive anything in Dropbox yet.
        download_dropbox_inbox(
            staging_dir=staging_dir,
            inbox_root=inbox_root,
            archive_root=archive_root,
            manifest_file=manifest_file,
        )
        return 0

    if args.command == "archive":
        # Step 4: resolve the manifest path for the archive phase.
        #
        # By the time we reach this branch, the rest of the workflow has already
        # completed successfully, so it is now safe to move the processed Dropbox
        # files out of the inbox.
        manifest_file = Path(args.manifest).resolve()

        # Step 5: run the archive phase.
        #
        # This reads the manifest created earlier and moves each recorded Dropbox
        # file into the archive folder.
        archive_dropbox_inbox(manifest_file)
        return 0

    # This is a fallback return. In normal use we should never reach it because
    # argparse requires one of the known commands above.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
