import json
import subprocess
import sys
import textwrap
import datetime as dt
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from tooling import ingest_photos
from tooling.photo_ingest import exif as exif_helpers
from tooling.photo_ingest import images as image_helpers
from tooling.photo_ingest import pages as page_helpers
from tooling.photo_ingest import source as source_helpers


def test_slugify():
    assert source_helpers.slugify("  Hello, World!  ") == "hello-world"


def test_infer_category():
    src_root = Path("/tmp/inbox")
    nested = src_root / "Street Shots" / "img.jpg"
    top_level = src_root / "img.jpg"

    assert (
        source_helpers.infer_category(nested, src_root, fallback=None) == "street-shots"
    )
    assert (
        source_helpers.infer_category(top_level, src_root, fallback="Travel Photos")
        == "travel-photos"
    )
    assert source_helpers.infer_category(top_level, src_root, fallback=None) is None


def test_unique_id_retries_when_files_exist(tmp_path, monkeypatch):
    category_dir = tmp_path
    captured_at = dt.datetime(2024, 2, 22, 13, 15, 0)
    first_candidate = "2024-02-22-131500-deadbeef"
    second_candidate = "2024-02-22-131500-feedface"

    (category_dir / f"{first_candidate}.json").write_text("{}", encoding="utf-8")
    generated_ids = iter([first_candidate, second_candidate])
    monkeypatch.setattr(
        source_helpers,
        "generated_photo_id",
        lambda dt_value: next(generated_ids),
    )

    candidate = source_helpers.unique_id(
        category_dir,
        captured_at,
        image_helpers.derivative_paths,
    )
    assert candidate == second_candidate


def test_require_exiftool_raises_when_missing(monkeypatch):
    monkeypatch.setattr(exif_helpers.shutil, "which", lambda name: None)

    try:
        exif_helpers.require_exiftool()
    except RuntimeError as error:
        assert "requires exiftool" in str(error)
    else:
        raise AssertionError("require_exiftool() should raise when exiftool is missing")


def test_parse_exiftool_datetime_supports_common_formats():
    assert (
        exif_helpers.parse_exiftool_datetime("2021:08:01 13:15:39").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        == "2021-08-01 13:15:39"
    )


def test_exiftool_datetime_from_metadata_prefers_supported_tags():
    metadata = {
        "ExifIFD:CreateDate": "2015:04:16 13:01:15",
        "ExifIFD:DateTimeOriginal": "2015:04:16 12:59:59",
    }

    detected = exif_helpers.exiftool_datetime_from_metadata(metadata)
    assert detected.strftime("%Y-%m-%d %H:%M:%S") == "2015-04-16 12:59:59"


def test_exif_datetimes_prefers_original_date_tags(monkeypatch, tmp_path):
    sample = tmp_path / "sample.jpg"
    sample.write_bytes(b"x")
    payload = json.dumps(
        [
            {
                "SourceFile": str(sample.resolve()),
                "ExifIFD:DateTimeOriginal": "2015:04:16 13:01:15",
            }
        ]
    )

    monkeypatch.setattr(
        exif_helpers.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=payload, stderr=""
        ),
    )

    detected = exif_helpers.exif_datetimes([sample], "/usr/bin/exiftool")[sample]
    assert detected.strftime("%Y-%m-%d") == "2015-04-16"


def test_exif_datetimes_reads_multiple_files_in_one_call(monkeypatch, tmp_path):
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"x")
    second.write_bytes(b"y")
    payload = json.dumps(
        [
            {
                "SourceFile": str(first.resolve()),
                "ExifIFD:DateTimeOriginal": "2015:04:16 13:01:15",
            },
            {
                "SourceFile": str(second.resolve()),
                "ExifIFD:CreateDate": "2016:05:17 14:02:16",
            },
        ]
    )

    monkeypatch.setattr(
        exif_helpers.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=payload, stderr=""
        ),
    )

    detected = exif_helpers.exif_datetimes([first, second], "/usr/bin/exiftool")

    assert detected[first].strftime("%Y-%m-%d %H:%M:%S") == "2015-04-16 13:01:15"
    assert detected[second].strftime("%Y-%m-%d %H:%M:%S") == "2016-05-17 14:02:16"


