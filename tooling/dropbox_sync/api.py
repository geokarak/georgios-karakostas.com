"""Helpers for Dropbox HTTP requests and file operations.

This module owns the low-level communication with Dropbox: JSON API calls,
folder creation, listing remote files, downloading file contents, and moving
files between Dropbox folders.
"""

import json
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .paths import is_supported_image

API_BASE_URL = "https://api.dropboxapi.com/2"
CONTENT_BASE_URL = "https://content.dropboxapi.com/2"


def read_error_payload(error: HTTPError) -> str:
    """Read a helpful error message from a failed Dropbox HTTP response."""
    body = error.read().decode("utf-8", errors="replace")
    if body:
        return body
    return str(error)


def dropbox_api_json(token: str, endpoint: str, payload: dict) -> dict:
    """Send one Dropbox JSON API request and return the parsed response."""
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


def create_remote_folder(token: str, folder: PurePosixPath) -> None:
    """Create one Dropbox folder, ignoring already-exists conflicts."""
    try:
        dropbox_api_json(
            token,
            "files/create_folder_v2",
            {"path": folder.as_posix(), "autorename": False},
        )
    except RuntimeError as error:
        if "conflict" not in str(error):
            raise


def ensure_remote_folder(token: str, folder: PurePosixPath) -> None:
    """Create a Dropbox folder and its missing parents when needed."""
    if folder in {PurePosixPath("/"), PurePosixPath(".")}:
        return

    parents = [
        parent for parent in reversed(folder.parents) if parent != PurePosixPath("/")
    ]
    for parent in parents:
        create_remote_folder(token, parent)
    create_remote_folder(token, folder)


def list_remote_images(token: str, inbox_root: PurePosixPath) -> list[dict]:
    """List supported image files under a Dropbox inbox root."""
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
    """Download one Dropbox file into a local destination path."""
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
    """Move one Dropbox file into another Dropbox folder."""
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
