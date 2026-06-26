#!/usr/bin/env python3

import argparse
from pathlib import Path

from tooling.dropbox_sync import apply as apply_helpers
from tooling.dropbox_sync import download as download_helpers
from tooling.dropbox_sync import paths as path_helpers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Dropbox photos for ingest, then apply the results later.",
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
        "--state-file",
        required=True,
        help="JSON file that tracks Dropbox files through download, ingest, and apply",
    )

    apply_parser = subparsers.add_parser(
        "apply",
        help="Remove accepted Dropbox files from the inbox and quarantine rejected ones.",
    )
    apply_parser.add_argument(
        "--state-file",
        required=True,
        help="JSON file shared by the download, ingest, and apply steps",
    )
    apply_parser.add_argument(
        "--dropbox-root",
        required=True,
        help="Dropbox inbox directory, for example /site-photo-inbox",
    )
    apply_parser.add_argument(
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
        state_file = Path(args.state_file).resolve()

        # Download Dropbox inbox files into local staging and seed the sync state.
        download_helpers.download_dropbox_inbox(
            staging_dir=staging_dir,
            inbox_root=inbox_root,
            state_file=state_file,
        )
        return 0

    if args.command == "apply":
        # Resolve the shared sync state file and Dropbox targets.
        state_file = Path(args.state_file).resolve()
        inbox_root = path_helpers.normalize_dropbox_path(args.dropbox_root)
        quarantine_root = path_helpers.normalize_dropbox_path(args.quarantine_root)

        # Apply ingest decisions back to Dropbox.
        apply_helpers.apply_dropbox_inbox_actions(
            state_file=state_file,
            inbox_root=inbox_root,
            quarantine_root=quarantine_root,
        )
        return 0

    # Keep a defensive fallback return.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
