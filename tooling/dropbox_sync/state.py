"""Helpers for reading and writing Dropbox sync state.

The Dropbox photo workflow uses one JSON state file across all phases:

- download records the original Dropbox path and the local source file path
- ingest adds the final `status` for each processed file
- apply uses the final Dropbox action from that same file
"""

import json
from pathlib import Path

REQUIRED_STATE_FIELDS = ("source_path", "source_file")


def write_state_file(state_file: Path, entries: list[dict[str, str]]) -> None:
    """Write the Dropbox sync state file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def read_state_file(state_file: Path) -> list[dict[str, str]]:
    """Read the Dropbox sync state file and return its list payload."""
    if not state_file.exists():
        return []

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Invalid Dropbox sync state format: {state_file}")
    return payload


def validate_state_entries(entries: list[dict[str, str]]) -> None:
    """Reject Dropbox sync state entries that are missing required fields."""
    invalid_entries = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            invalid_entries.append(f"entry {index} is not an object")
            continue

        missing_fields = [
            field for field in REQUIRED_STATE_FIELDS if field not in entry
        ]
        if missing_fields:
            invalid_entries.append(
                f"entry {index} missing {', '.join(sorted(missing_fields))}"
            )

    if invalid_entries:
        raise RuntimeError("Invalid Dropbox sync state: " + " | ".join(invalid_entries))
