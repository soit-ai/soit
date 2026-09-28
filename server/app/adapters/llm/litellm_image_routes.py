"""What each LiteLLM image route carries of the options SOIT forwards.

LiteLLM builds an image request per provider, and an option that request has
no place for is dropped, or refused with an error of LiteLLM's own, without
SOIT hearing of it: the call answers and bills for an image that ignored the
option. This module names the route an image call takes, the way LiteLLM
picks it, and lists what that route carries, so the adapter can refuse such an
option before anything is billed.

The lists record the requests LiteLLM 1.91.1 sends; the wire tests in
tests/unit/test_litellm_image_routes_wire.py check every entry against the
real library, so an upgrade that moves an option fails there first. A route
the lists do not name carries none of the options.
"""

from __future__ import annotations

GENERATE = "generate"
EDIT = "edit"

# The options SOIT forwards by name. "n" stands for more than one image and
# "mask" for an edit mask; a single image and no mask need no route support.
GENERATE_OPTIONS = ("background", "output_format", "n", "size", "response_format")
EDIT_OPTIONS = (
    "background",
    "output_format",
    "seed",
    "strength",
    "negative_prompt",
    "n",
    "mask",
    "size",
    "response_format",
)

# A route LiteLLM reaches without an image config of its own: the providers it
# treats as OpenAI-compatible, whose generations go out as OpenAI requests.
OPENAI_COMPATIBLE_ROUTE = "openai_compatible"

# Generation routes whose provider takes OpenAI's image request. LiteLLM sends
# them an option under OpenAI's own name, which is how their API names it; on
# any other route an option counts as carried only where LiteLLM maps it to
# the provider's field, since sent under OpenAI's name it is a field that API
# does not have.
OPENAI_PROTOCOL_ROUTES = frozenset(
    {
        "GPTImageGenerationConfig",
        "DallE2ImageGenerationConfig",
        "DallE3ImageGenerationConfig",
        "AzureGPTImageGenerationConfig",
        "AzureDallE2ImageGenerationConfig",
        "AzureDallE3ImageGenerationConfig",
        "LiteLLMProxyImageGenerationConfig",
        "AzureFoundryFluxImageGenerationConfig",
        "AzureFoundryGPTImageGenerationConfig",
        "AzureFoundryDallE2ImageGenerationConfig",
        "AzureFoundryDallE3ImageGenerationConfig",
        OPENAI_COMPATIBLE_ROUTE,
        "XInferenceImageGenerationConfig",
        "CometAPIImageGenerationConfig",
        "ModelScopeImageGenerationConfig",
        "RecraftImageGenerationConfig",
    }
)


# Edit routes whose request is OpenAI's own multipart edit.
OPENAI_EDIT_ROUTES = frozenset(
    {
        "OpenAIImageEditConfig",
        "DallE2ImageEditConfig",
        "AzureImageEditConfig",
        "LiteLLMProxyImageEditConfig",
        "AzureFoundryFluxImageEditConfig",
    }
)


def _options(*names: str) -> frozenset[str]:
    return frozenset(names)


_OPENAI_GENERATION = _options("background", "output_format", "n", "size")
_OPENAI_EDIT = _options("background", "n", "mask", "size", "response_format")

