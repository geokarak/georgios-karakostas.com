"""Helpers for image conversion and derivative generation.

This module handles the photo-processing part of ingest: color profile cleanup,
resizing, and writing the display and thumbnail files used by the site.
"""

import io
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

DISPLAY_MAX_EDGE = 2200
THUMBNAIL_MAX_EDGE = 900
DERIVATIVE_FORMAT = "WEBP"
DERIVATIVE_EXTENSION = ".webp"
DERIVATIVE_QUALITY = 82


def srgb_profile_bytes() -> bytes:
    """Build an sRGB ICC profile for saved web images."""
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    return profile.tobytes()


def convert_to_srgb(
    image: Image.Image, icc_profile: bytes | None
) -> tuple[Image.Image, bytes]:
    """Convert an image to sRGB when it already has a color profile."""
    srgb_bytes = srgb_profile_bytes()
    if not icc_profile:
        return image, srgb_bytes

    try:
        source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        target_profile = ImageCms.ImageCmsProfile(io.BytesIO(srgb_bytes))
        if image.mode == "RGBA":
            rgb_image = ImageCms.profileToProfile(
                image.convert("RGB"),
                source_profile,
                target_profile,
                outputMode="RGB",
            )
            rgb_image.putalpha(image.getchannel("A"))
            return rgb_image, srgb_bytes

        converted = ImageCms.profileToProfile(
            image,
            source_profile,
            target_profile,
            outputMode=image.mode,
        )
        return converted, srgb_bytes
    except Exception:
        return image, icc_profile


def derivative_paths(category_dir: Path, photo_id: str) -> tuple[Path, Path]:
    """Return the display and thumbnail output paths for one photo id."""
    display_file = category_dir / f"{photo_id}-display{DERIVATIVE_EXTENSION}"
    thumbnail_file = category_dir / f"{photo_id}-thumb{DERIVATIVE_EXTENSION}"
    return display_file, thumbnail_file


def save_web_derivative(
    source_file: Path, destination_file: Path, max_edge: int
) -> None:
    """Create one resized web-ready image derivative."""
    with Image.open(source_file) as image:
        icc_profile = image.info.get("icc_profile")
        rendered = ImageOps.exif_transpose(image)
        if rendered.mode not in {"RGB", "RGBA"}:
            rendered = rendered.convert("RGB")

        rendered, derivative_icc_profile = convert_to_srgb(rendered, icc_profile)

        rendered.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        save_options = {
            "format": DERIVATIVE_FORMAT,
            "quality": DERIVATIVE_QUALITY,
            "method": 6,
            "icc_profile": derivative_icc_profile,
        }
        if rendered.mode == "RGBA":
            save_options["lossless"] = False

        rendered.save(destination_file, **save_options)
