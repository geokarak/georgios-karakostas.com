import json
from pathlib import Path

from PIL import Image, ImageCms

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
        "display_filename": "2024-01-01-photo-display.webp",
        "thumbnail_filename": "2024-01-01-photo-thumb.webp",
    }
    serialized = json.dumps(metadata)
    assert isinstance(serialized, str)


def test_save_web_derivative_resizes_large_image(tmp_path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "thumb.webp"

    Image.new("RGB", (4032, 3024), color="navy").save(source, format="JPEG")

    ingest_photos.save_web_derivative(source, destination, max_edge=900)

    assert destination.exists()
    with Image.open(destination) as image:
        assert max(image.size) == 900


def test_derivative_paths_use_expected_suffixes(tmp_path):
    display_file, thumbnail_file = ingest_photos.derivative_paths(tmp_path, "2024-01-01-photo")

    assert display_file.name == "2024-01-01-photo-display.webp"
    assert thumbnail_file.name == "2024-01-01-photo-thumb.webp"


def test_save_web_derivative_embeds_icc_profile(tmp_path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "display.webp"
    icc_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

    Image.new("RGB", (1200, 800), color="red").save(
        source,
        format="JPEG",
        icc_profile=icc_profile,
    )

    ingest_photos.save_web_derivative(source, destination, max_edge=900)

    with Image.open(destination) as image:
        assert image.info.get("icc_profile")


def test_main_writes_only_derivatives_and_metadata(tmp_path, monkeypatch):
    src_dir = tmp_path / "inbox" / "iphone"
    dest_dir = tmp_path / "content" / "images" / "photos"
    src_dir.mkdir(parents=True)
    source = src_dir / "test.jpg"
    Image.new("RGB", (1600, 1200), color="green").save(source, format="JPEG")

    monkeypatch.setattr(
        ingest_photos,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {
                "src": str(tmp_path / "inbox"),
                "dest": str(dest_dir),
                "category": None,
                "copy": False,
                "draft": False,
                "dry_run": False,
            },
        )(),
    )
    monkeypatch.setattr(ingest_photos, "ensure_gallery_page", lambda *args, **kwargs: None)

    assert ingest_photos.main() == 0

    category_dir = dest_dir / "iphone"
    metadata_files = list(category_dir.glob("*.json"))
    assert len(metadata_files) == 1

    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["display_filename"].endswith("-display.webp")
    assert metadata["thumbnail_filename"].endswith("-thumb.webp")
    assert "filename" not in metadata

    assert (category_dir / metadata["display_filename"]).exists()
    assert (category_dir / metadata["thumbnail_filename"]).exists()
    assert list(category_dir.glob("*.jpg")) == []
    assert not source.exists()
