""" service

One execution path for governed image jobs.

Generation and editing differ only in which gateway method they call and what
they send; everything after that — how results are returned, how the run is
closed, what evidence is written — is identical, so it lives here once and both
the synchronous request and the detached worker call the same function.

Returning results as run artifacts exists because the inline shape has a
ceiling: four 2048px images are 10-16 MB of base64 in one response body, which
a gateway in front of the API will cut before the provider has finished. An
artifact moves the bytes into governed storage and leaves the caller a run to
poll, which is also what makes the request survivable when the provider takes
minutes.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.kernel.commons.errors import ForbiddenError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ImageGenerationResponse, LLMPort
from app.kernel.ports.safety.interface import (
    ContentSafetyPort,
    SafetyDecision,
    SafetyDirection,
)
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.runtime.runs.writer import TraceWriter

RESPONSE_FORMATS = ("b64_json", "url", "artifact")

_OUTPUT_MIME = {
    "png": "image/png",
    "webp": "image/webp",
}


@dataclass(frozen=True)
class ImageJobRequest:
    """Everything one image call needs, independent of how it was submitted."""

    kind: str
    """Either ``generate`` or ``edit``."""

    model: str
    prompt: str
    n: int = 1
    size: str | None = None
    response_format: str = "b64_json"
    output_format: str = "png"
    image: bytes | None = None
    mask: bytes | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ("generate", "edit"):
            raise ValidationError(f"Unsupported image job kind: {self.kind}")
        if self.kind == "edit" and not self.image:
            raise ValidationError("An image edit requires a source image")

    @property
    def summary(self) -> str:
        masked = "yes" if self.mask else "no"
        base = f"model={self.model}, n={self.n}"
        if self.kind == "edit":
            base = f"{base}, mask={masked}"
        return f"{base}, prompt={self.prompt[:200]}"


@dataclass(frozen=True)
class ImageResult:
    """One returned image, in whichever shape the caller asked for."""

    b64_json: str | None = None
    url: str | None = None
    attachment_id: str | None = None


@dataclass(frozen=True)
class ImageJobOutcome:
    model: str | None
    results: list[ImageResult]
    safety: list[dict[str, Any]] = field(default_factory=list)
    """What the content check found, recorded as run evidence."""


def _gateway_kwargs(request: ImageJobRequest, run_id: str) -> dict[str, Any]:
    kwargs = dict(request.extra)
    kwargs["run_id"] = run_id
    # Providers know nothing about artifacts: that is SOIT's own return shape,
    # so the wire request always asks for inline bytes we can store ourselves.
    kwargs["response_format"] = (
        "b64_json" if request.response_format == "artifact" else request.response_format
    )
    if request.kind == "edit":
        kwargs["output_format"] = request.output_format
    return kwargs


async def _call_gateway(
    llm_port: LLMPort,
    request: ImageJobRequest,
    run_id: str,
) -> ImageGenerationResponse:
    kwargs = _gateway_kwargs(request, run_id)
    if request.kind == "edit":
        return await llm_port.edit_image(
            image=request.image,
            prompt=request.prompt,
            model=request.model,
            mask=request.mask,
            n=request.n,
            size=request.size,
            **kwargs,
        )
    return await llm_port.generate_image(
        prompt=request.prompt,
        model=request.model,
        n=request.n,
        size=request.size,
        **kwargs,
    )


def _decode(b64_json: str) -> bytes:
    try:
        return base64.b64decode(b64_json, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("Provider returned an undecodable image") from exc


async def _store_as_artifacts(
    response: ImageGenerationResponse,
    *,
    ctx: RequestContext,
    trace_writer: TraceWriter,
    storage_port: StoragePort,
    run_id: str,
    request: ImageJobRequest,
) -> list[ImageResult]:
    mime = _OUTPUT_MIME.get(request.output_format, "image/png")
    results: list[ImageResult] = []
    for index, image in enumerate(response.images):
        if not image.b64_json:
            # A provider that answered with a URL has kept the bytes; there is
            # nothing to store, so the caller is handed the URL unchanged
            # rather than a broken artifact reference.
            results.append(ImageResult(url=image.url))
            continue
        data = _decode(image.b64_json)
        storage_key = (
            f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}"
            f"/runs/{run_id}/images/{index}.{request.output_format}"
        )
        await storage_port.put(
            storage_key,
            data,
            content_type=mime,
            metadata={"run_id": run_id, "index": str(index)},
        )
        artifact = trace_writer.create_artifact(
            run_id=run_id,
            artifact_type="file",
            storage_key=storage_key,
            mime=mime,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            meta={
                "kind": "image",
                "index": index,
                "name": f"{index}.{request.output_format}",
                "operation": (
                    "edit_image" if request.kind == "edit" else "generate_image"
                ),
            },
        )
        results.append(ImageResult(attachment_id=artifact.id))
    return results


async def _inspect_results(
    response: ImageGenerationResponse,
    *,
    content_safety: ContentSafetyPort | None,
    request: ImageJobRequest,
    run_id: str,
) -> list[dict[str, Any]]:
    """Check the produced images and return what the check found.

    Runs before results are stored or returned, so a blocked image never
    reaches the caller and never becomes a durable artifact. A deployment with
    no classifier records nothing here, which the port states as "no such
    capability" rather than as an all-clear.
    """
    if content_safety is None:
        return []

    evidence: list[dict[str, Any]] = []
    media_type = _OUTPUT_MIME.get(request.output_format, "image/png")
    for index, image in enumerate(response.images):
        if not image.b64_json:
            # A provider-hosted URL means the bytes never reached us; saying so
            # is more honest than reporting an image we did not look at.
            evidence.append(
                {
                    "index": index,
                    "decision": "not_inspected",
                    "reason": "provider_hosted_url",
                }
            )
            continue

        verdict = await content_safety.inspect_image(
            _decode(image.b64_json),
            direction=SafetyDirection.OUTBOUND,
            media_type=media_type,
            run_id=run_id,
        )
        if verdict.findings:
            evidence.append(
                {
                    **verdict.evidence(),
                    "direction": SafetyDirection.OUTBOUND.value,
                    "index": index,
                }
            )
        if verdict.decision is SafetyDecision.BLOCK:
            raise ForbiddenError(
                "Generated image refused by the content safety policy",
                {
                    "direction": SafetyDirection.OUTBOUND.value,
                    "provider": verdict.provider,
                    "index": index,
                    "categories": [finding.category for finding in verdict.findings],
                },
            )
    return evidence


async def execute_image_job(
    request: ImageJobRequest,
    *,
    run_id: str,
    ctx: RequestContext,
    llm_port: LLMPort,
    trace_writer: TraceWriter,
    storage_port: StoragePort | None = None,
    content_safety: ContentSafetyPort | None = None,
) -> ImageJobOutcome:
    """Run one image job against an already-open run.

    The run is left open: the caller closes it, because the synchronous path
    and the detached worker commit on different sessions.
    """
    if request.response_format == "artifact" and storage_port is None:
        raise ValidationError("Artifact responses require governed storage")

    response = await _call_gateway(llm_port, request, run_id)

    safety = await _inspect_results(
        response,
        content_safety=content_safety,
        request=request,
        run_id=run_id,
    )

    if request.response_format == "artifact":
        results = await _store_as_artifacts(
            response,
            ctx=ctx,
            trace_writer=trace_writer,
            storage_port=storage_port,
            run_id=run_id,
            request=request,
        )
    else:
        results = [
            ImageResult(b64_json=image.b64_json, url=image.url)
            for image in response.images
        ]

    return ImageJobOutcome(model=response.model, results=results, safety=safety)
