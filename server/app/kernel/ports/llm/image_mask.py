""" image_mask

Mask conventions for governed image edits.

Two conventions are in use and they are exact opposites. Stable Diffusion and
the tools built on it treat **white as the region to repaint**. OpenAI's edit
endpoint treats **transparent as the region to edit**, and ignores colour
entirely. Guessing wrong does not degrade the result, it inverts it: the whole
picture is repainted and the one region the caller selected is preserved.

SOIT therefore fixes one convention at its own boundary — white is the edit
region — and converts per provider here, so a caller's mask means the same
thing whichever model the route lands on.
"""

from __future__ import annotations

import io

from app.kernel.commons.errors import ValidationError

# Above this the pixel counts as "selected". Anti-aliased brush edges and JPEG
# artefacts leave mid-greys around every stroke; a midpoint threshold keeps a
# soft edge on the side the caller drew it.
_SELECTED_LUMINANCE_THRESHOLD = 128

MASK_CONVENTION = "white_is_edit_region"


def _require_pillow():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ValidationError(
            "Image mask handling requires the Pillow dependency"
        ) from exc
    return Image


def mask_to_openai_alpha(mask: bytes) -> bytes:
    """Convert a white-is-edit mask into the alpha mask OpenAI expects.

    OpenAI reads only the alpha channel: transparent marks the region to
    replace. The caller's white strokes therefore become fully transparent and
    everything else becomes fully opaque.

    Returns PNG bytes, because the alpha channel has to survive the encoding
    and JPEG has none.
    """
    if not mask:
        raise ValidationError("Image mask is empty")

    Image = _require_pillow()
    try:
        with Image.open(io.BytesIO(mask)) as source:
            source.load()
            # Flatten to luminance first so a mask drawn in any mode - RGB,
            # palette, or already-alpha - is read by the same rule.
            luminance = source.convert("L")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Image mask could not be decoded: {exc}") from exc

    # Selected (white) -> alpha 0 -> "edit here". Unselected -> alpha 255.
    alpha = luminance.point(
        lambda value: 0 if value >= _SELECTED_LUMINANCE_THRESHOLD else 255
    )
    canvas = Image.new("RGBA", luminance.size, (0, 0, 0, 255))
    canvas.putalpha(alpha)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def openai_alpha_to_mask(mask: bytes) -> bytes:
    """Convert an OpenAI alpha mask into SOIT's white-is-edit mask.

    The inverse of :func:`mask_to_openai_alpha`, for callers that speak
    OpenAI's convention: transparent pixels become white (edit here), opaque
    ones black. A mask without an alpha channel carries no selection in that
    convention and is refused rather than read as all-opaque.
    """
    if not mask:
        raise ValidationError("Image mask is empty")

    Image = _require_pillow()
    try:
        with Image.open(io.BytesIO(mask)) as source:
            source.load()
            has_alpha = "A" in source.getbands() or "transparency" in source.info
            rgba = source.convert("RGBA")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Image mask could not be decoded: {exc}") from exc
    if not has_alpha:
        raise ValidationError(
            "The mask needs an alpha channel: transparent pixels mark the region to edit"
        )

    selection = rgba.getchannel("A").point(
        lambda value: 255 if value < _SELECTED_LUMINANCE_THRESHOLD else 0
    )
    buffer = io.BytesIO()
    selection.save(buffer, format="PNG")
    return buffer.getvalue()


def assert_mask_matches_image(image: bytes, mask: bytes) -> None:
    """Refuse a mask whose dimensions do not match the image.

    Providers differ on this: some resize silently, some refuse. A silent
    resize shifts the selected region, which reads as the model ignoring the
    selection rather than as a bad request.
    """
    Image = _require_pillow()
    try:
        with Image.open(io.BytesIO(image)) as source:
            image_size = source.size
        with Image.open(io.BytesIO(mask)) as source:
            mask_size = source.size
    except Exception as exc:
        raise ValidationError(f"Image or mask could not be decoded: {exc}") from exc

    if image_size != mask_size:
        raise ValidationError(
            "Image mask dimensions must match the image: "
            f"image is {image_size[0]}x{image_size[1]}, "
            f"mask is {mask_size[0]}x{mask_size[1]}"
        )


def image_dimensions(image: bytes) -> tuple[int, int]:
    """Return the pixel size of an encoded image."""
    Image = _require_pillow()
    try:
        with Image.open(io.BytesIO(image)) as source:
            return source.size
    except Exception as exc:
        raise ValidationError(f"Image could not be decoded: {exc}") from exc
