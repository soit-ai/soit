"""A stand-in OpenAI-compatible provider for rehearsing a pilot without real credentials.

Standard library only. Configure it in SOIT as an ``openai_compatible``
provider with base URL ``http://127.0.0.1:9311/v1`` and any API key. The model
name decides how a call goes:

- ``pilot-ok``: answers, whole or streamed, with 100 prompt and 50 completion
  tokens on every call, a response id ``chatcmpl-mock-N`` and an
  ``x-request-id: req_mock_N`` header.
- ``pilot-fail``: answers ``503``, so a virtual model moves on to its next target.
- ``pilot-slow``: waits ``--slow-seconds`` (default 30) before answering, to
  exercise a timeout.

Run: ``python mock_upstream.py [--port 9311] [--slow-seconds 30]``. A model call
from SOIT to this address also needs ``EGRESS_PRIVATE_NETWORKS`` to name
``127.0.0.1/32`` and ``127.0.0.1`` in the workspace egress allowlist.
"""

from __future__ import annotations

import argparse
import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PROMPT_TOKENS = 100
COMPLETION_TOKENS = 50
MODELS = ("pilot-ok", "pilot-fail", "pilot-slow")

_counter = itertools.count(1)
_lock = threading.Lock()
_slow_seconds = 30.0


def _next_ids() -> tuple[str, str]:
    with _lock:
        n = next(_counter)
    return f"chatcmpl-mock-{n}", f"req_mock_{n}"


class Handler(BaseHTTPRequestHandler):
    server_version = "soit-pilot-mock/1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        print(f"{self.address_string()} {format % args}", flush=True)

    def _json(self, status: int, body: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._json(200, {"object": "list", "data": [{"id": name, "object": "model"} for name in MODELS]})
            return
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._json(400, {"error": {"message": "invalid JSON", "type": "invalid_request_error"}})
            return
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        model = str(body.get("model") or "")
        if model.endswith("pilot-fail"):
            self._json(503, {"error": {"message": "upstream unavailable (mock)", "type": "server_error"}})
            return
        if model.endswith("pilot-slow"):
            time.sleep(_slow_seconds)
        response_id, request_id = _next_ids()
        text = "Pilot answer from the mock provider."
        usage = {
            "prompt_tokens": PROMPT_TOKENS,
            "completion_tokens": COMPLETION_TOKENS,
            "total_tokens": PROMPT_TOKENS + COMPLETION_TOKENS,
        }
        if not body.get("stream"):
            self._json(
                200,
                {
                    "id": response_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
                    ],
                    "usage": usage,
                },
                {"x-request-id": request_id},
            )
            return
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("x-request-id", request_id)
        self.end_headers()
        base = {"id": response_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": model}
        events = [
            {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]},
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        if (body.get("stream_options") or {}).get("include_usage"):
            events.append({**base, "choices": [], "usage": usage})
        for event in events:
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> None:
    global _slow_seconds
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9311)
    parser.add_argument("--slow-seconds", type=float, default=30.0)
    args = parser.parse_args()
    _slow_seconds = args.slow_seconds
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"mock provider on http://{args.host}:{args.port}/v1 (models: {', '.join(MODELS)})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
