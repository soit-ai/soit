"""Mask convention conversion (M1).

The failure this guards against is not a degraded edit but an inverted one:
getting the convention backwards repaints the whole image and preserves only
the region the caller selected.
"""

import io

import pytest
from PIL import Image

from app.kernel.commons.errors import ValidationError
from app.kernel.ports.llm.image_mask import (
    MASK_CONVENTION,
    assert_mask_matches_image,
    image_dimensions,
    mask_to_openai_alpha,
    openai_alpha_to_mask,
)


def _encode(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _half_white_mask(size=(10, 10)) -> bytes:
    """Left half white (edit), right half black (keep)."""
    mask = Image.new("L", size, 0)
    for x in range(size[0] // 2):
        for y in range(size[1]):
            mask.putpixel((x, y), 255)
    return _encode(mask)


class TestMaskConvention:
    def test_the_declared_convention_is_white_is_edit(self):
        assert MASK_CONVENTION == "white_is_edit_region"

    def test_white_becomes_transparent_and_black_becomes_opaque(self):
        result = mask_to_openai_alpha(_half_white_mask())

        with Image.open(io.BytesIO(result)) as out:
            assert out.mode == "RGBA"
            alpha = out.getchannel("A")
            # Left half was white: the region OpenAI must replace, so alpha 0.
            assert alpha.getpixel((0, 0)) == 0
            assert alpha.getpixel((4, 9)) == 0
            # Right half was black: preserved, so fully opaque.
            assert alpha.getpixel((5, 0)) == 255
            assert alpha.getpixel((9, 9)) == 255

    def test_conversion_is_not_inverted(self):
        # Stated as its own case because an inverted mask is the one failure
        # that silently destroys the caller's image.
        all_white = _encode(Image.new("L", (4, 4), 255))
        all_black = _encode(Image.new("L", (4, 4), 0))

        with Image.open(io.BytesIO(mask_to_openai_alpha(all_white))) as out:
            assert out.getchannel("A").getextrema() == (0, 0)
        with Image.open(io.BytesIO(mask_to_openai_alpha(all_black))) as out:
            assert out.getchannel("A").getextrema() == (255, 255)

    def test_output_is_png_so_alpha_survives(self):
        result = mask_to_openai_alpha(_half_white_mask())
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_rgb_mask_is_read_by_luminance(self):
        mask = Image.new("RGB", (4, 4), (255, 255, 255))
        with Image.open(io.BytesIO(mask_to_openai_alpha(_encode(mask)))) as out:
            assert out.getchannel("A").getextrema() == (0, 0)

    def test_soft_brush_edges_resolve_to_one_side(self):
        # Anti-aliased strokes leave mid-greys; every pixel must end up either
        # selected or not, never partially transparent.
        gradient = Image.new("L", (256, 1))
        for x in range(256):
            gradient.putpixel((x, 0), x)

        with Image.open(io.BytesIO(mask_to_openai_alpha(_encode(gradient)))) as out:
            values = set(out.getchannel("A").getdata())
            assert values <= {0, 255}
            assert out.getchannel("A").getpixel((0, 0)) == 255
            assert out.getchannel("A").getpixel((255, 0)) == 0

    def test_palette_mask_is_accepted(self):
        mask = Image.new("P", (4, 4))
        mask.putpalette([255, 255, 255] * 256)
        with Image.open(io.BytesIO(mask_to_openai_alpha(_encode(mask)))) as out:
            assert out.getchannel("A").getextrema() == (0, 0)

    def test_empty_mask_is_rejected(self):
        with pytest.raises(ValidationError, match="empty"):
            mask_to_openai_alpha(b"")

    def test_undecodable_mask_is_rejected(self):
        with pytest.raises(ValidationError, match="could not be decoded"):
            mask_to_openai_alpha(b"not an image")


class TestMaskDimensions:
    def test_matching_dimensions_pass(self):
        image = _encode(Image.new("RGB", (10, 10), (1, 2, 3)))
        assert_mask_matches_image(image, _half_white_mask((10, 10)))

    def test_mismatched_dimensions_are_refused(self):
        # A silent provider-side resize shifts the selection, which reads as
        # the model ignoring the mask rather than as a bad request.
        image = _encode(Image.new("RGB", (10, 10), (1, 2, 3)))
        with pytest.raises(ValidationError, match="must match"):
            assert_mask_matches_image(image, _half_white_mask((8, 8)))

    def test_image_dimensions_are_reported(self):
        assert image_dimensions(_encode(Image.new("RGB", (321, 123)))) == (321, 123)

    def test_undecodable_image_is_rejected(self):
        with pytest.raises(ValidationError):
            image_dimensions(b"nope")

class TestOpenAIAlphaToMask:
    def _half_transparent(self, size=(10, 10)) -> bytes:
        mask = Image.new("RGBA", size, (0, 0, 0, 255))
        for x in range(size[0] // 2):
            for y in range(size[1]):
                mask.putpixel((x, y), (0, 0, 0, 0))
        return _encode(mask)

    def test_transparent_becomes_white_and_opaque_becomes_black(self):
        result = openai_alpha_to_mask(self._half_transparent())

        with Image.open(io.BytesIO(result)) as out:
            assert out.mode == "L"
            assert out.getpixel((0, 0)) == 255
            assert out.getpixel((9, 9)) == 0

    def test_the_round_trip_keeps_the_selection(self):
        original = self._half_transparent()

        restored = mask_to_openai_alpha(openai_alpha_to_mask(original))

        with Image.open(io.BytesIO(restored)) as out:
            alpha = out.getchannel("A")
            assert alpha.getpixel((0, 5)) == 0
            assert alpha.getpixel((9, 5)) == 255

    def test_a_mask_without_alpha_is_refused(self):
        with pytest.raises(ValidationError, match="alpha channel"):
            openai_alpha_to_mask(_half_white_mask())

    def test_an_undecodable_mask_is_refused(self):
        with pytest.raises(ValidationError):
            openai_alpha_to_mask(b"not an image")
