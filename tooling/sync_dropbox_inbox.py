#!/usr/bin/env python3

import argparse
from pathlib import Path

from tooling.dropbox_sync import download as download_helpers
from tooling.dropbox_sync import reconcile as reconcile_helpers
from tooling.dropbox_sync import paths as path_helpers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Dropbox photos for ingest, then reconcile the inbox later.",
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
        "--manifest",
        required=True,
        help="JSON file that records which Dropbox files were downloaded",
    )

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Remove accepted Dropbox files from the inbox and quarantine rejected ones.",
    )
    reconcile_parser.add_argument(
        "--download-manifest",
        required=True,
        help="JSON file created by the download step",
    )
    reconcile_parser.add_argument(
        "--ingest-results",
        required=True,
        help="JSON file created by the ingest step",
    )
    reconcile_parser.add_argument(
        "--dropbox-root",
        required=True,
        help="Dropbox inbox directory, for example /site-photo-inbox",
    )
    reconcile_parser.add_argument(
        "--quarantine-root",
        default="/site-photo-quarantine",
        help="Dropbox quarantine directory for rejected files",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Branch by workflow phase.
    if args.command == "download":
        # Resolve download paths.
        staging_dir = Path(args.staging_dir).resolve()
        inbox_root = path_helpers.normalize_dropbox_path(args.dropbox_root)
        manifest_file = Path(args.manifest).resolve()

        # Download Dropbox inbox files into local staging.
        download_helpers.download_dropbox_inbox(
            staging_dir=staging_dir,
            inbox_root=inbox_root,
            manifest_file=manifest_file,
        )
        return 0

    if args.command == "reconcile":
        # Resolve reconcile manifests and Dropbox targets.
        download_manifest_file = Path(args.download_manifest).resolve()
        ingest_results_file = Path(args.ingest_results).resolve()
        inbox_root = path_helpers.normalize_dropbox_path(args.dropbox_root)
        quarantine_root = path_helpers.normalize_dropbox_path(args.quarantine_root)

        # Apply ingest decisions back to Dropbox.
        reconcile_helpers.reconcile_dropbox_inbox(
            download_manifest_file=download_manifest_file,
            ingest_results_file=ingest_results_file,
            inbox_root=inbox_root,
            quarantine_root=quarantine_root,
        )
        return 0

    # Keep a defensive fallback return.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
