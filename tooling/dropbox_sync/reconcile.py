"""Helpers for the Dropbox reconcile phase.

This module owns the second workflow phase: compare download and ingest
manifests, fail loudly on drift, remove accepted files from the inbox, and move
rejected files to quarantine.

The key idea is that reconcile never inspects the staged directory directly.
Instead, it compares:

- the download manifest: Dropbox inbox path -> staged file path
- the ingest results manifest: staged file path -> ingest status

Joining those two manifests by staged file path tells reconcile which original
Dropbox file each ingest result belongs to.

The outcome rules are simple:

- if a staged file was `ingested`, remove the original Dropbox file from the inbox
- if a staged file was `skipped`, move the original Dropbox file to quarantine
- if the manifests do not line up, stop instead of guessing
"""

from pathlib import Path, PurePosixPath

from .api import move_dropbox_file, remove_dropbox_file
from .auth import require_access_token
from .manifests import read_manifest_file
from .paths import quarantine_destination, validate_target_root


def reconcile_dropbox_inbox(
    download_manifest_file: Path,
    ingest_results_file: Path,
    inbox_root: PurePosixPath,
    quarantine_root: PurePosixPath,
) -> int:
    """Apply ingest results back to the original Dropbox inbox files.

    Rules:
    - `ingested` -> remove the original Dropbox file from the inbox
    - `skipped` -> move the original Dropbox file to quarantine
    - manifest mismatch -> fail instead of guessing
    """
    validate_target_root("Quarantine", inbox_root, quarantine_root)

    download_entries = read_manifest_file(download_manifest_file)
    ingest_results = read_manifest_file(ingest_results_file)
    if not download_entries or not ingest_results:
        print("No Dropbox files to reconcile")
        return 0

    # Build one lookup keyed by staged file path. This is the join point between
    # the download phase and the ingest results phase.
    download_entry_by_staging_path = {
        download_entry["staging_path"]: download_entry
        for download_entry in download_entries
        if "staging_path" in download_entry
    }
    staged_file_paths = list(download_entry_by_staging_path)

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
            "Unsupported ingest result statuses in reconcile step: "
            + ", ".join(unknown_statuses)
        )

    result_staged_file_paths = [
        ingest_result["source_file"] for ingest_result in ingest_results
    ]
    unmatched_results = sorted(
        path
        for path in result_staged_file_paths
        if path not in download_entry_by_staging_path
    )
    unmatched_downloads = sorted(
        path for path in staged_file_paths if path not in set(result_staged_file_paths)
    )

    if unmatched_results or unmatched_downloads:
        # Reconcile only trusts explicit manifest agreement. If either side talks
        # about a staged file the other side does not know, we stop instead of
        # guessing which Dropbox file should be changed.
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
            "Manifest mismatch during Dropbox reconcile step: "
            + " | ".join(mismatch_parts)
        )

    access_token = require_access_token()

    imported_successfully = 0
    quarantined = 0
    for ingest_result in ingest_results:
        # `ingest_photos` reports results using the local staged file path it read
        # from. We use that path to recover the original Dropbox inbox file.
        download_entry = download_entry_by_staging_path[ingest_result["source_file"]]

        dropbox_source_path = download_entry["source_path"]
        if ingest_result["status"] == "ingested":
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
