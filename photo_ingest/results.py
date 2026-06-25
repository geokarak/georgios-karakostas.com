"""Helpers for writing ingest result records.

This module keeps the small manifest-writing logic separate from the main ingest
flow so the orchestration code can stay focused on decision-making.
"""

import json
from pathlib import Path


def write_result_manifest(
    manifest_file: Path | None, entries: list[dict[str, str]]
) -> None:
    """Write the ingest result manifest when one was requested."""
    if manifest_file is None:
        return

    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
