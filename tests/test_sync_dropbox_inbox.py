from pathlib import PurePosixPath

from scripts import sync_dropbox_inbox


def test_normalize_dropbox_path_adds_leading_slash():
    assert sync_dropbox_inbox.normalize_dropbox_path("site-photo-inbox") == PurePosixPath(
        "/site-photo-inbox"
    )


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


def test_sync_dropbox_inbox_creates_staging_dir_when_inbox_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_dropbox_inbox, "require_access_token", lambda: "token")
    monkeypatch.setattr(sync_dropbox_inbox, "list_remote_images", lambda token, root: [])

    staging_dir = tmp_path / "dropbox-inbox"
    downloaded = sync_dropbox_inbox.sync_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        archive_root=PurePosixPath("/site-photo-archive"),
    )

    assert downloaded == 0
    assert staging_dir.exists()
