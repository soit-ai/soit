"""Layer decomposition on Volcengine Ark.

Ark serves layer decomposition from its image generation endpoint: the source
image goes in with ``layer_decomposition`` set, and the answer lists a base
image (``z_index`` 0) followed by one transparent PNG per lifted element, each
with where it sits on the source. LiteLLM's image request has no place for the
flag and its response keeps none of the layer fields, so this module speaks
Ark's request directly. It holds no policy: admission, retries, pricing and
storage stay with the gateway and the image service.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from app.adapters.llm.upstream_ids import header_id
from app.kernel.commons.errors import KernelError, ValidationError
from app.kernel.ports.llm.interface import (
    DecomposedLayer,
    GeneratedImage,
    ImageDecompositionResponse,
    TextLine,
    TextRun,
    TextStyle,
)

VOLCENGINE_PROVIDER = "volcengine"

# The resolution tiers Ark's layer decomposition takes.
SIZES = frozenset({"1K", "1.5K", "2K", "auto"})

# Ark counts the base image in ``max_images``; SOIT's ``max_layers`` does not.
MAX_LAYERS = 99

# Ark answers with its request id in either header, depending on the gateway.
_REQUEST_ID_HEADERS = ("x-request-id", "x-tt-logid")

Poster = Callable[[str, dict[str, str], dict[str, Any], float | None], Awaitable[httpx.Response]]


class ArkRequestError(Exception):
    """Ark refused or failed the call.

    ``status_code`` is what the gateway's retry policy reads; the message keeps
    Ark's own code so an operator can look it up.
    """

    def __init__(self, status_code: int, code: str | None, message: str) -> None:
        super().__init__(f"Ark returned {status_code} {code or ''}: {message}".strip())
        self.status_code = status_code
        self.code = code


def supports_layer_decomposition(litellm_provider: str | None) -> bool:
    """Whether a provider configured with this LiteLLM prefix is served here."""
    return litellm_provider == VOLCENGINE_PROVIDER


def validate_decomposition_request(
    *, size: str | None, max_layers: int | None, model: str
) -> None:
    """Refuse what Ark's layer decomposition would refuse, before anything is billed."""
    if size is not None and size not in SIZES:
        raise KernelError(
            "MODEL_IMAGE_CAPABILITY_UNAVAILABLE",
            f"Layer decomposition takes a size of {', '.join(sorted(SIZES))}",
            {"model": model, "param": "size", "reason": "size_not_supported"},
        )
    if max_layers is not None and not 1 <= max_layers <= MAX_LAYERS:
        raise ValidationError(
            f"max_layers must be between 1 and {MAX_LAYERS}",
            {"param": "max_layers"},
        )


