"""Image cost snapshots record the request shape (M4 part two).

The rate stays per image. What changes is the evidence: diffusion cost tracks
resolution and step count, so a ledger that records only a count cannot explain
itself. Four 4096px images and four 256px images bill identically today, and
without the shape there is nothing in the row to show the difference.
"""

from decimal import Decimal

from app.kernel.ports.llm.policy import _image_pricing


def _priced() -> dict:
    return {"currency": "USD", "image": "0.04"}


class TestQuantities:
    def test_count_is_recorded_as_before(self):
        snapshot = _image_pricing({}, image_count=3).snapshot
        assert snapshot["quantities"]["images"] == 3
        assert snapshot["billing_basis"] == "images"

    def test_size_is_recorded_when_given(self):
        snapshot = _image_pricing({}, image_count=1, size="2048x2048").snapshot
        assert snapshot["quantities"]["size"] == "2048x2048"

    def test_quality_and_steps_are_recorded_when_given(self):
        snapshot = _image_pricing(
            {}, image_count=1, quality="hd", steps=40
        ).snapshot
        assert snapshot["quantities"]["quality"] == "hd"
        assert snapshot["quantities"]["steps"] == 40

    def test_absent_shape_is_omitted_rather_than_guessed(self):
        # A provider default we did not observe must not be written into the
        # ledger as though the caller asked for it.
        quantities = _image_pricing({}, image_count=1).snapshot["quantities"]
        assert set(quantities) == {"images"}

    def test_zero_steps_is_still_recorded(self):
        quantities = _image_pricing({}, image_count=1, steps=0).snapshot["quantities"]
        assert quantities["steps"] == 0


class TestPricingIsUnchanged:
    def test_the_rate_is_still_per_image(self):
        calculation = _image_pricing(_priced(), image_count=4, size="4096x4096")
        assert calculation.amount == Decimal("0.16")
        assert calculation.currency == "USD"

    def test_shape_does_not_alter_the_amount(self):
        small = _image_pricing(_priced(), image_count=2, size="256x256")
        large = _image_pricing(_priced(), image_count=2, size="4096x4096")
        assert small.amount == large.amount

    def test_unpriced_routes_stay_auditable(self):
        snapshot = _image_pricing({}, image_count=2, size="1024x1024").snapshot
        assert snapshot["priced"] is False
        assert snapshot["reason"] == "pricing_not_configured"
        # The shape is evidence even when no rate is configured.
        assert snapshot["quantities"]["size"] == "1024x1024"
