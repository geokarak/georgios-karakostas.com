import json

import pytest

from plugins.photos import photos


def test_parse_date_supports_multiple_formats():
    assert photos.parse_date("2024-02-22").strftime("%Y-%m-%d") == "2024-02-22"
    assert photos.parse_date("20240222").strftime("%Y-%m-%d") == "2024-02-22"


def test_parse_date_raises_for_invalid_format():
    with pytest.raises(ValueError):
        photos.parse_date("22/02/2024")


def test_find_image_for_metadata_prefers_filename(tmp_path):
    metadata_path = tmp_path / "photo.json"
    metadata_path.write_text("{}", encoding="utf-8")
    preferred = tmp_path / "custom-name.webp"
    preferred.write_bytes(b"img")

    found = photos.find_image_for_metadata(
        metadata_path,
        {"filename": "custom-name.webp"},
    )
    assert found == preferred


def test_load_photos_from_sidecars_builds_photo_entries(tmp_path):
    content_dir = tmp_path / "content"
    photos_dir = content_dir / "images" / "photos" / "iphone"
    photos_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "id": "2024-02-22-champ-du-tordoir",
        "category": "iphone",
        "date": "2024-02-22",
        "caption": "In the park",
        "location": "Tubize",
        "filename": "2024-02-22-champ-du-tordoir.jpg",
    }
    metadata_path = photos_dir / "2024-02-22-champ-du-tordoir.json"
    image_path = photos_dir / "2024-02-22-champ-du-tordoir.jpg"

    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    image_path.write_bytes(b"img")

    original_content_dir = photos.CONTENT_DIR
    try:
        photos.CONTENT_DIR = content_dir
        loaded = photos.load_photos_from_sidecars(content_dir / "images" / "photos")
    finally:
        photos.CONTENT_DIR = original_content_dir

    assert len(loaded) == 1
    assert loaded[0]["photo_id"] == metadata["id"]
    assert loaded[0]["caption"] == "In the park"
    assert loaded[0]["photo_url"] == "../images/photos/iphone/2024-02-22-champ-du-tordoir.jpg"


def test_load_photos_from_sidecars_skips_unpublished(tmp_path):
    content_dir = tmp_path / "content"
    photos_dir = content_dir / "images" / "photos" / "iphone"
    photos_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = photos_dir / "hidden.json"
    metadata_path.write_text(
        json.dumps(
            {
                "id": "hidden",
                "category": "iphone",
                "date": "2024-02-22",
                "published": False,
            }
        ),
        encoding="utf-8",
    )

    original_content_dir = photos.CONTENT_DIR
    try:
        photos.CONTENT_DIR = content_dir
        loaded = photos.load_photos_from_sidecars(content_dir / "images" / "photos")
    finally:
        photos.CONTENT_DIR = original_content_dir

    assert loaded == []


def test_display_title_handles_iphone_exception():
    assert photos.display_title("iphone") == "iPhone"
    assert photos.display_title("macro") == "Macro"
