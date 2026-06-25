"""Helpers for reading and writing Dropbox sync manifests.

These manifests let different workflow phases pass structured file decisions to
one another without re-deriving state from scratch.
"""

import json
from pathlib import Path


def write_manifest_file(manifest_file: Path, entries: list[dict[str, str]]) -> None:
    """Write a JSON manifest file with one entry per tracked file."""
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def read_manifest_file(manifest_file: Path) -> list[dict[str, str]]:
    """Read a JSON manifest file and return its list payload."""
    if not manifest_file.exists():
        return []

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Invalid archive manifest format: {manifest_file}")
    return payload
