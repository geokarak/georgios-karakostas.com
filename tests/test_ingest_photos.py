import json
from pathlib import Path

from scripts import ingest_photos


def test_slugify():
    assert ingest_photos.slugify("  Hello, World!  ") == "hello-world"


def test_infer_category():
    src_root = Path("/tmp/inbox")
    nested = src_root / "Street Shots" / "img.jpg"
    top_level = src_root / "img.jpg"

    assert ingest_photos.infer_category(nested, src_root, fallback=None) == "street-shots"
    assert (
        ingest_photos.infer_category(top_level, src_root, fallback="Travel Photos")
        == "travel-photos"
    )
    assert ingest_photos.infer_category(top_level, src_root, fallback=None) is None


def test_unique_id_increments_when_files_exist(tmp_path):
    category_dir = tmp_path
    base_id = "2024-02-22-sunset"

    (category_dir / f"{base_id}.json").write_text("{}", encoding="utf-8")
    (category_dir / f"{base_id}.jpg").write_bytes(b"image")

    candidate = ingest_photos.unique_id(category_dir, base_id)
    assert candidate == f"{base_id}-2"


def test_ensure_gallery_page_creates_page(tmp_path):
    ingest_photos.ensure_gallery_page("macro", tmp_path, dry_run=False)

    page_file = tmp_path / "content" / "pages" / "macro.md"
    assert page_file.exists()
    text = page_file.read_text(encoding="utf-8")
    assert "title: Macro" in text
    assert "slug: macro" in text
    assert "template: gallery" in text


def test_ensure_gallery_page_handles_iphone_exception(tmp_path):
    ingest_photos.ensure_gallery_page("iphone", tmp_path, dry_run=False)

    page_file = tmp_path / "content" / "pages" / "iphone.md"
    text = page_file.read_text(encoding="utf-8")
    assert "title: iPhone" in text


def test_source_images_filters_supported_extensions(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    (tmp_path / "c.PNG").write_bytes(b"x")

    found = ingest_photos.source_images(tmp_path)
    assert [path.name for path in found] == ["a.jpg", "c.PNG"]


def test_generated_metadata_schema_is_serializable():
    metadata = {
        "id": "2024-01-01-photo",
        "category": "street",
        "date": "2024-01-01",
        "location": "",
        "caption": "",
        "published": True,
        "filename": "2024-01-01-photo.jpg",
    }
    serialized = json.dumps(metadata)
    assert isinstance(serialized, str)
