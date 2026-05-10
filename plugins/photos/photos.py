import datetime
import json
import logging
from pathlib import Path

from pelican import signals
from pelican.contents import Article
from pelican.readers import BaseReader

BASE_DIR = Path(__file__).resolve(strict=True).parents[2]
CONTENT_DIR = BASE_DIR / "content"
IMAGES_DIR = BASE_DIR / "content" / "images" / "photos"
SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
DISPLAY_TITLE_EXCEPTIONS = {"iphone": "iPhone"}

logger = logging.getLogger(__name__)


def parse_date(date_value):
    for date_format in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(date_value, date_format)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_value}")


def relative_photo_url(image_file):
    relative_path = image_file.relative_to(CONTENT_DIR).as_posix()
    return f"../{relative_path}"


def find_image_for_metadata(metadata_path, metadata):
    filename = metadata.get("filename")
    if filename:
        candidate = metadata_path.parent / filename
        if candidate.exists() and candidate.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            return candidate

    for extension in SUPPORTED_IMAGE_EXTENSIONS:
        candidate = metadata_path.with_suffix(extension)
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
            logger.warning("Skipping invalid JSON metadata in %s: %s", metadata_path, error)
            continue

        if metadata.get("published", True) is False:
            continue

        category = metadata.get("category")
        photo_id = metadata.get("id")
        date_value = metadata.get("date", "")

        if not category or not photo_id:
            logger.warning("Skipping %s: missing 'category' or 'id'", metadata_path)
            continue

        try:
            date_object = parse_date(date_value)
        except ValueError as error:
            logger.warning("Skipping %s: %s", metadata_path, error)
            continue

        image_file = find_image_for_metadata(metadata_path, metadata)
        if not image_file:
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
                "photo_url": relative_photo_url(image_file),
            }
        )

    return photos


def add_photos(articleGenerator):
    settings = articleGenerator.settings
    base_reader = BaseReader(settings)

    photos_list = load_photos_from_sidecars(IMAGES_DIR)

    counter = 0
    for photo in photos_list:
        category = photo["category"]
        photo_id = photo["id"]

        new_article = Article(
            photo["caption"],
            {
                "title": display_title(category),
                "date": photo["date"],
                "location": photo["location"],
                "photo_url": photo["photo_url"],
                "thumbnail_url": photo["photo_url"],
                "photo_id": photo["photo_id"],
                "category": base_reader.process_metadata("category", category),
                "url": f"{category}/{photo_id}.html",
                "save_as": f"{category}/{photo_id}.html",
            },
        )

        articleGenerator.articles.append(new_article)
        counter += 1

    logger.info(f"Added {counter} photos to the article list")


def register():
    signals.article_generator_finalized.connect(add_photos)