_CARRIED: dict[tuple[str, str], frozenset[str]] = {
    (GENERATE, "GPTImageGenerationConfig"): _OPENAI_GENERATION,
    (GENERATE, "DallE2ImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "DallE3ImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "AzureGPTImageGenerationConfig"): _OPENAI_GENERATION,
    (GENERATE, "AzureDallE2ImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "AzureDallE3ImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "LiteLLMProxyImageGenerationConfig"): _OPENAI_GENERATION,
    (GENERATE, "AzureFoundryFluxImageGenerationConfig"): _OPENAI_GENERATION,
    (GENERATE, "AzureFoundryGPTImageGenerationConfig"): _OPENAI_GENERATION,
    (GENERATE, "AzureFoundryDallE2ImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "AzureFoundryDallE3ImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, OPENAI_COMPATIBLE_ROUTE): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "XInferenceImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "CometAPIImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "ModelScopeImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    (GENERATE, "RecraftImageGenerationConfig"): _OPENAI_GENERATION | {"response_format"},
    # Azure AI's FLUX 2 goes to Black Forest Labs' own API, which names none
    # of these the OpenAI way.
    (GENERATE, "AzureFoundryFluxImageGenerationConfig:flux2"): _options(),
    (GENERATE, "AzureFoundryMAIImageGenerationConfig"): _options("size"),
    (GENERATE, "GoogleImageGenConfig:imagen"): _options("background", "output_format", "n", "size"),
    (GENERATE, "GoogleImageGenConfig:gemini"): _options("n", "size"),
    (GENERATE, "VertexAIImagenImageGenerationConfig"): _options("n", "size"),
    (GENERATE, "VertexAIGeminiImageGenerationConfig"): _options("n", "size"),
    # DashScope nests other options where it does not read them.
    (GENERATE, "DashScopeImageGenerationConfig"): _options("n", "size"),
    (GENERATE, "OpenRouterImageGenerationConfig"): _options("size"),
    (GENERATE, "AmazonStabilityConfig"): _options("size"),
    (GENERATE, "AmazonStability3Config"): _options(),
    (GENERATE, "AmazonTitanImageGenerationConfig"): _options("n", "size"),
    (GENERATE, "AmazonNovaCanvasConfig"): _options("n", "size"),
    # Stability maps a size to one of its aspect ratios, and drops others.
    (GENERATE, "StabilityImageGenerationConfig"): _options("output_format", "size"),
    (GENERATE, "BlackForestLabsImageGenerationConfig"): _options("size"),
    (GENERATE, "BlackForestLabsImageGenerationConfig:ultra"): _options("n", "size"),
    (GENERATE, "FalAIImageGenerationConfig"): _options(),
    (GENERATE, "FalAIImagen4Config"): _options("n", "size"),
    (GENERATE, "FalAINanoBananaConfig"): _options("n", "size"),
    (GENERATE, "FalAIFluxProV11Config"): _options("n", "size"),
    (GENERATE, "FalAIFluxProV11UltraConfig"): _options("n", "size"),
    (GENERATE, "FalAIFluxSchnellConfig"): _options("n", "size"),
    (GENERATE, "FalAIBytedanceSeedreamV3Config"): _options("n", "size"),
    (GENERATE, "FalAIBytedanceDreaminaV31Config"): _options("n", "size"),
    (GENERATE, "FalAIIdeogramV3Config"): _options("n", "size"),
    (GENERATE, "FalAIStableDiffusionConfig"): _options("n", "size"),
    (GENERATE, "FalAIRecraftV3Config"): _options("size"),
    (GENERATE, "FalAIBriaConfig"): _options("size"),
    (GENERATE, "AimlImageGenerationConfig"): _options("n", "size", "response_format"),
    (GENERATE, "RunwayMLImageGenerationConfig"): _options("size"),
    (EDIT, "OpenAIImageEditConfig"): _OPENAI_EDIT,
    (EDIT, "DallE2ImageEditConfig"): _OPENAI_EDIT,
    (EDIT, "AzureImageEditConfig"): _OPENAI_EDIT,
    (EDIT, "LiteLLMProxyImageEditConfig"): _OPENAI_EDIT,
    (EDIT, "AzureFoundryFluxImageEditConfig"): _OPENAI_EDIT,
    (EDIT, "AzureFoundryFlux2ImageEditConfig"): _options("n", "size"),
    (EDIT, "AzureFoundryMAIImageEditConfig"): _options("n", "size"),
    (EDIT, "GeminiImageEditConfig:imagen"): _options("n"),
    (EDIT, "GeminiImageEditConfig:gemini"): _options("n", "size"),
    (EDIT, "OpenRouterImageEditConfig"): _options("n", "size"),
    (EDIT, "RecraftImageEditConfig"): _options("n", "response_format"),
    (EDIT, "BedrockAmazonNovaCanvasImageEditConfig"): _options("seed", "n", "mask", "size"),
    (EDIT, "BedrockStabilityImageEditConfig"): _options(
        "output_format", "seed", "strength", "negative_prompt", "mask", "size"
    ),
    (EDIT, "StabilityImageEditConfig"): _options(
        "seed", "strength", "negative_prompt", "mask", "size"
    ),
    # Its option list has no mask, so even the fill model is sent none.
    (EDIT, "BlackForestLabsImageEditConfig"): _options("output_format", "seed"),
    (EDIT, "VertexAIImagenImageEditConfig"): _options("n", "mask"),
    (EDIT, "VertexAIGeminiImageEditConfig"): _options("size"),
}


