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
import json
from dataclasses import dataclass, field
from typing import Any

from app.kernel.commons.errors import ForbiddenError, KernelError, ValidationError
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


def resolve_response_format(requested: str | None, *, detached: bool) -> str:
    """The shape an image job returns its images in.

    A job run detached has no response to carry inline images: its results
    reach the caller only as run artifacts, fetched by polling the run. So
    ``artifact`` is what an asynchronous request without a format means, and
    one that asks for ``b64_json`` or ``url`` is refused before a run opens or
    anything is billed, rather than billed and then left with nothing to
    retrieve.
    """
    if requested is not None and requested not in RESPONSE_FORMATS:
        raise ValidationError(f"Unsupported image response_format: {requested}", {"param": "response_format"})
    if not detached:
        return requested or "b64_json"
    if requested in (None, "artifact"):
        return "artifact"
    raise ValidationError(
        "An asynchronous image job returns its images as run artifacts; "
        "omit response_format or set it to artifact",
        {"param": "response_format"},
    )


_OUTPUT_MIME = {
    "png": "image/png",
    "webp": "image/webp",
    "jpeg": "image/jpeg",
}


def _sniff_format(data: bytes) -> str | None:
    """The image format the bytes are actually in, when it is one we label.

    A provider may ignore the requested output_format, so the stored artifact
    is named and typed after what came back rather than after what was asked.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


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
    output_format: str | None = None
    """Sent to the provider only when set; ``png`` is assumed otherwise."""
    image: bytes | None = None
    mask: bytes | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ("generate", "edit"):
            raise ValidationError(f"Unsupported image job kind: {self.kind}")
        if self.kind == "edit" and not self.image:
            raise ValidationError("An image edit requires a source image")

    @property
    def file_format(self) -> str:
        return self.output_format or "png"

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
    artifact_id: str | None = None
    """The run artifact holding the image, on an ``artifact`` job."""


@dataclass(frozen=True)
class ImageJobOutcome:
    model: str | None
    results: list[ImageResult]
    safety: list[dict[str, Any]] = field(default_factory=list)
    """What the content check found, recorded as run evidence."""


def _image_options(request: ImageJobRequest) -> dict[str, Any]:
    options = dict(request.extra)
    # Providers know nothing about artifacts: that is SOIT's own return shape,
    # so the wire request always asks for inline bytes we can store ourselves.
    options["response_format"] = (
        "b64_json" if request.response_format == "artifact" else request.response_format
    )
    if request.output_format is not None:
        options["output_format"] = request.output_format
    return options


def _gateway_kwargs(request: ImageJobRequest, run_id: str) -> dict[str, Any]:
    return {**_image_options(request), "run_id": run_id}


async def check_image_job(llm_port: LLMPort, request: ImageJobRequest) -> None:
    """Refuse a job its model or route cannot serve as asked, before its run opens.

    The call makes the same checks, but by then the run is open and an
    asynchronous job has already been accepted; checked here, the caller is
    told at once and nothing is opened, admitted or billed.
    """
    await llm_port.check_image_request(
        request.model,
        operation=request.kind,
        n=request.n,
        size=request.size,
        has_mask=request.mask is not None,
        **_image_options(request),
    )


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
        # The provider's fault, found after it was paid: not a bad request.
        raise KernelError(
            "IMAGE_UNDELIVERABLE", "The provider returned an image that could not be decoded"
        ) from exc


def _images_prefix(ctx: RequestContext, run_id: str) -> str:
    return f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run_id}/images"


def _operation(request: ImageJobRequest) -> str:
    return "edit_image" if request.kind == "edit" else "generate_image"


async def _store_provider_link(
    url: str,
    *,
    index: int,
    ctx: RequestContext,
    trace_writer: TraceWriter,
    storage_port: StoragePort,
    run_id: str,
    request: ImageJobRequest,
) -> ImageResult:
    """Keep a provider-hosted image as a link artifact on the run.

    A provider that answers with a URL has kept the bytes itself, so the
    address is all there is to keep. It goes in the stored object rather than
    in the artifact metadata that run listings show, because such URLs are
    often signed. The artifact says the image was never inspected, since its
    bytes never passed the content check, and it is a pointer rather than a
    copy: the provider decides how long the URL lives.
    """
    data = json.dumps({"index": index, "url": url}).encode("utf-8")
    storage_key = f"{_images_prefix(ctx, run_id)}/{index}.url.json"
    await storage_port.put(
        storage_key,
        data,
        content_type="application/json",
        metadata={"run_id": run_id, "index": str(index)},
    )
    artifact = await trace_writer.create_artifact(
        run_id=run_id,
        artifact_type="json",
        storage_key=storage_key,
        mime="application/json",
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        meta={
            "kind": "image_url",
            "index": index,
            "name": f"{index}.url.json",
            "operation": _operation(request),
            "inspected": False,
        },
    )
    return ImageResult(url=url, artifact_id=artifact.id)


async def _store_as_artifacts(
    response: ImageGenerationResponse,
    *,
    ctx: RequestContext,
    trace_writer: TraceWriter,
    storage_port: StoragePort,
    run_id: str,
    request: ImageJobRequest,
) -> list[ImageResult]:
    results: list[ImageResult] = []
    for index, image in enumerate(response.images):
        if not image.b64_json:
            results.append(
                await _store_provider_link(
                    image.url,
                    index=index,
                    ctx=ctx,
                    trace_writer=trace_writer,
                    storage_port=storage_port,
                    run_id=run_id,
                    request=request,
                )
                if image.url
                else ImageResult()
            )
            continue
        data = _decode(image.b64_json)
        file_format = _sniff_format(data) or request.file_format
        mime = _OUTPUT_MIME.get(file_format, "image/png")
        storage_key = f"{_images_prefix(ctx, run_id)}/{index}.{file_format}"
        await storage_port.put(
            storage_key,
            data,
            content_type=mime,
            metadata={"run_id": run_id, "index": str(index)},
        )
        meta: dict[str, Any] = {
            "kind": "image",
            "index": index,
            "name": f"{index}.{file_format}",
            "operation": _operation(request),
        }
        if request.output_format is not None and request.output_format != file_format:
            # The provider answered in another format than the one asked for.
            meta["requested_format"] = request.output_format
        artifact = await trace_writer.create_artifact(
            run_id=run_id,
            artifact_type="file",
            storage_key=storage_key,
            mime=mime,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            meta=meta,
        )
        results.append(ImageResult(artifact_id=artifact.id))
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

        data = _decode(image.b64_json)
        verdict = await content_safety.inspect_image(
            data,
            direction=SafetyDirection.OUTBOUND,
            media_type=_OUTPUT_MIME.get(_sniff_format(data) or request.file_format, "image/png"),
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
        if any(result.artifact_id is None for result in results):
            # Every billed image of an artifact job is retrievable from the
            # run, or the job fails (its cost stays recorded): it never ends
            # succeeded with less to fetch than it was charged for.
            raise KernelError(
                "IMAGE_UNDELIVERABLE",
                "The provider returned an image that could not be kept as a run artifact",
                {"images": len(results), "stored": sum(1 for r in results if r.artifact_id)},
            )
    else:
        results = [
            ImageResult(b64_json=image.b64_json, url=image.url)
            for image in response.images
        ]

    return ImageJobOutcome(model=response.model, results=results, safety=safety)
