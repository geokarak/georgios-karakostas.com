#!/usr/bin/env python3

import argparse
from pathlib import Path

from photo_ingest import exif as exif_helpers
from photo_ingest import images as image_helpers
from photo_ingest import pages as page_helpers
from photo_ingest import results as result_helpers
from photo_ingest import source as source_helpers
from photo_ingest.transaction import ingest_photo_atomically


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
        "--category",
        default=None,
        help="Fallback category for images directly under --src",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy files instead of moving them (default is move)",
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
        help="Optional JSON file that records which source files were ingested or skipped",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result_manifest = (
        Path(args.result_manifest).resolve() if args.result_manifest else None
    )
    ingest_results: list[dict[str, str]] = []

    # Step 1: figure out the main folders we are going to work with.
    #
    # `project_root` is the root of this repository.
    # `src_dir` is the inbox folder that contains the uploaded photos.
    # `dest_dir` is where the generated website photo files will be written.
    #
    # We convert the input paths to absolute paths up front so the rest of the
    # script does not have to guess where files live.
    project_root = Path(__file__).resolve().parents[1]
    src_dir = Path(args.src).resolve()
    dest_dir = Path(args.dest).resolve()

    # Step 2: make sure the source inbox actually exists.
    #
    # If the user points to a folder that is missing, there is no point in
    # continuing. We stop immediately and print a clear message instead of
    # failing later with a more confusing error.
    if not src_dir.exists():
        print(f"Source directory does not exist: {src_dir}")
        return 1

    # Step 3: make sure `exiftool` is installed.
    #
    # This project uses the capture date stored in the photo metadata. That date
    # is important because it becomes part of the generated JSON metadata and it
    # also helps build the final photo id. We rely on `exiftool` to read that
    # metadata, so the whole ingest process depends on it being available.
    try:
        exiftool_path = exif_helpers.require_exiftool()
    except RuntimeError as error:
        print(error)
        return 1

    # Step 4: collect the photos that are candidates for ingest.
    #
    # `source_images()` walks through the inbox and keeps only the file types we
    # know how to process, such as JPG, PNG, and WebP.
    #
    # An empty inbox is not an error. It simply means there is nothing new to do,
    # so we exit cleanly.
    images = source_helpers.source_images(src_dir)
    if not images:
        result_helpers.write_result_manifest(result_manifest, ingest_results)
        print(f"No images found in {src_dir}")
        return 0

    # Step 4a: read the EXIF capture dates for the full batch in one go.
    #
    # We still process photos one by one below, but asking `exiftool` for every
    # single file would repeat the same external process startup over and over.
    #
    # Instead, we ask for all candidate files in one batch here and keep the
    # results in memory. The rest of the pipeline can then reuse those parsed
    # dates without paying that startup cost again.
    detected_datetimes = exif_helpers.exif_datetimes(images, exiftool_path)

    # Step 5: prepare some simple counters for the final summary.
    #
    # `copied` counts photos that were successfully processed.
    # `skipped` counts photos that we deliberately ignored, for example because
    # they did not have enough metadata or we could not work out a category.
    copied = 0
    skipped = 0

    # Step 6: ensure the destination root exists before real work starts.
    #
    # We only do this in normal mode. In `--dry-run` mode, the whole point is to
    # preview what would happen without changing the filesystem.
    #
    # Individual category folders such as `content/images/photos/iphone/` are
    # still created later only if we actually ingest a photo into them.
    if not args.dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    # Step 7: process each discovered source image one by one.
    #
    # We go photo-by-photo so each file gets its own category lookup, metadata
    # lookup, generated filenames, and final success or skip message.
    for source_file in images:
        # Step 7a: decide which gallery category this photo belongs to.
        #
        # Normally the category comes from the inbox folder name. For example:
        # `inbox/street/picture.jpg` becomes category `street`.
        #
        # If the file sits directly under the source root instead of inside a
        # category folder, we can fall back to `--category`.
        #
        # If we still cannot decide on a category, we skip the file because the
        # site would not know which gallery page should show it.
        category = source_helpers.infer_category(source_file, src_dir, args.category)
        if not category:
            ingest_results.append(
                {
                    "source_file": str(source_file.resolve()),
                    "status": "skipped",
                    "reason": "missing-category",
                }
            )
            print(
                "Skipping "
                f"{source_file}: no category found. Use subfolders or pass --category."
            )
            skipped += 1
            continue

        # Step 7b: read the capture date from the already-loaded EXIF results.
        #
        # The site expects every imported photo to have a real capture timestamp.
        # We use it for the `DateTimeOriginal` field in the JSON metadata, and it
        # also feeds into the generated photo id.
        #
        # If a photo does not have a supported EXIF capture date, we skip it
        # instead of inventing one. That keeps the stored metadata trustworthy.
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

        # Step 7c: decide the final output paths and build the metadata payload.
        #
        # At this point we know enough to plan the import:
        # - which category folder the photo belongs to
        # - the unique id that will identify this photo on disk
        # - the final display image path
        # - the final thumbnail image path
        # - the JSON metadata file path
        #
        # We also create the metadata dictionary that will later be written to
        # disk. This is the record the site reads when building the photo pages.
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

        # Step 7d: handle `--dry-run` mode.
        #
        # In dry-run mode we do not write, move, or delete anything. We only show
        # which files would be created if this were a real ingest.
        #
        # This is helpful when you want to sanity-check a batch before letting the
        # script actually change the repository contents.
        if args.dry_run:
            print(f"[DRY RUN] display -> {display_file}")
            print(f"[DRY RUN] thumbnail -> {thumbnail_file}")
            print(f"[DRY RUN] metadata -> {metadata_file}")
            page_helpers.ensure_gallery_page(category, project_root, dry_run=True)
            copied += 1
            continue

        # Step 7e: run the real import.
        #
        # This is the point where files are actually created.
        #
        # We hand off to `ingest_photo_atomically()` so the related outputs for
        # one photo stay in sync. That helper stages the generated files first and
        # only commits them when the full set is ready. The source file is removed
        # only after the import has succeeded.
        ingest_photo_atomically(
            source_file=source_file,
            category=category,
            project_root=project_root,
            category_dir=category_dir,
            metadata_file=metadata_file,
            display_file=display_file,
            thumbnail_file=thumbnail_file,
            metadata=metadata,
            copy_source=args.copy,
        )

        # Step 7f: record and report success for this one photo.
        #
        # This gives immediate feedback during larger imports and makes it easier
        # to see which file was processed most recently if something goes wrong on
        # a later image.
        copied += 1
        ingest_results.append(
            {
                "source_file": str(source_file.resolve()),
                "status": "ingested",
            }
        )
        print(
            f"Ingested {source_file.name} -> {display_file.relative_to(dest_dir.parent)}"
        )

    # Step 8: print a final summary for the whole batch.
    #
    # This gives the user one simple overview at the end: how many files were
    # ingested successfully and how many were skipped.
    #
    # If `--copy` was used, we also print a reminder that keeping the original
    # inbox files around makes it easier to import the same photo again by
    # accident on the next run.
    result_helpers.write_result_manifest(result_manifest, ingest_results)
    print(f"Done. Ingested: {copied}, Skipped: {skipped}")
    if not args.dry_run and args.copy:
        print("Tip: avoid --copy to prevent re-ingesting the same inbox files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
