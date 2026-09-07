"""Image capability declarations and pre-flight refusals (M3).

These cover the contract the requirement calls "fast failure": a request the
routed model has declared it cannot serve is refused by SOIT with one code,
before the provider is called and before anything is billed.
"""

import pytest

from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.runtime_config import (
    IMAGE_CAPABILITY_DEFAULTS,
    PROVIDER_CAPABILITY_PRESETS,
    normalize_image_capabilities,
    parse_image_size,
    validate_image_request,
)
from app.middleware.error_handler import ERROR_CODE_TO_STATUS


class TestCapabilityPresets:
    def test_image_flags_exist_for_every_provider_kind(self):
        # Without these the router's fallback answers False for image routes,
        # which is how generation came to depend on a hand-set matrix entry.
        for kind, preset in PROVIDER_CAPABILITY_PRESETS.items():
            assert "image_generation" in preset, kind
            assert "image_edit" in preset, kind

    def test_openai_declares_both_image_capabilities(self):
        assert PROVIDER_CAPABILITY_PRESETS["openai"]["image_generation"] is True
        assert PROVIDER_CAPABILITY_PRESETS["openai"]["image_edit"] is True

    def test_chat_only_kinds_declare_no_image_support(self):
        for kind in ("anthropic", "deepseek", "ollama"):
            assert PROVIDER_CAPABILITY_PRESETS[kind]["image_generation"] is False
            assert PROVIDER_CAPABILITY_PRESETS[kind]["image_edit"] is False

    def test_edit_is_off_where_the_gateway_has_no_edit_branch(self):
        # LiteLLM 1.91 routes image edits for openai / bedrock / stability /
        # black_forest_labs only. Declaring edit elsewhere would trade our
        # error for the vendor's.
        for kind in ("gemini", "openrouter", "dashscope"):
            assert PROVIDER_CAPABILITY_PRESETS[kind]["image_generation"] is True
            assert PROVIDER_CAPABILITY_PRESETS[kind]["image_edit"] is False


class TestNormalizeImageCapabilities:
    def test_absent_document_yields_all_unknown(self):
        assert normalize_image_capabilities(None) == IMAGE_CAPABILITY_DEFAULTS
        assert normalize_image_capabilities({}) == IMAGE_CAPABILITY_DEFAULTS

    def test_non_dict_image_entry_is_ignored(self):
        assert normalize_image_capabilities({"image": "yes"}) == IMAGE_CAPABILITY_DEFAULTS

    def test_declared_traits_are_read(self):
        traits = normalize_image_capabilities(
            {
                "image": {
                    "mask": True,
                    "transparent_background": False,
                    "max_dimension": 2048,
                    "supports_seed": True,
                }
            }
        )
        assert traits == {
            "mask": True,
            "transparent_background": False,
            "max_dimension": 2048,
            "supports_seed": True,
        }

    def test_string_support_values_are_accepted(self):
        traits = normalize_image_capabilities(
            {"image": {"mask": "supported", "supports_seed": "unsupported"}}
        )
        assert traits["mask"] is True
        assert traits["supports_seed"] is False

    def test_unreadable_trait_stays_unknown_rather_than_refusing(self):
        # A bad catalog entry must not take a working model offline.
        traits = normalize_image_capabilities({"image": {"mask": {"nested": 1}}})
        assert traits["mask"] is None

    @pytest.mark.parametrize("value", [0, -1, "wide", None, True])
    def test_unusable_max_dimension_is_unknown(self, value):
        traits = normalize_image_capabilities({"image": {"max_dimension": value}})
        assert traits["max_dimension"] is None


class TestParseImageSize:
    def test_parses_pixels(self):
        assert parse_image_size("1024x768") == (1024, 768)

    def test_absent_size_is_none(self):
        assert parse_image_size(None) is None
        assert parse_image_size("") is None

    def test_malformed_size_is_rejected(self):
        with pytest.raises(ValidationError):
            parse_image_size("big")


class TestValidateImageRequest:
    def test_undeclared_model_is_routed_unchanged(self):
        # Backwards compatibility: models that never declared traits keep
        # behaving exactly as they did before the fields existed.
        validate_image_request(
            None, model="model:openai:gpt-image-1", size="4096x4096", has_mask=True,
            background="transparent", seed=7,
        )

    def test_mask_is_refused_when_declared_unsupported(self):
        with pytest.raises(KernelError) as exc:
            validate_image_request(
                {"mask": False}, model="model:openai:x", has_mask=True
            )
        assert exc.value.code == "MODEL_IMAGE_CAPABILITY_UNAVAILABLE"
        assert exc.value.details["capability"] == "mask"

    def test_mask_passes_when_supported(self):
        validate_image_request({"mask": True}, model="model:openai:x", has_mask=True)

    def test_transparent_background_is_refused_when_unsupported(self):
        with pytest.raises(KernelError) as exc:
            validate_image_request(
                {"transparent_background": False},
                model="model:openai:x",
                background="transparent",
            )
        assert exc.value.details["capability"] == "transparent_background"

    def test_opaque_background_is_never_refused(self):
        validate_image_request(
            {"transparent_background": False},
            model="model:openai:x",
            background="opaque",
        )

    def test_seed_is_refused_when_unsupported(self):
        with pytest.raises(KernelError) as exc:
            validate_image_request(
                {"supports_seed": False}, model="model:openai:x", seed=42
            )
        assert exc.value.details["capability"] == "supports_seed"

    def test_seed_zero_is_still_a_seed(self):
        # 0 is a legitimate seed; treating it as "unset" would silently drop a
        # value the caller asked to reproduce with.
        with pytest.raises(KernelError):
            validate_image_request(
                {"supports_seed": False}, model="model:openai:x", seed=0
            )

    def test_size_beyond_max_dimension_is_refused(self):
        with pytest.raises(KernelError) as exc:
            validate_image_request(
                {"max_dimension": 1024}, model="model:openai:x", size="2048x1024"
            )
        assert exc.value.details["capability"] == "max_dimension"
        assert exc.value.details["max_dimension"] == 1024
        assert exc.value.details["requested"] == "2048x1024"

    def test_size_within_max_dimension_passes(self):
        validate_image_request(
            {"max_dimension": 2048}, model="model:openai:x", size="2048x1024"
        )


class TestErrorMapping:
    def test_capability_refusals_are_structured_4xx(self):
        # The requirement is a structured 4xx rather than a 500 carrying each
        # provider's own wording.
        for code in (
            "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
            "MODEL_CAPABILITY_UNAVAILABLE",
        ):
            assert 400 <= ERROR_CODE_TO_STATUS[code] < 500
