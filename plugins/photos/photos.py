"""This file reads photo data from the configured photos directory and hands it
to the gallery templates so they can render the photography pages.

What this plugin does
---------------------
1. Read every JSON file under the configured ``PHOTOS_PATH``.
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

DISPLAY_TITLE_EXCEPTIONS = {"iphone": "iPhone"}

logger = logging.getLogger(__name__)


def parse_datetime_original(date_value):
    try:
        return datetime.datetime.strptime(date_value, "%Y:%m:%d %H:%M:%S")
    except ValueError as error:
        raise ValueError(f"Invalid DateTimeOriginal format: {date_value}") from error


# Read the content root from Pelican settings so the plugin follows the same
# folder configuration as the rest of the site.
def content_dir_from_settings(settings):
    configured_path = Path(settings["PATH"])
    return configured_path.resolve()


# Keep photo sidecars configurable inside the content tree instead of tying the
# plugin to one hardcoded `content/images/photos` repo layout.
def photos_dir_from_settings(settings, content_dir):
    photos_path = Path(settings.get("PHOTOS_PATH", "images/photos"))
    return (content_dir / photos_path).resolve()


# Build URLs from the content-relative asset path and SITEURL. This avoids
# guessing where the page lives with `../...`, which breaks more easily when
# page URLs change.
def photo_url(image_file, content_dir, siteurl):
    relative_path = image_file.relative_to(content_dir).as_posix()
    normalized_siteurl = siteurl.rstrip("/")
    if normalized_siteurl:
        return f"{normalized_siteurl}/{relative_path}"
    return f"/{relative_path}"


def find_image_by_filename(metadata_path, filename):
    if filename:
        candidate = metadata_path.parent / filename
        if candidate.exists():
            return candidate

    return None


def display_title(category):
    return DISPLAY_TITLE_EXCEPTIONS.get(category, category.capitalize())


def load_photos_from_sidecars(path, content_dir, siteurl):
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
                "photo_url": photo_url(display_file, content_dir, siteurl),
                "thumbnail_url": photo_url(thumbnail_file, content_dir, siteurl),
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
    # `generators` is the list of Pelican build objects available while the site
    # is being created.
    #
    # For this plugin, the important idea is simple: these objects already know
    # the current site settings and already carry the shared data that templates
    # can read.
    #
    # So this function uses them to answer two questions:
    # 1. Where should photos be loaded from for this build?
    # 2. Where should the loaded photo data be stored so templates can use it?

    # Step 1: if Pelican gives us no build objects, there is nothing useful to do.
    if not generators:
        return

    # Step 2: use the first build object as our source of truth.
    #
    # It already knows the settings for this build, so we read the paths and URL
    # values from there instead of hardcoding them in the plugin.
    first_generator = generators[0]
    settings = first_generator.settings

    # Step 3: work out the key locations we need.
    #
    # `content_dir` is the main content folder.
    # `photos_dir` is the photo folder inside it.
    # `siteurl` tells us how final image links should look for this build.
    content_dir = content_dir_from_settings(settings)
    photos_dir = photos_dir_from_settings(settings, content_dir)
    siteurl = settings.get("SITEURL", "")

    # Step 4: read the photo data from disk.
    #
    # This loads the JSON files, ignores broken or unpublished entries, finds the
    # matching image files, and builds the photo records the templates need.
    photos_list = load_photos_from_sidecars(photos_dir, content_dir, siteurl)

    # Step 5: store that photo data in the shared template data.
    #
    # We keep:
    # - one flat list of all photos
    # - one grouped version, so a page like `/iphone/` can grab only iPhone photos
    shared_context = first_generator.context
    shared_context["photos"] = photos_list
    photos_by_category = group_photos_by_category(photos_list)
    shared_context["photos_by_category"] = photos_by_category

    # Step 6: print a short summary so the build output shows what was loaded.
    logger.info("Loaded %s photos into shared template context", len(photos_list))
    print(format_photo_summary(photos_by_category))


def register():
    signals.all_generators_finalized.connect(add_photos_to_context)
