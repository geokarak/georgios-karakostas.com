import json
from pathlib import PurePosixPath

import pytest

from dropbox_sync import download as download_helpers
from dropbox_sync import finalize as finalize_helpers
from dropbox_sync import paths as path_helpers


def test_normalize_dropbox_path_adds_leading_slash():
    assert path_helpers.normalize_dropbox_path("site-photo-inbox") == PurePosixPath(
        "/site-photo-inbox"
    )


def test_relative_dropbox_path_preserves_category_structure():
    relative = path_helpers.relative_dropbox_path(
        "/site-photo-inbox/iphone/2024-02-22-photo.jpg",
        PurePosixPath("/site-photo-inbox"),
    )

    assert relative == PurePosixPath("iphone/2024-02-22-photo.jpg")


def test_archive_destination_mirrors_inbox_structure():
    archive_path = path_helpers.archive_destination(
        "/site-photo-inbox/street/frame.webp",
        PurePosixPath("/site-photo-inbox"),
        PurePosixPath("/site-photo-archive"),
    )

    assert archive_path == PurePosixPath("/site-photo-archive/street/frame.webp")


def test_quarantine_destination_mirrors_inbox_structure():
    quarantine_path = path_helpers.quarantine_destination(
        "/site-photo-inbox/street/frame.webp",
        PurePosixPath("/site-photo-inbox"),
        PurePosixPath("/site-photo-quarantine"),
    )

    assert quarantine_path == PurePosixPath("/site-photo-quarantine/street/frame.webp")


def test_is_supported_image_filters_extensions():
    assert path_helpers.is_supported_image("/site-photo-inbox/a.JPG") is True
    assert path_helpers.is_supported_image("/site-photo-inbox/a.heic") is False


def test_download_dropbox_inbox_creates_staging_dir_when_inbox_is_empty(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(download_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(download_helpers, "list_remote_images", lambda token, root: [])

    staging_dir = tmp_path / "dropbox-inbox"
    manifest_file = tmp_path / "archive-manifest.json"
    downloaded = download_helpers.download_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        manifest_file=manifest_file,
    )

    assert downloaded == 0
    assert staging_dir.exists()
    assert json.loads(manifest_file.read_text(encoding="utf-8")) == []


def test_download_dropbox_inbox_writes_manifest_for_later_archive(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(download_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        download_helpers,
        "list_remote_images",
        lambda token, root: [
            {"path_display": "/site-photo-inbox/iphone/a.jpg", "path_lower": "a"}
        ],
    )

    def fake_download(token, source_path, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"img")

    monkeypatch.setattr(
        download_helpers,
        "download_remote_file",
        fake_download,
    )

    staging_dir = tmp_path / "dropbox-inbox"
    manifest_file = tmp_path / "archive-manifest.json"

    downloaded = download_helpers.download_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        manifest_file=manifest_file,
    )

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert downloaded == 1
    assert (staging_dir / "iphone" / "a.jpg").exists()
    assert manifest == [
        {
            "source_path": "/site-photo-inbox/iphone/a.jpg",
            "staging_path": str((staging_dir / "iphone" / "a.jpg").resolve()),
        }
    ]


def test_finalize_dropbox_inbox_archives_ingested_and_quarantines_skipped(
    monkeypatch, tmp_path
):
    download_manifest = tmp_path / "download-manifest.json"
    download_manifest.write_text(
        json.dumps(
            [
                {
                    "source_path": "/site-photo-inbox/street/frame.webp",
                    "staging_path": "/tmp/dropbox-inbox/street/frame.webp",
                },
                {
                    "source_path": "/site-photo-inbox/iphone/bad.jpg",
                    "staging_path": "/tmp/dropbox-inbox/iphone/bad.jpg",
                },
            ]
        ),
        encoding="utf-8",
    )

    ingest_results = tmp_path / "ingest-results.json"
    ingest_results.write_text(
        json.dumps(
            [
                {
                    "source_file": "/tmp/dropbox-inbox/street/frame.webp",
                    "status": "ingested",
                },
                {
                    "source_file": "/tmp/dropbox-inbox/iphone/bad.jpg",
                    "status": "skipped",
                    "reason": "missing-exif-datetimeoriginal",
                },
            ]
        ),
        encoding="utf-8",
    )

    moved_paths = []
    monkeypatch.setattr(finalize_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        finalize_helpers,
        "move_remote_file",
        lambda token, source_path, destination_path: moved_paths.append(
            (token, source_path, destination_path)
        ),
    )

    finalized = finalize_helpers.finalize_dropbox_inbox(
        download_manifest_file=download_manifest,
        ingest_results_file=ingest_results,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        archive_root=PurePosixPath("/site-photo-archive"),
        quarantine_root=PurePosixPath("/site-photo-quarantine"),
    )

    assert finalized == 2
    assert moved_paths == [
        (
            "token",
            "/site-photo-inbox/street/frame.webp",
            PurePosixPath("/site-photo-archive/street/frame.webp"),
        ),
        (
            "token",
            "/site-photo-inbox/iphone/bad.jpg",
            PurePosixPath("/site-photo-quarantine/iphone/bad.jpg"),
        ),
    ]


def test_finalize_dropbox_inbox_fails_on_manifest_mismatch(monkeypatch, tmp_path):
    download_manifest = tmp_path / "download-manifest.json"
    download_manifest.write_text(
        json.dumps(
            [
                {
                    "source_path": "/site-photo-inbox/street/frame.webp",
                    "staging_path": "/tmp/dropbox-inbox/street/frame.webp",
                }
            ]
        ),
        encoding="utf-8",
    )

    ingest_results = tmp_path / "ingest-results.json"
    ingest_results.write_text(
        json.dumps(
            [
                {
                    "source_file": "/tmp/dropbox-inbox/other/frame.webp",
                    "status": "ingested",
                }
            ]
        ),
        encoding="utf-8",
    )

    moved_paths = []
    monkeypatch.setattr(finalize_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        finalize_helpers,
        "move_remote_file",
        lambda token, source_path, destination_path: moved_paths.append(
            (token, source_path, destination_path)
        ),
    )

    with pytest.raises(RuntimeError):
        finalize_helpers.finalize_dropbox_inbox(
            download_manifest_file=download_manifest,
            ingest_results_file=ingest_results,
            inbox_root=PurePosixPath("/site-photo-inbox"),
            archive_root=PurePosixPath("/site-photo-archive"),
            quarantine_root=PurePosixPath("/site-photo-quarantine"),
        )

    assert moved_paths == []
