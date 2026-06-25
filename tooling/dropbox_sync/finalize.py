"""Helpers for the Dropbox finalization phase.

This module owns the second workflow phase: compare download and ingest
manifests, fail loudly on drift, and move accepted files to archive while
moving rejected files to quarantine.
"""

from pathlib import Path, PurePosixPath

from .api import move_remote_file
from .auth import require_access_token
from .manifests import read_manifest_file
from .paths import (
    archive_destination,
    quarantine_destination,
    validate_target_root,
)


def finalize_dropbox_inbox(
    download_manifest_file: Path,
    ingest_results_file: Path,
    inbox_root: PurePosixPath,
    archive_root: PurePosixPath,
    quarantine_root: PurePosixPath,
) -> int:
    """Move accepted files to archive and rejected ones to quarantine."""
    validate_target_root("Archive", inbox_root, archive_root)
    validate_target_root("Quarantine", inbox_root, quarantine_root)

    if archive_root == quarantine_root:
        raise ValueError("Archive and quarantine paths must be different")

    download_entries = read_manifest_file(download_manifest_file)
    ingest_results = read_manifest_file(ingest_results_file)
    if not download_entries or not ingest_results:
        print("No Dropbox files to finalize")
        return 0

    download_by_staging_path = {
        entry["staging_path"]: entry
        for entry in download_entries
        if "staging_path" in entry
    }
    download_staging_paths = list(download_by_staging_path)

    known_statuses = {"ingested", "skipped"}
    unknown_statuses = sorted(
        {
            result.get("status", "")
            for result in ingest_results
            if result.get("status") not in known_statuses
        }
    )
    if unknown_statuses:
        raise RuntimeError(
            "Unsupported ingest result statuses in finalize step: "
            + ", ".join(unknown_statuses)
        )

    result_source_paths = [result["source_file"] for result in ingest_results]
    unmatched_results = sorted(
        path for path in result_source_paths if path not in download_by_staging_path
    )
    unmatched_downloads = sorted(
        path for path in download_staging_paths if path not in set(result_source_paths)
    )

    if unmatched_results or unmatched_downloads:
        mismatch_parts = []
        if unmatched_results:
            mismatch_parts.append(
                "ingest results without matching downloads: "
                + ", ".join(unmatched_results)
            )
        if unmatched_downloads:
            mismatch_parts.append(
                "downloads without matching ingest results: "
                + ", ".join(unmatched_downloads)
            )
        raise RuntimeError(
            "Manifest mismatch during Dropbox finalization: "
            + " | ".join(mismatch_parts)
        )

    token = require_access_token()

    archived = 0
    quarantined = 0
    for result in ingest_results:
        download_entry = download_by_staging_path[result["source_file"]]

        source_path = download_entry["source_path"]
        if result["status"] == "ingested":
            destination_path = archive_destination(
                source_path, inbox_root, archive_root
            )
            move_remote_file(token, source_path, destination_path)
            archived += 1
            print(f"Archived {source_path} -> {destination_path.as_posix()}")
            continue

        destination_path = quarantine_destination(
            source_path, inbox_root, quarantine_root
        )
        move_remote_file(token, source_path, destination_path)
        quarantined += 1
        print(f"Quarantined {source_path} -> {destination_path.as_posix()}")

    print(f"Done. Archived: {archived}, Quarantined: {quarantined}")
    return archived + quarantined
