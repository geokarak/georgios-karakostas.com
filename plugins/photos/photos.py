import datetime
import logging
from pathlib import Path

from pelican import signals
from pelican.contents import Article
from pelican.readers import BaseReader
from PIL import Image

BASE_DIR = Path(__file__).resolve(strict=True).parents[2]
IMAGES_DIR = BASE_DIR / "content" / "images" / "photos"

logger = logging.getLogger(__name__)


def add_photos(articleGenerator):
    settings = articleGenerator.settings
    baseReader = BaseReader(settings)

    photos_list = load_photos_from(IMAGES_DIR)

    counter = 0
    for photo in photos_list:
        photo_mta = photo.text

        category = photo_mta.get("category")

        date = photo_mta.get("date", "")
        date_object = datetime.datetime.strptime(date, "%Y-%m-%d")

        location = photo_mta.get("location")
        caption = photo_mta.get("caption", "")

        _id = photo_mta.get("id")
        photo_url = f"../images/photos/{_id}.png"
        thumbnail_url = f"../images/photos/{_id}.png"

        new_article = Article(
            caption,
            {
                "title": date,
                "date": date_object,
                "location": location,
                "photo_url": photo_url,
                "thumbnail_url": thumbnail_url,
                "category": baseReader.process_metadata("category", category),
                "url": f"{category}/{_id}.html",
                "save_as": f"{category}/{_id}.html",
            },
        )

        articleGenerator.articles.append(new_article)
        counter += 1

    logger.info(f"Added {counter} photos to the article list")


def load_photos_from(path):
    photos_list = []
    for filename in path.glob("*.png"):
        img = Image.open(filename)
        photos_list.append(img)
    return photos_list


def register():
    signals.article_generator_finalized.connect(add_photos)
