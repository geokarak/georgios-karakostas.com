#!/usr/bin/env python3

import argparse
import datetime as dt
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
EXIF_DATE_TAGS = (36867, 36868, 306)
DISPLAY_TITLE_EXCEPTIONS = {"iphone": "iPhone"}
DISPLAY_MAX_EDGE = 2200
THUMBNAIL_MAX_EDGE = 900
DERIVATIVE_FORMAT = "WEBP"
DERIVATIVE_EXTENSION = ".webp"
DERIVATIVE_QUALITY = 82


def srgb_profile_bytes() -> bytes:
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    return profile.tobytes()


def convert_to_srgb(image: Image.Image, icc_profile: bytes | None) -> tuple[Image.Image, bytes]:
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


def exif_datetime(path: Path) -> dt.datetime | None:
    try:
        with Image.open(path) as image:
            exif_data = image.getexif()
    except Exception:
        return None

    if not exif_data:
        return None

    for tag in EXIF_DATE_TAGS:
        value = exif_data.get(tag)
        if not value:
            continue
        try:
            return dt.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return None


def infer_category(source_file: Path, src_root: Path, fallback: str | None) -> str | None:
    relative = source_file.relative_to(src_root)
    if len(relative.parts) > 1:
        return slugify(relative.parts[0])
    if fallback:
        return slugify(fallback)
    return None


def unique_id(category_dir: Path, base_id: str) -> str:
    candidate = base_id
    counter = 2
    while True:
        metadata_exists = (category_dir / f"{candidate}.json").exists()
        display_file, thumbnail_file = derivative_paths(category_dir, candidate)
        image_exists = display_file.exists() or thumbnail_file.exists()
        if not metadata_exists and not image_exists:
            return candidate
        candidate = f"{base_id}-{counter}"
        counter += 1


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


def ensure_gallery_page(category: str, project_root: Path, dry_run: bool) -> None:
    pages_dir = project_root / "content" / "pages"
    page_file = pages_dir / f"{category}.md"
    if page_file.exists():
        return

    title = title_from_slug(category)
    page_content = (
        f"title: {title}\n"
        f"slug: {category}\n"
        "template: gallery\n"
    )

    if dry_run:
        print(f"[DRY RUN] page -> {page_file}")
        return

    pages_dir.mkdir(parents=True, exist_ok=True)
    page_file.write_text(page_content, encoding="utf-8")


def derivative_paths(category_dir: Path, photo_id: str) -> tuple[Path, Path]:
    display_file = category_dir / f"{photo_id}-display{DERIVATIVE_EXTENSION}"
    thumbnail_file = category_dir / f"{photo_id}-thumb{DERIVATIVE_EXTENSION}"
    return display_file, thumbnail_file


def save_web_derivative(source_file: Path, destination_file: Path, max_edge: int) -> None:
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


def main() -> int:
    args = parse_args()

    project_root = Path(__file__).resolve().parents[1]
    src_dir = Path(args.src).resolve()
    dest_dir = Path(args.dest).resolve()

    if not src_dir.exists():
        print(f"Source directory does not exist: {src_dir}")
        return 1

    images = source_images(src_dir)
    if not images:
        print(f"No images found in {src_dir}")
        return 0

    copied = 0
    skipped = 0

    for source_file in images:
        category = infer_category(source_file, src_dir, args.category)
        if not category:
            print(
                "Skipping "
                f"{source_file}: no category found. Use subfolders or pass --category."
            )
            skipped += 1
            continue

        detected_dt = exif_datetime(source_file)
        if not detected_dt:
            detected_dt = dt.datetime.fromtimestamp(source_file.stat().st_mtime)

        category_dir = dest_dir / category
        raw_stem = slugify(source_file.stem) or "photo"
        base_id = f"{detected_dt.strftime('%Y-%m-%d')}-{raw_stem}"
        photo_id = unique_id(category_dir, base_id)

        metadata_file = category_dir / f"{photo_id}.json"
        display_file, thumbnail_file = derivative_paths(category_dir, photo_id)

        metadata = {
            "id": photo_id,
            "category": category,
            "date": detected_dt.strftime("%Y-%m-%d"),
            "location": "",
            "caption": "",
            "published": not args.draft,
            "display_filename": display_file.name,
            "thumbnail_filename": thumbnail_file.name,
        }

        if args.dry_run:
            print(f"[DRY RUN] display -> {display_file}")
            print(f"[DRY RUN] thumbnail -> {thumbnail_file}")
            print(f"[DRY RUN] metadata -> {metadata_file}")
            ensure_gallery_page(category, project_root, dry_run=True)
            copied += 1
            continue

        category_dir.mkdir(parents=True, exist_ok=True)
        save_web_derivative(source_file, display_file, DISPLAY_MAX_EDGE)
        save_web_derivative(source_file, thumbnail_file, THUMBNAIL_MAX_EDGE)

        if not args.copy:
            source_file.unlink()

        metadata_file.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        ensure_gallery_page(category, project_root, dry_run=False)

        copied += 1
        print(
            f"Ingested {source_file.name} -> {display_file.relative_to(dest_dir.parent)}"
        )

    print(f"Done. Ingested: {copied}, Skipped: {skipped}")
    if not args.dry_run and args.copy:
        print("Tip: avoid --copy to prevent re-ingesting the same inbox files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
