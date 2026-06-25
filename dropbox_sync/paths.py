"""Helpers for Dropbox path validation and destination planning.

This module covers the small path-related rules used by the Dropbox sync flow:
normalizing Dropbox paths, recognizing supported image files, and deciding where
accepted or rejected files should end up.
"""

from pathlib import PurePosixPath

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_dropbox_path(path: str) -> PurePosixPath:
    """Normalize a Dropbox path and require a real absolute location."""
    cleaned = path.strip()
    if not cleaned:
        raise ValueError("Dropbox path cannot be empty")

    normalized = PurePosixPath(cleaned if cleaned.startswith("/") else f"/{cleaned}")
    if normalized == PurePosixPath("."):
        raise ValueError("Dropbox path cannot resolve to the current directory")
    return normalized


def is_supported_image(path: str) -> bool:
    """Return whether a Dropbox path points to a supported image file."""
    return PurePosixPath(path).suffix.lower() in SUPPORTED_EXTENSIONS


def relative_dropbox_path(path: str, root: PurePosixPath) -> PurePosixPath:
    """Return the path of a Dropbox file relative to a chosen root."""
    return normalize_dropbox_path(path).relative_to(root)


def archive_destination(
    source_path: str,
    inbox_root: PurePosixPath,
    archive_root: PurePosixPath,
) -> PurePosixPath:
    """Build the archive destination for one accepted Dropbox file."""
    return archive_root / relative_dropbox_path(source_path, inbox_root)


def quarantine_destination(
    source_path: str,
    inbox_root: PurePosixPath,
    quarantine_root: PurePosixPath,
) -> PurePosixPath:
    """Build the quarantine destination for one rejected Dropbox file."""
    return quarantine_root / relative_dropbox_path(source_path, inbox_root)


def validate_target_root(
    name: str, inbox_root: PurePosixPath, target_root: PurePosixPath
) -> None:
    """Reject target folders that overlap the Dropbox inbox."""
    if target_root == inbox_root or target_root.is_relative_to(inbox_root):
        raise ValueError(f"{name} path must live outside the Dropbox inbox path")
