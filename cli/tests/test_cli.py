"""The CLI against a stand-in SOIT API."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from soit_cli import config
from soit_cli.main import EXIT_FAILED, EXIT_OK, EXIT_REGRESSED, main

KEY = "sk_test_key"


def ok(data: object) -> httpx.Response:
    return httpx.Response(200, json={"success": True, "code": "OK", "message": "OK", "data": data})


class Api:
    """Answers requests from a route table and remembers what it was asked."""

    def __init__(self, routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]]) -> None:
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            handler = self.routes.get((request.method, request.url.path))
            if handler is None:
                return httpx.Response(404, json={"success": False, "code": "NOT_FOUND", "message": "no route"})
            return handler(request)

        return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "soit" / "config.json"
    monkeypatch.setenv("SOIT_CONFIG", str(path))
    for name in ("SOIT_API_URL", "SOIT_API_KEY", "SOIT_WORKSPACE_ID"):
        monkeypatch.delenv(name, raising=False)
    return path


def _signed_in() -> None:
    config.save(config.Credentials(url="https://soit.example.com", api_key=KEY))


def test_login_checks_the_key_and_remembers_it(_isolated: Path, capsys) -> None:
    me = {"email": "ops@example.com", "workspace_id": "ws_1", "workspace_role": "Dev"}
    api = Api({("GET", "/api/v1/me"): lambda _: ok(me)})

    code = main(["login", "--url", "https://soit.example.com/", "--api-key", KEY], transport=api.transport())

    assert code == EXIT_OK
    assert "ops@example.com (workspace ws_1, Dev)" in capsys.readouterr().out
    assert api.requests[0].headers["authorization"] == f"Bearer {KEY}"
    stored = json.loads(_isolated.read_text(encoding="utf-8"))
    assert stored == {"url": "https://soit.example.com", "api_key": KEY}
    if os.name != "nt":
        assert stat.S_IMODE(_isolated.stat().st_mode) == 0o600


def test_login_reads_the_key_from_stdin(monkeypatch, capsys) -> None:
    api = Api({("GET", "/api/v1/me"): lambda _: ok({"email": "ops@example.com"})})
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{KEY}\n"))

    assert main(["login", "--api-key-stdin"], transport=api.transport()) == EXIT_OK
    assert config.load().api_key == KEY
    assert "Signed in to http://localhost:9200" in capsys.readouterr().out


def test_a_refused_key_is_not_remembered(_isolated: Path, capsys) -> None:
    body = {"success": False, "code": "UNAUTHORIZED", "message": "Invalid API key"}
    refused = Api({("GET", "/api/v1/me"): lambda _: httpx.Response(401, json=body)})

    code = main(["login", "--api-key", "sk_wrong"], transport=refused.transport())

    assert code == EXIT_FAILED
    assert "UNAUTHORIZED: Invalid API key" in capsys.readouterr().err
    assert not _isolated.exists()


def test_a_service_principal_key_signs_in_without_a_profile(capsys) -> None:
    api = Api({("GET", "/api/v1/tools"): lambda _: ok([])})

    assert main(["login", "--api-key", KEY], transport=api.transport()) == EXIT_OK
    assert "a service principal" in capsys.readouterr().out


def test_the_environment_signs_in_without_a_file(monkeypatch) -> None:
    monkeypatch.setenv("SOIT_API_URL", "https://ci.example.com/")
    monkeypatch.setenv("SOIT_API_KEY", "sk_from_env")
    monkeypatch.setenv("SOIT_WORKSPACE_ID", "ws_ci")

    credentials = config.load()

    assert credentials == config.Credentials(url="https://ci.example.com", api_key="sk_from_env", workspace_id="ws_ci")


def test_commands_need_a_sign_in(capsys) -> None:
    assert main(["run", "agt_1", "hello"]) == EXIT_FAILED
    assert "not signed in" in capsys.readouterr().err


def test_run_prints_the_answer_and_names_the_run(capsys) -> None:
    _signed_in()
    api = Api(
        {
            ("POST", "/api/v1/agents/agt_1/execute"): lambda request: ok(
                {
                    "run_id": "run_9",
                    "thread_id": "thr_2",
                    "output": f"echo: {json.loads(request.content)['input']}",
                    "model": "model:openai:gpt-5.5",
                    "tokens_prompt": 12,
                    "tokens_completion": 30,
                    "cost_total": 0.0021,
                }
            )
        }
    )

    assert main(["run", "agt_1", "How long do refunds take?"], transport=api.transport()) == EXIT_OK

    out = capsys.readouterr()
    assert out.out.strip() == "echo: How long do refunds take?"
    assert "run run_9, model:openai:gpt-5.5, 42 tokens" in out.err


def _replay(regressed: list[str]) -> dict:
    side = {
        "total": 2,
        "passed": 2,
        "failed": 0,
        "pass_rate": 1.0,
        "avg_latency_ms": 900,
        "total_cost_amount": 0.01,
        "errors": 0,
    }
    worse = {**side, "passed": 2 - len(regressed), "failed": len(regressed), "pass_rate": (2 - len(regressed)) / 2}
    return {
        "id": "regrpl_1",
        "model_ref": "model:openai:gpt-6",
        "case_count": 2,
        "subjects": [
            {
                "agent_id": "agt_1",
                "agent_name": "support-desk",
                "dataset": "default",
                "baseline_model_ref": "model:openai:gpt-5.5",
                "baseline": side,
                "candidate": worse,
                "regressed": regressed,
                "fixed": [],
            }
        ],
        "totals": {
            "baseline": side,
            "candidate": worse,
            "delta": {"pass_rate": worse["pass_rate"] - 1.0, "avg_latency_ms": 0, "total_cost_amount": 0.0},
            "regressed": len(regressed),
            "fixed": 0,
            "skipped": [],
        },
    }


def test_eval_replays_on_the_model_and_prints_the_comparison(capsys) -> None:
    _signed_in()
    api = Api({("POST", "/api/v1/evaluations/model-replays"): lambda _: ok(_replay([]))})

    code = main(
        ["eval", "model:openai:gpt-6", "--agent", "agt_1", "--dataset", "smoke", "--max-cases", "10"],
        transport=api.transport(),
    )

    assert code == EXIT_OK
    assert json.loads(api.requests[0].content) == {
        "model_ref": "model:openai:gpt-6",
        "agent_ids": ["agt_1"],
        "dataset": "smoke",
        "max_cases": 10,
    }
    out = capsys.readouterr().out
    assert "support-desk/default" in out
    assert "100.0% -> 100.0%" in out


def test_eval_fails_a_ci_step_when_a_case_regresses(capsys) -> None:
    _signed_in()
    api = Api({("POST", "/api/v1/evaluations/model-replays"): lambda _: ok(_replay(["regcase_1"]))})

    lenient = main(["eval", "model:openai:gpt-6"], transport=api.transport())
    strict = main(["eval", "model:openai:gpt-6", "--fail-on-regression", "--json"], transport=api.transport())

    assert (lenient, strict) == (EXIT_OK, EXIT_REGRESSED)
    assert "1 case(s) pass on the current model" in capsys.readouterr().err


def test_evidence_is_saved_after_its_digest_is_checked(tmp_path: Path, capsys) -> None:
    _signed_in()
    bundle = b"PK\x05\x06" + b"\x00" * 18
    digest = hashlib.sha256(bundle).hexdigest()
    api = Api(
        {
            ("GET", "/api/v1/runs/run_9/evidence"): lambda _: httpx.Response(
                200,
                content=bundle,
                headers={
                    "content-disposition": 'attachment; filename="soit-evidence-run_9.zip"',
                    "x-soit-evidence-sha256": digest,
                },
            )
        }
    )
    target = tmp_path / "out" / "evidence.zip"

    assert main(["export", "evidence", "run_9", "-o", str(target)], transport=api.transport()) == EXIT_OK

    assert target.read_bytes() == bundle
    assert digest in capsys.readouterr().err


def test_a_bundle_that_does_not_match_its_digest_is_refused(tmp_path: Path, capsys) -> None:
    _signed_in()
    api = Api(
        {
            ("GET", "/api/v1/runs/run_9/evidence"): lambda _: httpx.Response(
                200, content=b"tampered", headers={"x-soit-evidence-sha256": "0" * 64}
            )
        }
    )
    target = tmp_path / "evidence.zip"

    assert main(["export", "evidence", "run_9", "-o", str(target)], transport=api.transport()) == EXIT_FAILED
    assert "does not match its digest" in capsys.readouterr().err
    assert not target.exists()


def test_ledger_records_are_exported_for_a_window(tmp_path: Path, capsys) -> None:
    _signed_in()
    api = Api(
        {
            ("GET", "/api/v1/exports/costs"): lambda _: httpx.Response(
                200,
                content=b"cost_entry_id,amount\n",
                headers={"content-disposition": 'attachment; filename="soit-costs.csv"', "x-soit-ledger-schema": "1.0"},
            )
        }
    )
    target = tmp_path / "costs.csv"

    code = main(
        ["export", "costs", "--since", "2026-09-01T00:00:00Z", "--format", "csv", "-o", str(target)],
        transport=api.transport(),
    )

    assert code == EXIT_OK
    assert dict(api.requests[0].url.params) == {"since": "2026-09-01T00:00:00Z", "format": "csv"}
    assert target.read_bytes() == b"cost_entry_id,amount\n"
    assert "ledger contract 1.0" in capsys.readouterr().err


def test_a_ledger_export_needs_a_window(capsys) -> None:
    _signed_in()

    assert main(["export", "audit"]) == EXIT_FAILED
    assert "needs --since" in capsys.readouterr().err


def test_an_unreachable_server_is_reported_plainly(capsys) -> None:
    _signed_in()

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    assert main(["whoami"], transport=httpx.MockTransport(refuse)) == EXIT_FAILED
    assert "cannot reach https://soit.example.com" in capsys.readouterr().err


def test_logout_forgets_the_key(_isolated: Path, capsys) -> None:
    _signed_in()

    assert main(["logout"]) == EXIT_OK
    assert not _isolated.exists()
    assert "Signed out" in capsys.readouterr().out
