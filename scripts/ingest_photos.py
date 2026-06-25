#!/usr/bin/env python3

import argparse
import datetime as dt
import io
import json
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DISPLAY_TITLE_EXCEPTIONS = {"iphone": "iPhone"}
DISPLAY_MAX_EDGE = 2200
THUMBNAIL_MAX_EDGE = 900
DERIVATIVE_FORMAT = "WEBP"
DERIVATIVE_EXTENSION = ".webp"
DERIVATIVE_QUALITY = 82
EXIFTOOL_DATE_TAGS = ("ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate")


def srgb_profile_bytes() -> bytes:
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    return profile.tobytes()


def convert_to_srgb(
    image: Image.Image, icc_profile: bytes | None
) -> tuple[Image.Image, bytes]:
    srgb_bytes = srgb_profile_bytes()
    if not icc_profile:
        return image, srgb_bytes

    try:
        source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        target_profile = ImageCms.ImageCmsProfile(io.BytesIO(srgb_bytes))
        if image.mode == "RGBA":
            rgb_image = ImageCms.profileToProfile(
                image.convert("RGB"),
                source_profile,
                target_profile,
                outputMode="RGB",
            )
            rgb_image.putalpha(image.getchannel("A"))
            return rgb_image, srgb_bytes

        converted = ImageCms.profileToProfile(
            image,
            source_profile,
            target_profile,
            outputMode=image.mode,
        )
        return converted, srgb_bytes
    except Exception:
        return image, icc_profile


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def generated_photo_id(captured_at: dt.datetime) -> str:
    return f"{captured_at.strftime('%Y-%m-%d-%H%M%S')}-{secrets.token_hex(4)}"


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
    return parser.parse_args()


def require_exiftool() -> str:
    exiftool_path = shutil.which("exiftool")
    if exiftool_path:
        return exiftool_path

    raise RuntimeError(
        "This project requires exiftool for photo ingestion. "
        "Install exiftool and try again."
    )


def parse_exiftool_datetime(value: str) -> dt.datetime | None:
    normalized = value.strip()
    if not normalized:
        return None

    for date_format in ("%Y:%m:%d %H:%M:%S",):
        try:
            return dt.datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return None


