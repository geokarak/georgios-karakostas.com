"""Helpers for reading and writing Dropbox sync manifests.

These manifests let different workflow phases pass structured file decisions to
one another without re-deriving state from scratch.

The Dropbox sync pipeline uses two JSON manifests:

- the download manifest, written by `tooling.dropbox_sync.download`, records
  which Dropbox inbox file was downloaded to which local staged file path
- the ingest results manifest, written by `tooling.ingest_photos`, records what
  happened to each staged file path during ingest

The reconcile step joins those two manifests on the staged file path. That is
how it knows which original Dropbox file should be removed from the inbox or
moved to quarantine after ingest has finished.
"""

import json
from pathlib import Path


def write_manifest_file(manifest_file: Path, entries: list[dict[str, str]]) -> None:
    """Write one JSON manifest used to hand file state to a later step."""
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def read_manifest_file(manifest_file: Path) -> list[dict[str, str]]:
    """Read one JSON manifest file and return its list payload."""
    if not manifest_file.exists():
        return []

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Invalid Dropbox sync manifest format: {manifest_file}")
    return payload
