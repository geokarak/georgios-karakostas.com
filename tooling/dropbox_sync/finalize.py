"""Helpers for finalizing Dropbox inbox actions.

This module owns the final workflow phase: read the shared sync state file,
fail loudly if any entry is still missing an ingest outcome, remove accepted
files from the inbox, and move rejected files to quarantine.
"""

from pathlib import Path, PurePosixPath

from .api import move_dropbox_file, remove_dropbox_file
from .auth import require_access_token
from .paths import quarantine_destination, validate_target_root
from .state import read_state_file, validate_state_entries


def finalize_dropbox_inbox_actions(
    state_file: Path,
    inbox_root: PurePosixPath,
    quarantine_root: PurePosixPath,
) -> int:
    """Finalize Dropbox inbox actions from the shared sync state.

    Rules:
    - `ingested` -> remove the original Dropbox file from the inbox
    - `skipped` -> move the original Dropbox file to quarantine
    - missing or unknown status -> fail instead of guessing
    """
    validate_target_root("Quarantine", inbox_root, quarantine_root)

    state_entries = read_state_file(state_file)
    if not state_entries:
        print("No Dropbox actions to finalize")
        return 0

    validate_state_entries(state_entries)

    known_statuses = {"ingested", "skipped"}
    missing_statuses = [
        entry["source_file"] for entry in state_entries if "status" not in entry
    ]
    if missing_statuses:
        raise RuntimeError(
            "Dropbox sync state is missing ingest results for: "
            + ", ".join(sorted(missing_statuses))
        )

    unknown_statuses = sorted(
        {
            entry.get("status", "")
            for entry in state_entries
            if "status" in entry and entry.get("status") not in known_statuses
        }
    )
    if unknown_statuses:
        raise RuntimeError(
            "Dropbox sync state contains unsupported statuses: "
            + ", ".join(unknown_statuses)
        )

    access_token = require_access_token()

    imported_successfully = 0
    quarantined = 0
    for state_entry in state_entries:
        dropbox_source_path = state_entry["source_path"]
        if state_entry["status"] == "ingested":
            remove_dropbox_file(access_token, dropbox_source_path)
            imported_successfully += 1
            print(f"Removed from inbox {dropbox_source_path}")
            continue

        destination_path = quarantine_destination(
            dropbox_source_path, inbox_root, quarantine_root
        )
        move_dropbox_file(access_token, dropbox_source_path, destination_path)
        quarantined += 1
        print(f"Quarantined {dropbox_source_path} -> {destination_path.as_posix()}")

    print(
        f"Done. Imported successfully: {imported_successfully}, Quarantined: {quarantined}"
    )
    return imported_successfully + quarantined
