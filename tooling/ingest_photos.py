#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from tooling.dropbox_sync.state import (
    read_state_file,
    validate_state_entries,
    write_state_file,
)
from tooling.photo_ingest import exif as exif_helpers
from tooling.photo_ingest import images as image_helpers
from tooling.photo_ingest import pages as page_helpers
from tooling.photo_ingest import source as source_helpers
from tooling.photo_ingest.transaction import ingest_photo_atomically


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest photos from an inbox folder into the site content directory.",
    )
    parser.add_argument("--src", default="inbox", help="Source inbox directory")
    parser.add_argument(
        "--dest",
        default="content/images/photos",
        help="Destination photos directory",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Mark ingested photos as unpublished",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing files",
    )
    parser.add_argument(
        "--result-manifest",
        default=None,
        help=(
            "Optional JSON file that records ingest outcomes. "
            "When the file already contains Dropbox sync state entries, "
            "statuses are merged into that file instead of replacing it."
        ),
    )
    return parser.parse_args()


def write_result_manifest(
    manifest_file: Path | None, entries: list[dict[str, str]]
) -> None:
    """Write ingest results or merge them into Dropbox sync state."""
    if manifest_file is None:
        return

    existing_entries = read_state_file(manifest_file)
    if any(
        isinstance(entry, dict) and "source_path" in entry for entry in existing_entries
    ):
        validate_state_entries(existing_entries)
        ingest_entry_by_source_file = {entry["source_file"]: entry for entry in entries}
        unexpected_results = sorted(
            source_file
            for source_file in ingest_entry_by_source_file
            if source_file not in {entry["source_file"] for entry in existing_entries}
        )
        if unexpected_results:
            raise RuntimeError(
                "Ingest results do not match the existing Dropbox sync state: "
                + ", ".join(unexpected_results)
            )

        merged_entries = []
        for existing_entry in existing_entries:
            source_file = existing_entry["source_file"]
            ingest_entry = ingest_entry_by_source_file.get(source_file)
            if ingest_entry is None:
                merged_entries.append(existing_entry)
                continue

            merged_entry = {
                "source_path": existing_entry["source_path"],
                "source_file": source_file,
                "status": ingest_entry["status"],
            }
            reason = ingest_entry.get("reason")
            if reason:
                merged_entry["reason"] = reason
            merged_entries.append(merged_entry)

        write_state_file(manifest_file, merged_entries)
        return

    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    result_manifest = (
        Path(args.result_manifest).resolve() if args.result_manifest else None
    )
    ingest_results: list[dict[str, str]] = []

    # Resolve repository and workflow paths.
    project_root = Path(__file__).resolve().parents[1]
    src_dir = Path(args.src).resolve()
    dest_dir = Path(args.dest).resolve()

    # Validate source input.
    if not src_dir.exists():
        print(f"Source directory does not exist: {src_dir}")
        return 1

    # Validate required external dependency.
    try:
        exiftool_path = exif_helpers.require_exiftool()
    except RuntimeError as error:
        print(error)
        return 1

    # Discover ingest candidates.
    images = source_helpers.source_images(src_dir)
    if not images:
        write_result_manifest(result_manifest, ingest_results)
        print(f"No images found in {src_dir}")
        return 0

    # Read EXIF capture timestamps in batch.
    detected_datetimes = exif_helpers.exif_datetimes(images, exiftool_path)

    # Track ingest outcomes.
    ingested = 0
    skipped = 0

    # Prepare destination root unless dry-run mode is active.
    if not args.dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    # Process photos one by one.
    for source_file in images:
        # Read category from the source path.
        category = source_helpers.get_category(source_file, src_dir)
        if not category:
            ingest_results.append(
                {
                    "source_file": str(source_file.resolve()),
                    "status": "skipped",
                    "reason": "missing-category",
                }
            )
            print(
                f"Skipping {source_file}: not inside a category folder. Place photos in category subfolders."
            )
            skipped += 1
            continue

        # Validate that EXIF capture time is available.
        detected_dt = detected_datetimes.get(source_file)
        if not detected_dt:
            ingest_results.append(
                {
                    "source_file": str(source_file.resolve()),
                    "status": "skipped",
                    "reason": "missing-exif-datetimeoriginal",
                }
            )
            print(
                "Skipping "
                f"{source_file}: missing EXIF DateTimeOriginal. "
                "This project requires capture dates in EXIF metadata."
            )
            skipped += 1
            continue

        # Plan output files and metadata payload.
        category_dir = dest_dir / category
        photo_id = source_helpers.unique_id(
            category_dir,
            detected_dt,
            image_helpers.derivative_paths,
        )

        metadata_file = category_dir / f"{photo_id}.json"
        display_file, thumbnail_file = image_helpers.derivative_paths(
            category_dir, photo_id
        )

        metadata = {
            "id": photo_id,
            "category": category,
            "DateTimeOriginal": detected_dt.strftime("%Y:%m:%d %H:%M:%S"),
            "location": "",
            "caption": "",
            "published": not args.draft,
            "display_filename": display_file.name,
            "thumbnail_filename": thumbnail_file.name,
        }

        # Preview planned outputs in dry-run mode.
        if args.dry_run:
            print(f"[DRY RUN] display -> {display_file}")
            print(f"[DRY RUN] thumbnail -> {thumbnail_file}")
            print(f"[DRY RUN] metadata -> {metadata_file}")
            page_helpers.ensure_gallery_page(category, project_root, dry_run=True)
            ingested += 1
            continue

        # Commit outputs atomically for this source image.
        ingest_photo_atomically(
            source_file=source_file,
            category=category,
            project_root=project_root,
            category_dir=category_dir,
            metadata_file=metadata_file,
            display_file=display_file,
            thumbnail_file=thumbnail_file,
            metadata=metadata,
        )

        # Record successful ingest result.
        ingested += 1
        ingest_results.append(
            {
                "source_file": str(source_file.resolve()),
                "status": "ingested",
            }
        )
        print(
            f"Ingested {source_file.name} -> {display_file.relative_to(dest_dir.parent)}"
        )

    # Persist ingest results and print final summary.
    write_result_manifest(result_manifest, ingest_results)
    print(f"Done. Ingested: {ingested}, Skipped: {skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
