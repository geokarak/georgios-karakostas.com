"""Helpers for creating gallery page files.

This module owns the small pieces of logic needed to name, locate, and create
gallery pages when a new photo category appears.
"""

from pathlib import Path

DISPLAY_TITLE_EXCEPTIONS = {"iphone": "iPhone"}


def title_from_slug(slug: str) -> str:
    """Turn a category slug into a human-readable page title."""
    if slug in DISPLAY_TITLE_EXCEPTIONS:
        return DISPLAY_TITLE_EXCEPTIONS[slug]
    return " ".join(part.capitalize() for part in slug.split("-") if part)


def gallery_page_path(category: str, project_root: Path) -> Path:
    """Return the markdown file path for one gallery page."""
    return project_root / "content" / "pages" / f"{category}.md"


def gallery_page_content(category: str) -> str:
    """Build the default markdown content for a new gallery page."""
    title = title_from_slug(category)
    return f"title: {title}\nslug: {category}\ntemplate: gallery\n"


def ensure_gallery_page(category: str, project_root: Path, dry_run: bool) -> None:
    """Create a gallery page file when the category does not have one yet."""
    pages_dir = project_root / "content" / "pages"
    page_file = gallery_page_path(category, project_root)
    if page_file.exists():
        return

    page_content = gallery_page_content(category)

    if dry_run:
        print(f"[DRY RUN] page -> {page_file}")
        return

    pages_dir.mkdir(parents=True, exist_ok=True)
    page_file.write_text(page_content, encoding="utf-8")
