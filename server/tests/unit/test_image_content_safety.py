"""Image content safety (M4 part one).

The property that matters is the distinction between "inspected and clean" and
"never inspected": a deployment whose classifier reads only text must not have
its generated images silently recorded as checked.
"""

from typing import Any

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.ports.safety.interface import (
    ContentSafetyPort,
    SafetyDecision,
    SafetyDirection,
    SafetyFinding,
    SafetyVerdict,
)
from app.kernel.runtime.images.service import ImageJobRequest, _inspect_results
from app.kernel.safety.rules import RuleContentSafetyPort


class _Response:
    def __init__(self, images):
        self.images = images
        self.model = "test-model"


class _Image:
    def __init__(self, b64_json=None, url=None):
        self.b64_json = b64_json
        self.url = url


class _TextOnlyPort(ContentSafetyPort):
    async def inspect(self, text, *, direction, **kwargs):
        return SafetyVerdict(decision=SafetyDecision.ALLOW, provider="text-only")


class _RecordingImagePort(ContentSafetyPort):
    def __init__(self, decision=SafetyDecision.ALLOW, findings=None):
        self.decision = decision
        self.findings = findings or []
        self.calls: list[dict[str, Any]] = []

    async def inspect(self, text, *, direction, **kwargs):
        return SafetyVerdict(decision=SafetyDecision.ALLOW, provider="recording")

    async def inspect_image(
        self, image, *, direction, media_type="image/png", **kwargs
    ):
        self.calls.append(
            {
                "bytes": len(image),
                "direction": direction,
                "media_type": media_type,
                "run_id": kwargs.get("run_id"),
            }
        )
        return SafetyVerdict(
            decision=self.decision, findings=self.findings, provider="recording"
        )


# "aGk=" decodes to b"hi": short, valid base64 standing in for image bytes.
_REQUEST = ImageJobRequest(kind="generate", model="model:test:m", prompt="a red dot")


class TestPortDefault:
    @pytest.mark.asyncio
    async def test_a_text_only_port_reports_no_image_capability(self):
        # Not an allow-with-no-findings: the run's evidence has to show the
        # image was never looked at.
        verdict = await _TextOnlyPort().inspect_image(
            b"bytes", direction=SafetyDirection.OUTBOUND
        )
        assert verdict.decision is SafetyDecision.ALLOW
        assert [finding.category for finding in verdict.findings] == [
            "safety.image_inspection_unavailable"
        ]

    @pytest.mark.asyncio
    async def test_the_builtin_rule_port_inherits_that_default(self):
        verdict = await RuleContentSafetyPort().inspect_image(
            b"bytes", direction=SafetyDirection.OUTBOUND
        )
        assert verdict.findings[0].category == "safety.image_inspection_unavailable"

    def test_evidence_never_carries_the_content(self):
        # Recording what was matched would recreate the exposure the check
        # exists to prevent.
        verdict = SafetyVerdict(
            decision=SafetyDecision.BLOCK,
            findings=[SafetyFinding(category="nudity", severity="high")],
            provider="p",
        )
        rendered = verdict.evidence()
        assert rendered["decision"] == "block"
        assert set(rendered["findings"][0]) == {"category", "severity", "detail"}


class TestResultInspection:
    @pytest.mark.asyncio
    async def test_no_classifier_records_nothing(self):
        evidence = await _inspect_results(
            _Response([_Image(b64_json="aGk=")]),
            content_safety=None,
            request=_REQUEST,
            run_id="run_1",
        )
        assert evidence == []

    @pytest.mark.asyncio
    async def test_every_returned_image_is_inspected(self):
        port = _RecordingImagePort()
        await _inspect_results(
            _Response([_Image(b64_json="aGk="), _Image(b64_json="aGk=")]),
            content_safety=port,
            request=_REQUEST,
            run_id="run_1",
        )
        assert len(port.calls) == 2
        assert all(call["direction"] is SafetyDirection.OUTBOUND for call in port.calls)
        assert all(call["run_id"] == "run_1" for call in port.calls)

    @pytest.mark.asyncio
    async def test_the_media_type_follows_the_output_format(self):
        port = _RecordingImagePort()
        request = ImageJobRequest(
            kind="edit",
            model="model:test:m",
            prompt="a red dot",
            image=b"source",
            output_format="webp",
        )
        await _inspect_results(
            _Response([_Image(b64_json="aGk=")]),
            content_safety=port,
            request=request,
            run_id="run_1",
        )
        assert port.calls[0]["media_type"] == "image/webp"

    @pytest.mark.asyncio
    async def test_findings_become_evidence(self):
        port = _RecordingImagePort(
            findings=[SafetyFinding(category="violence", severity="low")]
        )
        evidence = await _inspect_results(
            _Response([_Image(b64_json="aGk=")]),
            content_safety=port,
            request=_REQUEST,
            run_id="run_1",
        )
        assert evidence[0]["decision"] == "allow"
        assert evidence[0]["direction"] == "outbound"
        assert evidence[0]["index"] == 0
        assert evidence[0]["findings"][0]["category"] == "violence"

    @pytest.mark.asyncio
    async def test_a_clean_image_records_no_evidence(self):
        # Observe mode should stay quiet when there is nothing to report.
        evidence = await _inspect_results(
            _Response([_Image(b64_json="aGk=")]),
            content_safety=_RecordingImagePort(),
            request=_REQUEST,
            run_id="run_1",
        )
        assert evidence == []

    @pytest.mark.asyncio
    async def test_a_blocked_image_refuses_the_job(self):
        port = _RecordingImagePort(
            decision=SafetyDecision.BLOCK,
            findings=[SafetyFinding(category="nudity", severity="high")],
        )
        with pytest.raises(ForbiddenError) as exc:
            await _inspect_results(
                _Response([_Image(b64_json="aGk=")]),
                content_safety=port,
                request=_REQUEST,
                run_id="run_1",
            )
        assert exc.value.details["categories"] == ["nudity"]
        assert exc.value.details["index"] == 0

    @pytest.mark.asyncio
    async def test_blocking_happens_before_anything_is_stored(self):
        # _inspect_results runs ahead of artifact writing, so a refused image
        # never becomes a durable object. Asserted by the raise: execution
        # cannot reach the storage step.
        port = _RecordingImagePort(
            decision=SafetyDecision.BLOCK,
            findings=[SafetyFinding(category="nudity")],
        )
        with pytest.raises(ForbiddenError):
            await _inspect_results(
                _Response([_Image(b64_json="aGk="), _Image(b64_json="aGk=")]),
                content_safety=port,
                request=_REQUEST,
                run_id="run_1",
            )
        # Stopped at the first refusal rather than inspecting the rest.
        assert len(port.calls) == 1

    @pytest.mark.asyncio
    async def test_provider_hosted_urls_are_reported_as_not_inspected(self):
        # The bytes never reached us, so claiming a verdict would be a lie.
        port = _RecordingImagePort()
        evidence = await _inspect_results(
            _Response([_Image(url="https://provider.example/image.png")]),
            content_safety=port,
            request=_REQUEST,
            run_id="run_1",
        )
        assert port.calls == []
        assert evidence[0]["decision"] == "not_inspected"
        assert evidence[0]["reason"] == "provider_hosted_url"
