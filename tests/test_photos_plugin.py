import json

import pytest

from plugins.photos import photos


def test_parse_datetime_original_supports_expected_format():
    assert photos.parse_datetime_original("2024:02:22 13:15:39").strftime("%Y-%m-%d %H:%M:%S") == "2024-02-22 13:15:39"


def test_parse_datetime_original_raises_for_invalid_format():
    with pytest.raises(ValueError):
        photos.parse_datetime_original("2024-02-22")


def test_find_image_by_filename_returns_existing_file(tmp_path):
    metadata_path = tmp_path / "photo.json"
    metadata_path.write_text("{}", encoding="utf-8")
    preferred = tmp_path / "custom-name.webp"
    preferred.write_bytes(b"img")

    found = photos.find_image_by_filename(metadata_path, "custom-name.webp")
    assert found == preferred


def test_find_image_by_filename_supports_derivative_only_entries(tmp_path):
    metadata_path = tmp_path / "photo.json"
    metadata_path.write_text("{}", encoding="utf-8")
    derivative = tmp_path / "photo-display.webp"
    derivative.write_bytes(b"img")

    found = photos.find_image_by_filename(metadata_path, "photo-display.webp")
    assert found == derivative


def test_load_photos_from_sidecars_builds_photo_entries(tmp_path):
    content_dir = tmp_path / "content"
    photos_dir = content_dir / "images" / "photos" / "iphone"
    photos_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "id": "2024-02-22-131539-champ-du-tordoir",
        "category": "iphone",
        "DateTimeOriginal": "2024:02:22 13:15:39",
        "caption": "In the park",
        "location": "Tubize",
        "display_filename": "2024-02-22-131539-champ-du-tordoir-display.webp",
        "thumbnail_filename": "2024-02-22-131539-champ-du-tordoir-thumb.webp",
    }
    metadata_path = photos_dir / "2024-02-22-131539-champ-du-tordoir.json"
    display_path = photos_dir / metadata["display_filename"]
    thumbnail_path = photos_dir / metadata["thumbnail_filename"]

    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    display_path.write_bytes(b"img")
    thumbnail_path.write_bytes(b"img")

    original_content_dir = photos.CONTENT_DIR
    try:
        photos.CONTENT_DIR = content_dir
        loaded = photos.load_photos_from_sidecars(content_dir / "images" / "photos")
    finally:
        photos.CONTENT_DIR = original_content_dir

    assert len(loaded) == 1
    assert loaded[0]["photo_id"] == metadata["id"]
    assert loaded[0]["caption"] == "In the park"
    assert loaded[0]["photo_url"] == "../images/photos/iphone/2024-02-22-131539-champ-du-tordoir-display.webp"
    assert loaded[0]["thumbnail_url"] == "../images/photos/iphone/2024-02-22-131539-champ-du-tordoir-thumb.webp"


def test_load_photos_from_sidecars_prefers_generated_derivatives(tmp_path):
    content_dir = tmp_path / "content"
    photos_dir = content_dir / "images" / "photos" / "iphone"
    photos_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "id": "2024-02-22-131539-champ-du-tordoir",
        "category": "iphone",
        "DateTimeOriginal": "2024:02:22 13:15:39",
        "display_filename": "2024-02-22-131539-champ-du-tordoir-display.webp",
        "thumbnail_filename": "2024-02-22-131539-champ-du-tordoir-thumb.webp",
    }
    metadata_path = photos_dir / "2024-02-22-131539-champ-du-tordoir.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    (photos_dir / metadata["display_filename"]).write_bytes(b"img")
    (photos_dir / metadata["thumbnail_filename"]).write_bytes(b"img")

    original_content_dir = photos.CONTENT_DIR
    try:
        photos.CONTENT_DIR = content_dir
        loaded = photos.load_photos_from_sidecars(content_dir / "images" / "photos")
    finally:
        photos.CONTENT_DIR = original_content_dir

    assert loaded[0]["photo_url"] == "../images/photos/iphone/2024-02-22-131539-champ-du-tordoir-display.webp"
    assert loaded[0]["thumbnail_url"] == "../images/photos/iphone/2024-02-22-131539-champ-du-tordoir-thumb.webp"


def test_load_photos_from_sidecars_skips_entries_missing_derivatives(tmp_path):
    content_dir = tmp_path / "content"
    photos_dir = content_dir / "images" / "photos" / "iphone"
    photos_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = photos_dir / "broken.json"
    metadata_path.write_text(
        json.dumps(
            {
                "id": "broken",
                "category": "iphone",
                "DateTimeOriginal": "2024:02:22 13:15:39",
                "display_filename": "broken-display.webp",
                "thumbnail_filename": "broken-thumb.webp",
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
                "DateTimeOriginal": "2024:02:22 13:15:39",
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


def test_group_photos_by_category_groups_entries():
    grouped = photos.group_photos_by_category(
        [
            {"category": "iphone", "photo_id": "a"},
            {"category": "iphone", "photo_id": "b"},
            {"category": "street", "photo_id": "c"},
        ]
    )

    assert [photo["photo_id"] for photo in grouped["iphone"]] == ["a", "b"]
    assert [photo["photo_id"] for photo in grouped["street"]] == ["c"]


def test_format_photo_summary_sorts_categories():
    summary = photos.format_photo_summary(
        {
            "street": [{"photo_id": "a"}],
            "iphone": [{"photo_id": "b"}, {"photo_id": "c"}],
        }
    )

    assert summary == "Photos: total=3 | iphone=2, street=1"


def test_format_photo_summary_handles_empty_collection():
    assert photos.format_photo_summary({}) == "Photos: total=0"


def test_add_photos_to_context_populates_shared_context(monkeypatch):
    sample_photos = [
        {
            "category": "iphone",
            "photo_id": "sample",
            "photo_url": "../images/photos/iphone/sample-display.webp",
            "thumbnail_url": "../images/photos/iphone/sample-thumb.webp",
            "caption": "",
            "date": photos.parse_datetime_original("2024:02:22 13:15:39"),
        }
    ]
    monkeypatch.setattr(photos, "load_photos_from_sidecars", lambda path: sample_photos)

    shared_context = {}
    generator = type("Generator", (), {"context": shared_context})()

    photos.add_photos_to_context([generator])

    assert shared_context["photos"] == sample_photos
    assert shared_context["photos_by_category"]["iphone"] == sample_photos


def test_display_title_handles_iphone_exception():
    assert photos.display_title("iphone") == "iPhone"
    assert photos.display_title("macro") == "Macro"
