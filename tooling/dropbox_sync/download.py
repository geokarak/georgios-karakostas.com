"""Helpers for the Dropbox download phase.

This module owns the first workflow phase: list Dropbox inbox files, download
them locally, and write one state file that tracks each Dropbox file through the
rest of the workflow.
"""

from pathlib import Path, PurePosixPath

from .api import download_dropbox_file, list_dropbox_images
from .auth import require_access_token
from .paths import relative_dropbox_path
from .state import write_state_file


def download_dropbox_inbox(
    staging_dir: Path,
    inbox_root: PurePosixPath,
    state_file: Path,
) -> int:
    """Download inbox files and seed the shared Dropbox sync state file."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    access_token = require_access_token()
    dropbox_files = list_dropbox_images(access_token, inbox_root)

    if not dropbox_files:
        write_state_file(state_file, [])
        print(f"No Dropbox images found in {inbox_root.as_posix()}")
        return 0

    downloaded = 0
    state_entries = []
    for dropbox_file in dropbox_files:
        dropbox_source_path = dropbox_file["path_display"]
        relative_path = relative_dropbox_path(dropbox_source_path, inbox_root)
        source_file = staging_dir.joinpath(*relative_path.parts)

        download_dropbox_file(access_token, dropbox_source_path, source_file)
        state_entries.append(
            {
                "source_path": dropbox_source_path,
                "source_file": str(source_file.resolve()),
            }
        )

        downloaded += 1
        print(f"Staged {dropbox_source_path} -> {source_file}")

    write_state_file(state_file, state_entries)
    print(f"Wrote Dropbox sync state -> {state_file}")

    print(f"Done. Downloaded: {downloaded}")
    return downloaded