# Providers LiteLLM finds only by signing in: placing a model of theirs starts
# a device login over the network, so their prefix is taken as it stands.
_SIGN_IN_PREFIXES = frozenset({"chatgpt", "github_copilot"})


def image_route(model: str, operation: str) -> str | None:
    """The LiteLLM route an image call to ``model`` takes, or None if it has none.

    ``model`` is LiteLLM's ``prefix/name``. The route is the image config
    LiteLLM itself selects for the provider and model, so a model name picks
    the same one here as in the call; where a config branches on the model
    name, the branch is part of the route.
    """
    try:
        import litellm
        from litellm.types.utils import LlmProviders
        from litellm.utils import ProviderConfigManager

        prefix, _, name = model.partition("/")
        if prefix not in _SIGN_IN_PREFIXES:
            name, prefix, _key, _base = litellm.get_llm_provider(model=model)
        provider = LlmProviders(prefix)
    except Exception:  # noqa: BLE001 - LiteLLM raises its own errors for a model it cannot place
        return None
    try:
        if operation == EDIT:
            config = ProviderConfigManager.get_provider_image_edit_config(
                model=name, provider=provider
            )
            if config is None:
                return None
            return type(config).__name__ + _branch(type(config).__name__, name)
        if provider == LlmProviders.BEDROCK:
            from litellm.llms.bedrock.image_generation.image_handler import (
                BedrockImageGeneration,
            )

            return BedrockImageGeneration.get_config_class(model=name).__name__
        config = ProviderConfigManager.get_provider_image_generation_config(
            model=name, provider=provider
        )
    except ValueError:
        return None
    if config is None:
        return OPENAI_COMPATIBLE_ROUTE if prefix in litellm.openai_compatible_providers else None
    return type(config).__name__ + _branch(type(config).__name__, name)


def _branch(route: str, name: str) -> str:
    """The branch a config takes on the model name, where it takes one."""
    if route in ("GoogleImageGenConfig", "GeminiImageEditConfig"):
        from litellm.llms.gemini.common_utils import is_gemini_image_model

        return ":gemini" if is_gemini_image_model(name) else ":imagen"
    if route == "BlackForestLabsImageGenerationConfig":
        return ":ultra" if "ultra" in name.lower() else ""
    if route == "AzureFoundryFluxImageGenerationConfig":
        from litellm.llms.azure_ai.image_generation.flux_transformation import (
            AzureFoundryFluxImageGenerationConfig,
        )

        return ":flux2" if AzureFoundryFluxImageGenerationConfig.is_flux2_model(name) else ""
    return ""


def takes_openai_sizes(route: str | None, operation: str) -> bool:
    """Whether the route passes a size on as OpenAI's API reads it, ``auto`` included.

    Other routes carry a size by turning it into dimensions or an aspect ratio
    of their own, which ``auto`` is not.
    """
    if operation == EDIT:
        return route in OPENAI_EDIT_ROUTES
    return route in OPENAI_PROTOCOL_ROUTES


def is_listed(route: str | None, operation: str) -> bool:
    """Whether the table records ``route`` at all for ``operation``."""
    return route is not None and (operation, route) in _CARRIED


def carried_options(route: str | None, operation: str) -> frozenset[str]:
    """The options ``route`` sends on ``operation``; none for a route not listed."""
    if route is None:
        return frozenset()
    return _CARRIED.get((operation, route), frozenset())


def listed_routes() -> list[tuple[str, str]]:
    """Every (operation, route) the lists name, for the tests that check them."""
    return sorted(_CARRIED)
