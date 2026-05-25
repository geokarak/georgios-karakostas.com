"""This file reads photo data from ``content/images/photos`` and hands it to the
gallery templates so they can render the photography pages.

What this plugin does
---------------------
1. Read every JSON file under ``content/images/photos``.
2. Skip photos that are not published.
3. Resolve the matching ``display`` and ``thumb`` WebP files.
4. Build Python dictionaries for the published photos.
5. Add those dictionaries to Pelican's shared template context.

Here, "shared template context" simply means the data object that Pelican passes
to the Jinja templates when rendering pages. If a value is added there, it can be
used from template files under ``theme/templates/``.

This plugin adds two values to that context:

- ``photos``: all published photos in one flat list
- ``photos_by_category``: the same photos grouped by category slug
"""

import datetime
import json
import logging
from pathlib import Path

from pelican import signals

BASE_DIR = Path(__file__).resolve(strict=True).parents[2]
CONTENT_DIR = BASE_DIR / "content"
IMAGES_DIR = BASE_DIR / "content" / "images" / "photos"
DISPLAY_TITLE_EXCEPTIONS = {"iphone": "iPhone"}

logger = logging.getLogger(__name__)


def parse_datetime_original(date_value):
    try:
        return datetime.datetime.strptime(date_value, "%Y:%m:%d %H:%M:%S")
    except ValueError as error:
        raise ValueError(f"Invalid DateTimeOriginal format: {date_value}") from error


def relative_photo_url(image_file):
    relative_path = image_file.relative_to(CONTENT_DIR).as_posix()
    return f"../{relative_path}"


def find_image_by_filename(metadata_path, filename):
    if filename:
        candidate = metadata_path.parent / filename
        if candidate.exists():
            return candidate

    return None


def display_title(category):
    return DISPLAY_TITLE_EXCEPTIONS.get(category, category.capitalize())


def load_photos_from_sidecars(path):
    photos = []
    for metadata_path in sorted(path.rglob("*.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            logger.warning(
                "Skipping invalid JSON metadata in %s: %s", metadata_path, error
            )
            continue

        if metadata.get("published", True) is False:
            continue

        category = metadata.get("category")
        photo_id = metadata.get("id")
        date_value = metadata.get("DateTimeOriginal", "")

        if not category or not photo_id:
            logger.warning("Skipping %s: missing 'category' or 'id'", metadata_path)
            continue

        try:
            date_object = parse_datetime_original(date_value)
        except ValueError as error:
            logger.warning("Skipping %s: %s", metadata_path, error)
            continue

        display_file = find_image_by_filename(
            metadata_path, metadata.get("display_filename")
        )
        thumbnail_file = find_image_by_filename(
            metadata_path,
            metadata.get("thumbnail_filename"),
        )
        if not display_file or not thumbnail_file:
            logger.warning("Skipping %s: matching image file not found", metadata_path)
            continue

        photos.append(
            {
                "id": photo_id,
                "photo_id": photo_id,
                "category": category,
                "date": date_object,
                "location": metadata.get("location"),
                "caption": metadata.get("caption", ""),
                "photo_url": relative_photo_url(display_file),
                "thumbnail_url": relative_photo_url(thumbnail_file),
            }
        )

    return photos


def group_photos_by_category(photos):
    grouped = {}
    for photo in photos:
        grouped.setdefault(photo["category"], []).append(photo)
    return grouped


def format_photo_summary(photos_by_category):
    if not photos_by_category:
        return "Photos: total=0"

    total = sum(len(items) for items in photos_by_category.values())
    parts = [
        f"{category}={len(items)}"
        for category, items in sorted(photos_by_category.items())
    ]
    return f"Photos: total={total} | " + ", ".join(parts)


def add_photos_to_context(generators):
    if not generators:
        return

    photos_list = load_photos_from_sidecars(IMAGES_DIR)
    shared_context = generators[0].context
    shared_context["photos"] = photos_list
    photos_by_category = group_photos_by_category(photos_list)
    shared_context["photos_by_category"] = photos_by_category
    logger.info("Loaded %s photos into shared template context", len(photos_list))
    print(format_photo_summary(photos_by_category))


def register():
    signals.all_generators_finalized.connect(add_photos_to_context)