def test_exif_datetimes_falls_back_to_single_file_lookups_when_chunk_fails(
    monkeypatch, tmp_path
):
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"x")
    second.write_bytes(b"y")

    def fake_batch(paths, exiftool_path):
        if len(paths) == 2:
            return {path: None for path in paths}
        if paths[0] == first:
            return {first: dt.datetime(2015, 4, 16, 13, 1, 15)}
        return {second: dt.datetime(2016, 5, 17, 14, 2, 16)}

    monkeypatch.setattr(exif_helpers, "exif_datetimes_batch", fake_batch)

    detected = exif_helpers.exif_datetimes([first, second], "/usr/bin/exiftool")

    assert detected[first].strftime("%Y-%m-%d %H:%M:%S") == "2015-04-16 13:01:15"
    assert detected[second].strftime("%Y-%m-%d %H:%M:%S") == "2016-05-17 14:02:16"


def test_exif_datetimes_processes_multiple_chunks(monkeypatch, tmp_path):
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    third = tmp_path / "third.jpg"
    first.write_bytes(b"x")
    second.write_bytes(b"y")
    third.write_bytes(b"z")

    seen_chunks = []
    monkeypatch.setattr(exif_helpers, "EXIFTOOL_BATCH_SIZE", 2)

    def fake_batch(paths, exiftool_path):
        seen_chunks.append(paths)
        return {path: dt.datetime(2024, 1, 1, 12, 0, 0) for path in paths}

    monkeypatch.setattr(exif_helpers, "exif_datetimes_batch", fake_batch)

    detected = exif_helpers.exif_datetimes([first, second, third], "/usr/bin/exiftool")

    assert seen_chunks == [[first, second], [third]]
    assert all(value is not None for value in detected.values())


def test_exif_datetimes_returns_createdate_when_datetimeoriginal_missing(
    monkeypatch, tmp_path
):
    sample = tmp_path / "sample.jpg"
    sample.write_bytes(b"x")
    payload = json.dumps(
        [
            {
                "SourceFile": str(sample.resolve()),
                "ExifIFD:CreateDate": "2015:04:16 13:01:15",
                "XMP:CreateDate": "2015:04:16 13:01:15",
            }
        ]
    )

    monkeypatch.setattr(
        exif_helpers.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=payload, stderr=""
        ),
    )

    detected = exif_helpers.exif_datetimes([sample], "/usr/bin/exiftool")[sample]
    assert detected.strftime("%Y-%m-%d %H:%M:%S") == "2015-04-16 13:01:15"


def test_exif_datetimes_returns_none_without_supported_exif_tags(monkeypatch, tmp_path):
    sample = tmp_path / "sample.jpg"
    sample.write_bytes(b"x")
    payload = json.dumps(
        [
            {
                "SourceFile": str(sample.resolve()),
                "XMP:CreateDate": "2015:04:16 13:01:15",
            }
        ]
    )

    monkeypatch.setattr(
        exif_helpers.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=payload, stderr=""
        ),
    )

    assert exif_helpers.exif_datetimes([sample], "/usr/bin/exiftool")[sample] is None


def test_ensure_gallery_page_creates_page(tmp_path):
    page_helpers.ensure_gallery_page("macro", tmp_path, dry_run=False)

    page_file = tmp_path / "content" / "pages" / "macro.md"
    assert page_file.exists()
    text = page_file.read_text(encoding="utf-8")
    assert "title: Macro" in text
    assert "slug: macro" in text
    assert "template: gallery" in text


def test_ensure_gallery_page_handles_iphone_exception(tmp_path):
    page_helpers.ensure_gallery_page("iphone", tmp_path, dry_run=False)

    page_file = tmp_path / "content" / "pages" / "iphone.md"
    text = page_file.read_text(encoding="utf-8")
    assert "title: iPhone" in text