async def _post(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout: float | None
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        return await client.post(url, headers=headers, json=body)


def _media_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise ValidationError(
        "Layer decomposition takes a PNG or JPEG source image",
        {"param": "image", "reason": "unsupported_image_format"},
    )


def build_request(
    *,
    model_name: str,
    image: bytes,
    prompt: str | None,
    max_layers: int | None,
    text_recognition: bool,
    size: str | None,
    response_format: str | None,
) -> dict[str, Any]:
    """Ark's request body for one decomposition."""
    encoded = base64.b64encode(image).decode("ascii")
    body: dict[str, Any] = {
        "model": model_name,
        "image": f"data:{_media_type(image)};base64,{encoded}",
        "layer_decomposition": True,
        # Ark stamps a visible mark on its output unless told not to; a layer
        # carrying one would be pasted back into the caller's composition.
        "watermark": False,
        "response_format": "url" if response_format == "url" else "b64_json",
    }
    if prompt:
        body["prompt"] = prompt
    if size is not None:
        body["size"] = size
    options: dict[str, Any] = {}
    if max_layers is not None:
        options["max_images"] = max_layers + 1
    if text_recognition:
        options["text_recognition"] = True
    if options:
        body["layer_decomposition_options"] = options
    return body


def _box(value: Any) -> tuple[int, int, int, int] | None:
    if isinstance(value, Mapping):
        value = value.get("absolute")
    if not isinstance(value, list | tuple) or len(value) != 4:
        return None
    try:
        left, top, right, bottom = (int(round(float(v))) for v in value)
    except (TypeError, ValueError):
        return None
    return (left, top, right, bottom)


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _flag(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _style(raw: Any) -> TextStyle:
    if not isinstance(raw, Mapping):
        return TextStyle()
    return TextStyle(
        font_family=_text(raw.get("similar_font_family")),
        color=_text(raw.get("foreground_color")),
        bold=_flag(raw.get("bold")),
        italic=_flag(raw.get("italic")),
        underline=_flag(raw.get("underline")),
        strikethrough=_flag(raw.get("strikethrough")),
        shadow=_flag(raw.get("shadow")),
        translucent=_flag(raw.get("translucent")),
    )


def _text_lines(raw: Any) -> list[TextLine]:
    lines: list[TextLine] = []
    if not isinstance(raw, Mapping):
        return lines
    for line in raw.get("lines") or []:
        if not isinstance(line, Mapping):
            continue
        runs = [
            TextRun(text=str(run.get("text") or ""), style=_style(run.get("style")))
            for run in line.get("runs") or []
            if isinstance(run, Mapping)
        ]
        text = _text(line.get("text")) or "".join(run.text for run in runs)
        lines.append(TextLine(text=text, bounding_box=_box(line.get("bounding_box")), runs=runs))
    return lines


def _image(item: Mapping[str, Any]) -> GeneratedImage:
    return GeneratedImage(b64_json=_text(item.get("b64_json")), url=_text(item.get("url")))


def parse_response(
    payload: Mapping[str, Any],
    *,
    model_name: str,
    text_recognition: bool,
    request_id: str | None,
) -> ImageDecompositionResponse:
    """Read Ark's answer into the port's shape.

    Ark marks the base with ``z_index`` 0; the layers follow in stacking
    order. An answer without a base, or with an image carrying neither bytes
    nor a link, is not a decomposition the caller could rebuild.
    """
    items = [item for item in payload.get("data") or [] if isinstance(item, Mapping)]
    base_item = next((item for item in items if item.get("z_index") in (0, None)), None)
    if base_item is None:
        raise KernelError(
            "IMAGE_UNDELIVERABLE", "The provider returned no base image for the decomposition"
        )
    layers: list[DecomposedLayer] = []
    for item in items:
        if item is base_item:
            continue
        z_index = item.get("z_index")
        layer = DecomposedLayer(
            image=_image(item),
            z_index=z_index if isinstance(z_index, int) else len(layers) + 1,
            bounding_box=_box(item.get("bounding_box")),
            name=_text(item.get("name")),
            description=_text(item.get("description")),
            size=_text(item.get("size")),
        )
        # Ark puts recognized text on the layer that shows it; layers with
        # no text carry no entry, and are left with none here.
        recognized = item.get("text_recognition") if text_recognition else None
        if isinstance(recognized, Mapping):
            layer.text_lines = _text_lines(recognized)
            layer.text = _text(recognized.get("text")) or (
                "\n".join(line.text for line in layer.text_lines) or None
            )
        layers.append(layer)
    layers.sort(key=lambda layer: layer.z_index)
    response = ImageDecompositionResponse(
        base=_image(base_item),
        layers=layers,
        base_size=_text(base_item.get("size")),
        model=_text(payload.get("model")) or model_name,
        upstream_request_id=request_id,
    )
    if any(not (image.b64_json or image.url) for image in response.images):
        raise KernelError(
            "IMAGE_UNDELIVERABLE", "The provider returned a layer with no image"
        )
    return response


async def decompose(
    *,
    api_base: str | None,
    api_key: str | None,
    model_name: str,
    image: bytes,
    prompt: str | None,
    max_layers: int | None,
    text_recognition: bool,
    size: str | None,
    response_format: str | None,
    timeout: float | None,
    post: Poster | None = None,
) -> ImageDecompositionResponse:
    """Ask Ark for one decomposition and read its answer."""
    if not api_base:
        # The base URL is what the egress policy authorized; a default here
        # would send the call somewhere no one approved.
        raise ValidationError(
            "Layer decomposition needs the provider's base URL configured",
            {"param": "base_url", "reason": "base_url_required"},
        )
    if not api_key:
        raise KernelError("MODEL_PROVIDER_CREDENTIAL_REQUIRED", "Provider credential is required")
    validate_decomposition_request(size=size, max_layers=max_layers, model=model_name)
    body = build_request(
        model_name=model_name,
        image=image,
        prompt=prompt,
        max_layers=max_layers,
        text_recognition=text_recognition,
        size=size,
        response_format=response_format,
    )
    url = f"{api_base.rstrip('/')}/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = await (post or _post)(url, headers, body, timeout)
    request_id = header_id(response.headers, *_REQUEST_ID_HEADERS)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.status_code >= 400 or not isinstance(payload, Mapping):
        error = payload.get("error") if isinstance(payload, Mapping) else None
        error = error if isinstance(error, Mapping) else {}
        raise ArkRequestError(
            response.status_code,
            _text(error.get("code")),
            (_text(error.get("message")) or response.text or "no body")[:500],
        )
    return parse_response(
        payload,
        model_name=model_name,
        text_recognition=text_recognition,
        request_id=request_id,
    )
