"""A thin client for the parts of the SOIT API the CLI uses."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import httpx

from soit_cli import __version__
from soit_cli.config import Credentials

DEFAULT_TIMEOUT = 60.0
RUN_TIMEOUT = 600.0
REPLAY_TIMEOUT = 3600.0
EXPORT_TIMEOUT = 600.0


class SoitError(Exception):
    """A refusal from SOIT, or a failure to reach it."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code

    def __str__(self) -> str:
        return f"{self.code}: {self.args[0]}" if self.code else str(self.args[0])


def _filename(disposition: str | None, fallback: str) -> str:
    match = re.search(r'filename="?([^";]+)"?', disposition or "")
    return match.group(1) if match else fallback


class SoitClient:
    """One signed-in connection to a SOIT API."""

    def __init__(self, credentials: Credentials, *, transport: httpx.BaseTransport | None = None) -> None:
        headers = {
            "Authorization": f"Bearer {credentials.api_key}",
            "User-Agent": f"soit-cli/{__version__}",
        }
        if credentials.workspace_id:
            headers["X-Workspace-Id"] = credentials.workspace_id
        self.url = credentials.url
        self.http = httpx.Client(
            base_url=credentials.url,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
            transport=transport,
        )

    def close(self) -> None:
        self.http.close()

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise SoitError(f"{self.url} did not answer in time") from exc
        except httpx.HTTPError as exc:
            raise SoitError(f"cannot reach {self.url}: {exc}") from exc
        if response.is_success:
            return response
        try:
            body = response.json()
        except ValueError:
            body = {}
        if isinstance(body, dict):
            code = body.get("code")
            message = body.get("message") or response.reason_phrase
        else:
            code, message = None, response.reason_phrase
        raise SoitError(str(message), status=response.status_code, code=str(code) if code else None)

    def _data(self, method: str, path: str, **kwargs: Any) -> Any:
        body = self._send(method, path, **kwargs).json()
        # SOIT's own API wraps answers as {"success": true, "data": ...}.
        if isinstance(body, dict) and body.get("success") is True and "data" in body:
            return body["data"]
        return body

    def me(self) -> dict[str, Any]:
        return self._data("GET", "/api/v1/me")

    def tools(self) -> list[dict[str, Any]]:
        return self._data("GET", "/api/v1/tools")

    def run_agent(self, agent_id: str, text: str, *, thread_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"input": text}
        if thread_id:
            body["thread_id"] = thread_id
        return self._data("POST", f"/api/v1/agents/{agent_id}/execute", json=body, timeout=RUN_TIMEOUT)

    def model_replay(
        self,
        model_ref: str,
        *,
        agent_ids: list[str] | None = None,
        dataset: str | None = None,
        max_cases: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"model_ref": model_ref}
        if agent_ids:
            body["agent_ids"] = agent_ids
        if dataset:
            body["dataset"] = dataset
        if max_cases is not None:
            body["max_cases"] = max_cases
        return self._data("POST", "/api/v1/evaluations/model-replays", json=body, timeout=REPLAY_TIMEOUT)

    def evidence(self, run_id: str) -> tuple[str, bytes, str]:
        """A run's evidence bundle: file name, bytes, and its checked digest."""

        response = self._send("GET", f"/api/v1/runs/{run_id}/evidence", timeout=EXPORT_TIMEOUT)
        content = response.content
        digest = hashlib.sha256(content).hexdigest()
        announced = response.headers.get("x-soit-evidence-sha256")
        if announced and announced.lower() != digest:
            raise SoitError(f"the evidence bundle does not match its digest ({announced} announced, {digest} received)")
        return _filename(response.headers.get("content-disposition"), f"soit-evidence-{run_id}.zip"), content, digest

    def export(self, kind: str, *, since: str, until: str | None, fmt: str) -> tuple[str, bytes, str | None]:
        """One kind of ledger record in a window: file name, bytes, contract version."""

        params = {"since": since, "format": fmt}
        if until:
            params["until"] = until
        response = self._send("GET", f"/api/v1/exports/{kind}", params=params, timeout=EXPORT_TIMEOUT)
        return (
            _filename(response.headers.get("content-disposition"), f"soit-{kind}.{fmt}"),
            response.content,
            response.headers.get("x-soit-ledger-schema"),
        )