def exif_datetime(path: Path, exiftool_path: str) -> dt.datetime | None:
    try:
        result = subprocess.run(
            [
                exiftool_path,
                "-j",
                "-G1",
                *(f"-{tag}" for tag in EXIFTOOL_DATE_TAGS),
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    if not payload:
        return None

    metadata = payload[0]
    for tag in EXIFTOOL_DATE_TAGS:
        value = metadata.get(tag)
        if not value:
            continue
        parsed = parse_exiftool_datetime(value)
        if parsed:
            return parsed

    return None


def infer_category(
    source_file: Path, src_root: Path, fallback: str | None
) -> str | None:
    relative = source_file.relative_to(src_root)
    if len(relative.parts) > 1:
        return slugify(relative.parts[0])
    if fallback:
        return slugify(fallback)
    return None


def reserve_photo_id(
    category_dir: Path, photo_id: str, reserved_ids: set[str] | None = None
) -> bool:
    metadata_exists = (category_dir / f"{photo_id}.json").exists()
    display_file, thumbnail_file = derivative_paths(category_dir, photo_id)
    image_exists = display_file.exists() or thumbnail_file.exists()
    already_reserved = reserved_ids is not None and photo_id in reserved_ids
    return not metadata_exists and not image_exists and not already_reserved


def unique_id(
    category_dir: Path,
    captured_at: dt.datetime,
    reserved_ids: set[str] | None = None,
) -> str:
    while True:
        candidate = generated_photo_id(captured_at)
        if reserve_photo_id(category_dir, candidate, reserved_ids=reserved_ids):
            return candidate


def source_images(src_dir: Path) -> list[Path]:
    files = [
        path
        for path in src_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files)


def title_from_slug(slug: str) -> str:
    if slug in DISPLAY_TITLE_EXCEPTIONS:
        return DISPLAY_TITLE_EXCEPTIONS[slug]
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def gallery_page_path(category: str, project_root: Path) -> Path:
    return project_root / "content" / "pages" / f"{category}.md"


def gallery_page_content(category: str) -> str:
    title = title_from_slug(category)
    return f"title: {title}\nslug: {category}\ntemplate: gallery\n"


def ensure_gallery_page(category: str, project_root: Path, dry_run: bool) -> None:
    pages_dir = project_root / "content" / "pages"
    page_file = gallery_page_path(category, project_root)
    if page_file.exists():
        return

    page_content = gallery_page_content(category)

    if dry_run:
        print(f"[DRY RUN] page -> {page_file}")
        return

    pages_dir.mkdir(parents=True, exist_ok=True)
    page_file.write_text(page_content, encoding="utf-8")


def derivative_paths(category_dir: Path, photo_id: str) -> tuple[Path, Path]:
    display_file = category_dir / f"{photo_id}-display{DERIVATIVE_EXTENSION}"
    thumbnail_file = category_dir / f"{photo_id}-thumb{DERIVATIVE_EXTENSION}"
    return display_file, thumbnail_file


def save_web_derivative(
    source_file: Path, destination_file: Path, max_edge: int
) -> None:
    with Image.open(source_file) as image:
        icc_profile = image.info.get("icc_profile")
        rendered = ImageOps.exif_transpose(image)
        if rendered.mode not in {"RGB", "RGBA"}:
            rendered = rendered.convert("RGB")

        rendered, derivative_icc_profile = convert_to_srgb(rendered, icc_profile)

        rendered.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        save_options = {
            "format": DERIVATIVE_FORMAT,
            "quality": DERIVATIVE_QUALITY,
            "method": 6,
            "icc_profile": derivative_icc_profile,
        }
        if rendered.mode == "RGBA":
            save_options["lossless"] = False

        rendered.save(destination_file, **save_options)


def commit_staged_file(staged_file: Path, destination_file: Path) -> None:
    if destination_file.exists():
        raise FileExistsError(f"Destination already exists: {destination_file}")
    staged_file.replace(destination_file)


def ingest_photo_atomically(
    source_file: Path,
    category: str,
    project_root: Path,
    category_dir: Path,
    metadata_file: Path,
    display_file: Path,
    thumbnail_file: Path,
    metadata: dict[str, str | bool],
    copy_source: bool,
) -> None:
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".ingest-{metadata['id']}-", dir=category_dir.parent)
    )
    staged_category_dir = staging_root / category
    staged_display_file = staged_category_dir / display_file.name
    staged_thumbnail_file = staged_category_dir / thumbnail_file.name
    staged_metadata_file = staged_category_dir / metadata_file.name
    page_file = gallery_page_path(category, project_root)
    staged_page_file = staging_root / page_file.name
    should_create_page = not page_file.exists()
    committed_paths: list[Path] = []
    created_page = False

    try:
        staged_category_dir.mkdir(parents=True, exist_ok=True)
        save_web_derivative(source_file, staged_display_file, DISPLAY_MAX_EDGE)
        save_web_derivative(source_file, staged_thumbnail_file, THUMBNAIL_MAX_EDGE)
        staged_metadata_file.write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

        if should_create_page:
            staged_page_file.write_text(
                gallery_page_content(category), encoding="utf-8"
            )

        category_dir.mkdir(parents=True, exist_ok=True)
        commit_staged_file(staged_display_file, display_file)
        committed_paths.append(display_file)
        commit_staged_file(staged_thumbnail_file, thumbnail_file)
        committed_paths.append(thumbnail_file)
        commit_staged_file(staged_metadata_file, metadata_file)
        committed_paths.append(metadata_file)

        if should_create_page and not page_file.exists():
            page_file.parent.mkdir(parents=True, exist_ok=True)
            commit_staged_file(staged_page_file, page_file)
            created_page = True

        if not copy_source:
            source_file.unlink()
    except Exception:
        for committed_path in reversed(committed_paths):
            committed_path.unlink(missing_ok=True)
        if created_page:
            page_file.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


def main() -> int:
    args = parse_args()

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
        exiftool_path = require_exiftool()
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
    images = source_images(src_dir)
    if not images:
        print(f"No images found in {src_dir}")
        return 0

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
        category = infer_category(source_file, src_dir, args.category)
        if not category:
            print(
                "Skipping "
                f"{source_file}: no category found. Use subfolders or pass --category."
            )
            skipped += 1
            continue

        # Step 7b: read the capture date from the image metadata.
        #
        # The site expects every imported photo to have a real capture timestamp.
        # We use it for the `DateTimeOriginal` field in the JSON metadata, and it
        # also feeds into the generated photo id.
        #
        # If a photo does not have a supported EXIF capture date, we skip it
        # instead of inventing one. That keeps the stored metadata trustworthy.
        detected_dt = exif_datetime(source_file, exiftool_path)
        if not detected_dt:
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
        photo_id = unique_id(category_dir, detected_dt)

        metadata_file = category_dir / f"{photo_id}.json"
        display_file, thumbnail_file = derivative_paths(category_dir, photo_id)

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
            ensure_gallery_page(category, project_root, dry_run=True)
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
    print(f"Done. Ingested: {copied}, Skipped: {skipped}")
    if not args.dry_run and args.copy:
        print("Tip: avoid --copy to prevent re-ingesting the same inbox files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