def test_source_images_filters_supported_extensions(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    (tmp_path / "c.PNG").write_bytes(b"x")

    found = source_helpers.source_images(tmp_path)
    assert [path.name for path in found] == ["a.jpg", "c.PNG"]


def test_generated_metadata_schema_is_serializable():
    metadata = {
        "id": "2024-01-01-132045-a1b2c3d4",
        "category": "street",
        "DateTimeOriginal": "2024:01:01 13:20:45",
        "location": "",
        "caption": "",
        "published": True,
        "display_filename": "2024-01-01-132045-a1b2c3d4-display.webp",
        "thumbnail_filename": "2024-01-01-132045-a1b2c3d4-thumb.webp",
    }
    serialized = json.dumps(metadata)
    assert isinstance(serialized, str)


def test_save_web_derivative_resizes_large_image(tmp_path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "thumb.webp"

    Image.new("RGB", (4032, 3024), color="navy").save(source, format="JPEG")

    image_helpers.save_web_derivative(source, destination, max_edge=900)

    assert destination.exists()
    with Image.open(destination) as image:
        assert max(image.size) == 900


def test_derivative_paths_use_expected_suffixes(tmp_path):
    display_file, thumbnail_file = image_helpers.derivative_paths(
        tmp_path, "2024-01-01-132045-a1b2c3d4"
    )

    assert display_file.name == "2024-01-01-132045-a1b2c3d4-display.webp"
    assert thumbnail_file.name == "2024-01-01-132045-a1b2c3d4-thumb.webp"


def test_save_web_derivative_embeds_icc_profile(tmp_path):
    source = tmp_path / "source.jpg"
    destination = tmp_path / "display.webp"
    icc_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

    Image.new("RGB", (1200, 800), color="red").save(
        source,
        format="JPEG",
        icc_profile=icc_profile,
    )

    image_helpers.save_web_derivative(source, destination, max_edge=900)

    with Image.open(destination) as image:
        assert image.info.get("icc_profile")


def test_main_writes_only_derivatives_and_metadata(tmp_path, monkeypatch):
    src_dir = tmp_path / "inbox" / "iphone"
    dest_dir = tmp_path / "content" / "images" / "photos"
    result_manifest = tmp_path / "ingest-results.json"
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
                "result_manifest": str(result_manifest),
            },
        )(),
    )
    monkeypatch.setattr(exif_helpers, "require_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        exif_helpers,
        "exif_datetimes",
        lambda paths, exiftool_path: {
            path: dt.datetime(2024, 2, 22, 12, 0, 5) for path in paths
        },
    )
    monkeypatch.setattr(
        source_helpers,
        "generated_photo_id",
        lambda captured_at: "2024-02-22-120005-a1b2c3d4",
    )
    monkeypatch.setattr(
        page_helpers, "ensure_gallery_page", lambda *args, **kwargs: None
    )

    assert ingest_photos.main() == 0

    category_dir = dest_dir / "iphone"
    metadata_files = list(category_dir.glob("*.json"))
    assert len(metadata_files) == 1

    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["id"] == "2024-02-22-120005-a1b2c3d4"
    assert metadata["display_filename"].endswith("-display.webp")
    assert metadata["thumbnail_filename"].endswith("-thumb.webp")
    assert "filename" not in metadata
    assert metadata["DateTimeOriginal"] == "2024:02:22 12:00:05"
    assert "test" not in metadata["display_filename"]
    assert "test" not in metadata["thumbnail_filename"]

    assert (category_dir / metadata["display_filename"]).exists()
    assert (category_dir / metadata["thumbnail_filename"]).exists()
    assert list(category_dir.glob("*.jpg")) == []
    assert not source.exists()
    assert json.loads(result_manifest.read_text(encoding="utf-8")) == [
        {
            "source_file": str(source.resolve()),
            "status": "ingested",
        }
    ]


def test_main_writes_skip_results_to_manifest(tmp_path, monkeypatch):
    src_dir = tmp_path / "inbox" / "iphone"
    dest_dir = tmp_path / "content" / "images" / "photos"
    result_manifest = tmp_path / "ingest-results.json"
    src_dir.mkdir(parents=True)
    skipped_source = src_dir / "skipped.jpg"
    Image.new("RGB", (1600, 1200), color="orange").save(skipped_source, format="JPEG")

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
                "result_manifest": str(result_manifest),
            },
        )(),
    )
    monkeypatch.setattr(exif_helpers, "require_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        exif_helpers,
        "exif_datetimes",
        lambda paths, exiftool_path: {path: None for path in paths},
    )

    assert ingest_photos.main() == 0

    assert json.loads(result_manifest.read_text(encoding="utf-8")) == [
        {
            "source_file": str(skipped_source.resolve()),
            "status": "skipped",
            "reason": "missing-exif-datetimeoriginal",
        }
    ]


