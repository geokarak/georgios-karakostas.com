import json
from pathlib import PurePosixPath

from scripts import sync_dropbox_inbox


def test_normalize_dropbox_path_adds_leading_slash():
    assert sync_dropbox_inbox.normalize_dropbox_path(
        "site-photo-inbox"
    ) == PurePosixPath("/site-photo-inbox")


def test_relative_dropbox_path_preserves_category_structure():
    relative = sync_dropbox_inbox.relative_dropbox_path(
        "/site-photo-inbox/iphone/2024-02-22-photo.jpg",
        PurePosixPath("/site-photo-inbox"),
    )

    assert relative == PurePosixPath("iphone/2024-02-22-photo.jpg")


def test_archive_destination_mirrors_inbox_structure():
    archive_path = sync_dropbox_inbox.archive_destination(
        "/site-photo-inbox/street/frame.webp",
        PurePosixPath("/site-photo-inbox"),
        PurePosixPath("/site-photo-archive"),
    )

    assert archive_path == PurePosixPath("/site-photo-archive/street/frame.webp")


def test_is_supported_image_filters_extensions():
    assert sync_dropbox_inbox.is_supported_image("/site-photo-inbox/a.JPG") is True
    assert sync_dropbox_inbox.is_supported_image("/site-photo-inbox/a.heic") is False


def test_download_dropbox_inbox_creates_staging_dir_when_inbox_is_empty(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(sync_dropbox_inbox, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        sync_dropbox_inbox, "list_remote_images", lambda token, root: []
    )

    staging_dir = tmp_path / "dropbox-inbox"
    manifest_file = tmp_path / "archive-manifest.json"
    downloaded = sync_dropbox_inbox.download_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        archive_root=PurePosixPath("/site-photo-archive"),
        manifest_file=manifest_file,
    )

    assert downloaded == 0
    assert staging_dir.exists()
    assert json.loads(manifest_file.read_text(encoding="utf-8")) == []


def test_download_dropbox_inbox_writes_manifest_for_later_archive(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(sync_dropbox_inbox, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        sync_dropbox_inbox,
        "list_remote_images",
        lambda token, root: [
            {"path_display": "/site-photo-inbox/iphone/a.jpg", "path_lower": "a"}
        ],
    )

    def fake_download(token, source_path, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"img")

    monkeypatch.setattr(
        sync_dropbox_inbox,
        "download_remote_file",
        fake_download,
    )

    staging_dir = tmp_path / "dropbox-inbox"
    manifest_file = tmp_path / "archive-manifest.json"

    downloaded = sync_dropbox_inbox.download_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        archive_root=PurePosixPath("/site-photo-archive"),
        manifest_file=manifest_file,
    )

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert downloaded == 1
    assert (staging_dir / "iphone" / "a.jpg").exists()
    assert manifest == [
        {
            "source_path": "/site-photo-inbox/iphone/a.jpg",
            "archive_path": "/site-photo-archive/iphone/a.jpg",
        }
    ]


def test_archive_dropbox_inbox_moves_manifest_entries(monkeypatch, tmp_path):
    manifest_file = tmp_path / "archive-manifest.json"
    manifest_file.write_text(
        json.dumps(
            [
                {
                    "source_path": "/site-photo-inbox/street/frame.webp",
                    "archive_path": "/site-photo-archive/street/frame.webp",
                }
            ]
        ),
        encoding="utf-8",
    )

    moved_paths = []
    monkeypatch.setattr(sync_dropbox_inbox, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        sync_dropbox_inbox,
        "move_remote_file",
        lambda token, source_path, destination_path: moved_paths.append(
            (token, source_path, destination_path)
        ),
    )

    archived = sync_dropbox_inbox.archive_dropbox_inbox(manifest_file)

    assert archived == 1
    assert moved_paths == [
        (
            "token",
            "/site-photo-inbox/street/frame.webp",
            PurePosixPath("/site-photo-archive/street/frame.webp"),
        )
    ]
