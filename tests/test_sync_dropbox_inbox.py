import json
from pathlib import PurePosixPath

import pytest

from tooling.dropbox_sync import finalize as finalize_helpers
from tooling.dropbox_sync import download as download_helpers
from tooling.dropbox_sync import paths as path_helpers


def test_normalize_dropbox_path_adds_leading_slash():
    assert path_helpers.normalize_dropbox_path("site-photo-inbox") == PurePosixPath(
        "/site-photo-inbox"
    )


def test_dropbox_paths_preserve_relative_structure():
    inbox_root = PurePosixPath("/site-photo-inbox")
    source_path = "/site-photo-inbox/street/frame.webp"

    assert path_helpers.relative_dropbox_path(source_path, inbox_root) == PurePosixPath(
        "street/frame.webp"
    )
    assert path_helpers.quarantine_destination(
        source_path,
        inbox_root,
        PurePosixPath("/site-photo-quarantine"),
    ) == PurePosixPath("/site-photo-quarantine/street/frame.webp")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/site-photo-inbox/a.JPG", True),
        ("/site-photo-inbox/a.heic", False),
    ],
)
def test_is_supported_image_filters_extensions(path, expected):
    assert path_helpers.is_supported_image(path) is expected


def test_download_dropbox_inbox_creates_staging_dir_when_inbox_is_empty(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(download_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(download_helpers, "list_dropbox_images", lambda token, root: [])

    staging_dir = tmp_path / "dropbox-inbox"
    state_file = tmp_path / "dropbox-sync-state.json"
    downloaded = download_helpers.download_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        state_file=state_file,
    )

    assert downloaded == 0
    assert staging_dir.exists()
    assert json.loads(state_file.read_text(encoding="utf-8")) == []


def test_download_dropbox_inbox_writes_state_file_for_later_finalize(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(download_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        download_helpers,
        "list_dropbox_images",
        lambda token, root: [
            {"path_display": "/site-photo-inbox/iphone/a.jpg", "path_lower": "a"}
        ],
    )

    def fake_download(token, source_path, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"img")

    monkeypatch.setattr(
        download_helpers,
        "download_dropbox_file",
        fake_download,
    )

    staging_dir = tmp_path / "dropbox-inbox"
    state_file = tmp_path / "dropbox-sync-state.json"

    downloaded = download_helpers.download_dropbox_inbox(
        staging_dir=staging_dir,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        state_file=state_file,
    )

    state = json.loads(state_file.read_text(encoding="utf-8"))

    assert downloaded == 1
    assert (staging_dir / "iphone" / "a.jpg").exists()
    assert state == [
        {
            "source_path": "/site-photo-inbox/iphone/a.jpg",
            "source_file": str((staging_dir / "iphone" / "a.jpg").resolve()),
        }
    ]


def test_finalize_dropbox_inbox_actions_removes_ingested_and_quarantines_skipped(
    monkeypatch, tmp_path
):
    state_file = tmp_path / "dropbox-sync-state.json"
    state_file.write_text(
        json.dumps(
            [
                {
                    "source_path": "/site-photo-inbox/street/frame.webp",
                    "source_file": "/tmp/dropbox-inbox/street/frame.webp",
                    "status": "ingested",
                },
                {
                    "source_path": "/site-photo-inbox/iphone/bad.jpg",
                    "source_file": "/tmp/dropbox-inbox/iphone/bad.jpg",
                    "status": "skipped",
                    "reason": "missing-exif-datetimeoriginal",
                },
            ]
        ),
        encoding="utf-8",
    )

    removed_paths = []
    moved_paths = []
    monkeypatch.setattr(finalize_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        finalize_helpers,
        "remove_dropbox_file",
        lambda token, source_path: removed_paths.append((token, source_path)),
    )
    monkeypatch.setattr(
        finalize_helpers,
        "move_dropbox_file",
        lambda token, source_path, destination_path: moved_paths.append(
            (token, source_path, destination_path)
        ),
    )

    finalized = finalize_helpers.finalize_dropbox_inbox_actions(
        state_file=state_file,
        inbox_root=PurePosixPath("/site-photo-inbox"),
        quarantine_root=PurePosixPath("/site-photo-quarantine"),
    )

    assert finalized == 2
    assert removed_paths == [
        (
            "token",
            "/site-photo-inbox/street/frame.webp",
        )
    ]
    assert moved_paths == [
        (
            "token",
            "/site-photo-inbox/iphone/bad.jpg",
            PurePosixPath("/site-photo-quarantine/iphone/bad.jpg"),
        ),
    ]


def test_finalize_dropbox_inbox_actions_fails_when_state_is_missing_ingest_results(
    monkeypatch, tmp_path
):
    state_file = tmp_path / "dropbox-sync-state.json"
    state_file.write_text(
        json.dumps(
            [
                {
                    "source_path": "/site-photo-inbox/street/frame.webp",
                    "source_file": "/tmp/dropbox-inbox/street/frame.webp",
                }
            ]
        ),
        encoding="utf-8",
    )

    removed_paths = []
    moved_paths = []
    monkeypatch.setattr(finalize_helpers, "require_access_token", lambda: "token")
    monkeypatch.setattr(
        finalize_helpers,
        "remove_dropbox_file",
        lambda token, source_path: removed_paths.append((token, source_path)),
    )
    monkeypatch.setattr(
        finalize_helpers,
        "move_dropbox_file",
        lambda token, source_path, destination_path: moved_paths.append(
            (token, source_path, destination_path)
        ),
    )

    with pytest.raises(RuntimeError, match="missing ingest results"):
        finalize_helpers.finalize_dropbox_inbox_actions(
            state_file=state_file,
            inbox_root=PurePosixPath("/site-photo-inbox"),
            quarantine_root=PurePosixPath("/site-photo-quarantine"),
        )

    assert removed_paths == []
    assert moved_paths == []