def test_main_rolls_back_outputs_when_source_removal_fails(tmp_path, monkeypatch):
    src_dir = tmp_path / "inbox" / "macro"
    dest_dir = tmp_path / "content" / "images" / "photos"
    src_dir.mkdir(parents=True)
    source = src_dir / "test.jpg"
    Image.new("RGB", (1600, 1200), color="purple").save(source, format="JPEG")

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
                "result_manifest": None,
            },
        )(),
    )
    monkeypatch.setattr(exif_helpers, "require_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        exif_helpers,
        "exif_datetimes",
        lambda paths, exiftool_path: {
            path: dt.datetime(2024, 2, 22, 12, 0, 5) for path in paths
        },
    )
    monkeypatch.setattr(
        source_helpers,
        "generated_photo_id",
        lambda captured_at: "2024-02-22-120005-a1b2c3d4",
    )

    original_unlink = Path.unlink

    def fail_when_removing_source(self: Path, missing_ok: bool = False) -> None:
        if self == source and not missing_ok:
            raise PermissionError("cannot remove source file")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_when_removing_source)

    with pytest.raises(PermissionError):
        ingest_photos.main()

    category_dir = dest_dir / "macro"
    assert source.exists()
    assert not (category_dir / "2024-02-22-120005-a1b2c3d4-display.webp").exists()
    assert not (category_dir / "2024-02-22-120005-a1b2c3d4-thumb.webp").exists()
    assert not (category_dir / "2024-02-22-120005-a1b2c3d4.json").exists()
    assert not (tmp_path / "content" / "pages" / "macro.md").exists()


def test_gallery_build_smoke_renders_published_photos_in_order(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    content_dir = tmp_path / "content"
    output_dir = tmp_path / "output"
    photos_dir = content_dir / "images" / "photos" / "iphone"
    pages_dir = content_dir / "pages"
    photos_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    (pages_dir / "iphone.md").write_text(
        "title: iPhone\nslug: iphone\ntemplate: gallery\n",
        encoding="utf-8",
    )

    published_new = {
        "id": "2024-02-22-180931-new",
        "category": "iphone",
        "DateTimeOriginal": "2024:02:22 18:09:31",
        "caption": "Newest",
        "location": "",
        "published": True,
        "display_filename": "2024-02-22-180931-new-display.webp",
        "thumbnail_filename": "2024-02-22-180931-new-thumb.webp",
    }
    published_old = {
        "id": "2023-02-16-190509-old",
        "category": "iphone",
        "DateTimeOriginal": "2023:02:16 19:05:09",
        "caption": "Older",
        "location": "",
        "published": True,
        "display_filename": "2023-02-16-190509-old-display.webp",
        "thumbnail_filename": "2023-02-16-190509-old-thumb.webp",
    }
    unpublished = {
        "id": "2022-10-17-082933-hidden",
        "category": "iphone",
        "DateTimeOriginal": "2022:10:17 08:29:33",
        "caption": "Hidden",
        "location": "",
        "published": False,
        "display_filename": "2022-10-17-082933-hidden-display.webp",
        "thumbnail_filename": "2022-10-17-082933-hidden-thumb.webp",
    }

    for metadata in (published_new, published_old, unpublished):
        (photos_dir / f"{metadata['id']}.json").write_text(
            json.dumps(metadata) + "\n",
            encoding="utf-8",
        )
        (photos_dir / metadata["display_filename"]).write_bytes(b"img")
        (photos_dir / metadata["thumbnail_filename"]).write_bytes(b"img")

    config_file = tmp_path / "pelicanconf.py"
    config_file.write_text(
        textwrap.dedent(
            f"""
            import sys

            sys.path.insert(0, {str(repo_root)!r})

            AUTHOR = "Test Author"
            SITENAME = "Test Site"
            SITEURL = "https://example.com"
            SITE_DESCRIPTION = "Test description"
            SITELOGO = ""
            TWITTER_HANDLE = ""
            PATH = {str(content_dir)!r}
            PAGE_PATHS = ["pages"]
            PAGE_URL = "{{slug}}/"
            PAGE_SAVE_AS = "{{slug}}.html"
            ARTICLE_PATHS = []
            STATIC_PATHS = ["images"]
            PHOTOS_PATH = "images/photos"
            DEFAULT_PAGINATION = False
            FEED_ALL_ATOM = None
            CATEGORY_FEED_ATOM = None
            TRANSLATION_FEED_ATOM = None
            AUTHOR_FEED_ATOM = None
            AUTHOR_FEED_RSS = None
            THEME = {str(repo_root / "theme")!r}
            PLUGINS = ["plugins.photos"]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pelican",
            "-s",
            str(config_file),
            "-o",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )

    rendered = (output_dir / "iphone.html").read_text(encoding="utf-8")

    newest_index = rendered.index(published_new["display_filename"])
    older_index = rendered.index(published_old["display_filename"])

    assert (
        "https://example.com/images/photos/iphone/2024-02-22-180931-new-display.webp"
        in rendered
    )
    assert (
        "https://example.com/images/photos/iphone/2023-02-16-190509-old-display.webp"
        in rendered
    )
    assert unpublished["display_filename"] not in rendered
    assert newest_index < older_index
