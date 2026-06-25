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

    # Step 1: decide which phase of the Dropbox workflow we are running.
    #
    # This script has two separate jobs:
    # - `download`: fetch files from the Dropbox inbox into a local staging folder
    # - `reconcile`: remove accepted files from the inbox and quarantine rejected files
    #
    # The staging folder sits in the middle of those two jobs. Dropbox files are
    # downloaded there first, then `tooling.ingest_photos` reads those local
    # staged files, and only after that do we change Dropbox.
    #
    # Keeping these phases separate makes the overall workflow safer because the
    # Dropbox inbox change only happens after ingest has decided whether each
    # staged file was accepted or rejected.
    if args.command == "download":
        # Step 2: resolve the download inputs.
        #
        # `staging_dir` is the temporary local folder that will receive the files.
        # `inbox_root` is the Dropbox folder we scan for new uploads.
        # `manifest_file` is the JSON bridge between Dropbox and local ingest:
        # it records which Dropbox source file produced which local staged file.
        staging_dir = Path(args.staging_dir).resolve()
        inbox_root = path_helpers.normalize_dropbox_path(args.dropbox_root)
        manifest_file = Path(args.manifest).resolve()

        # Step 3: run the download phase.
        #
        # This only stages files locally and writes the download manifest. It
        # does not decide remove-from-inbox vs quarantine yet because ingest has
        # not classified the staged files at this point.
        download_helpers.download_dropbox_inbox(
            staging_dir=staging_dir,
            inbox_root=inbox_root,
            manifest_file=manifest_file,
        )
        return 0

    if args.command == "reconcile":
        # Step 4: resolve the manifest paths and Dropbox target folders for the
        # reconcile phase.
        #
        # By the time we reach this branch, ingest has already read the staged
        # files and written its own results manifest. Together, the two manifest
        # files tell us:
        # - which Dropbox inbox file became which staged file
        # - which staged files were ingested vs skipped
        #
        # That lets us send good files out of the inbox and send bad ones to
        # quarantine instead of treating them all the same.
        download_manifest_file = Path(args.download_manifest).resolve()
        ingest_results_file = Path(args.ingest_results).resolve()
        inbox_root = path_helpers.normalize_dropbox_path(args.dropbox_root)
        quarantine_root = path_helpers.normalize_dropbox_path(args.quarantine_root)

        # Step 5: run the reconcile phase.
        #
        # This reads:
        # - the download manifest, which maps Dropbox inbox files to local staged
        #   files
        # - the ingest results manifest, which says whether each staged file was
        #   ingested or skipped
        #
        # With both pieces together, the workflow can now apply the ingest
        # decision back to the original Dropbox file.
        reconcile_helpers.reconcile_dropbox_inbox(
            download_manifest_file=download_manifest_file,
            ingest_results_file=ingest_results_file,
            inbox_root=inbox_root,
            quarantine_root=quarantine_root,
        )
        return 0

    # This is a fallback return. In normal use we should never reach it because
    # argparse requires one of the known commands above.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
