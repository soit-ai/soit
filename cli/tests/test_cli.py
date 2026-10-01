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


AGENT_FILE = {
    "soit": "agent/v1",
    "agent": {
        "name": "support-triage",
        "description": None,
        "visibility": "private",
        "category": None,
        "icon_url": None,
        "tags": None,
    },
    "version": {
        "system_prompt": "Answer briefly.",
        "bindings": {"model_ref": "model:openai:gpt-6", "tool_refs": ["tool:echo"]},
    },
}


def test_an_agent_is_exported_as_yaml(tmp_path: Path, capsys) -> None:
    _signed_in()
    api = Api({("GET", "/api/v1/agents/agt_1/export"): lambda _: ok(AGENT_FILE)})
    out = tmp_path / "agent.yaml"

    assert main(["agent", "export", "agt_1", "-o", str(out)], transport=api.transport()) == EXIT_OK

    assert capsys.readouterr().out.strip() == str(out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("soit: agent/v1\n")
    assert "system_prompt: Answer briefly." in text
    assert "model_ref: model:openai:gpt-6" in text


def test_an_agent_export_goes_to_stdout_by_default(capsys) -> None:
    _signed_in()
    api = Api({("GET", "/api/v1/agents/agt_1/export"): lambda _: ok(AGENT_FILE)})

    assert main(["agent", "export", "agt_1"], transport=api.transport()) == EXIT_OK

    assert capsys.readouterr().out.startswith("soit: agent/v1\n")


def test_an_agent_file_is_imported_with_a_new_name(tmp_path: Path, capsys) -> None:
    _signed_in()
    received: list[dict] = []

    def create(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "success": True,
                "data": {"agent": {"id": "agt_2", "name": "copy"}, "version": {"id": "ver_2", "version": 1}},
            },
        )

    api = Api({("POST", "/api/v1/agents/import"): create})
    path = tmp_path / "agent.yaml"
    path.write_text(
        "soit: agent/v1\nagent:\n  name: support-triage\nversion:\n  bindings:\n    model_ref: model:openai:gpt-6\n",
        encoding="utf-8",
    )

    assert main(["agent", "import", str(path), "--name", "copy"], transport=api.transport()) == EXIT_OK

    out = capsys.readouterr()
    assert out.out.strip() == "agt_2"
    assert "imported copy as agt_2, version 1 as a draft" in out.err
    assert received == [
        {"soit": "agent/v1", "agent": {"name": "copy"}, "version": {"bindings": {"model_ref": "model:openai:gpt-6"}}}
    ]


def test_a_file_that_is_not_an_agent_is_refused_before_the_request(tmp_path: Path, capsys) -> None:
    _signed_in()
    api = Api({})
    path = tmp_path / "notes.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")

    assert main(["agent", "import", str(path)], transport=api.transport()) == EXIT_FAILED

    assert "is not an agent file" in capsys.readouterr().err
    assert api.requests == []


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


def _dataset(dataset_id: str = "regds_1", name: str = "refunds", agent: str = "agt_1", **extra) -> dict:
    return {
        "id": dataset_id,
        "subject_kind": "agent",
        "subject_id": agent,
        "name": name,
        "description": "",
        "revision": 3,
        "status": "active",
        "case_count": 2,
        "latest_report": {"id": "regrep_1", "passed": False, "total": 2, "passed_count": 1, "dataset_revision": 3},
        **extra,
    }


def _report(*, regressed: list[str], failed: int, baseline: str | None = "regrep_0") -> dict:
    return {
        "id": "regrep_2",
        "subject_version_id": "ver_9",
        "passed": failed == 0,
        "dataset": "refunds",
        "dataset_revision": 3,
        "baseline_report_id": baseline,
        "regressed_case_ids_json": regressed,
        "fixed_case_ids_json": [],
        "summary_json": {"total": 2, "passed": 2 - failed, "failed": failed},
        "metrics_json": {},
        "case_results_json": [
            {"case_id": "regcase_1", "name": "refund-window", "passed": True, "latency_ms": 800},
            {
                "case_id": "regcase_2",
                "name": "tone",
                "passed": failed == 0,
                "latency_ms": 880,
                "failure_reasons": [] if failed == 0 else ["llm_judge_below_threshold"],
            },
        ],
    }


def test_dataset_list_shows_revision_cases_and_the_latest_report(capsys) -> None:
    _signed_in()
    api = Api(
        {
            ("GET", "/api/v1/evaluations/datasets"): lambda _: ok(
                [_dataset(), _dataset("regds_2", "tone", latest_report=None, case_count=0, revision=1)]
            )
        }
    )

    assert main(["dataset", "list", "--agent", "agt_1"], transport=api.transport()) == EXIT_OK

    assert dict(api.requests[0].url.params) == {"status": "active", "limit": "200", "subject_id": "agt_1"}
    out = capsys.readouterr().out
    assert "regds_1" in out and "FAIL 1/2 (r3)" in out
    assert "never run" in out


def test_dataset_export_writes_the_jsonl_the_server_renders(tmp_path: Path, capsys) -> None:
    _signed_in()
    jsonl = '{"name":"a","input":"hi","expected_features":{"max_latency_ms":5}}\n'
    api = Api(
        {
            ("GET", "/api/v1/evaluations/datasets"): lambda _: ok([_dataset()]),
            ("GET", "/api/v1/evaluations/datasets/regds_1/export"): lambda _: httpx.Response(
                200, content=jsonl.encode("utf-8"), headers={"content-type": "application/x-ndjson"}
            ),
        }
    )
    target = tmp_path / "out" / "refunds.jsonl"

    assert main(["dataset", "export", "refunds", "-o", str(target)], transport=api.transport()) == EXIT_OK
    assert target.read_text(encoding="utf-8") == jsonl
    assert "2 cases from refunds r3" in capsys.readouterr().err

    assert main(["dataset", "export", "regds_1"], transport=api.transport()) == EXIT_OK
    assert capsys.readouterr().out == jsonl


def test_a_dataset_name_two_agents_share_must_be_disambiguated(capsys) -> None:
    _signed_in()
    api = Api({("GET", "/api/v1/evaluations/datasets"): lambda _: ok([_dataset(), _dataset("regds_2", agent="agt_2")])})

    assert main(["dataset", "export", "refunds"], transport=api.transport()) == EXIT_FAILED
    assert "2 datasets are named 'refunds' (agents agt_1, agt_2)" in capsys.readouterr().err


def test_dataset_import_sends_the_file_text_to_the_dataset(tmp_path: Path, capsys) -> None:
    _signed_in()
    seen: dict = {}

    def imported(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return ok({"imported": 2, "dataset": _dataset(revision=4, case_count=4)})

    api = Api(
        {
            ("GET", "/api/v1/evaluations/datasets"): lambda _: ok([_dataset()]),
            ("POST", "/api/v1/evaluations/datasets/regds_1/import"): imported,
        }
    )
    source = tmp_path / "cases.jsonl"
    source.write_text('{"name":"a"}\n{"name":"b"}\n', encoding="utf-8")

    code = main(["dataset", "import", "refunds", str(source), "--note", "from CI"], transport=api.transport())

    assert code == EXIT_OK
    assert seen == {"content": '{"name":"a"}\n{"name":"b"}\n', "note": "from CI"}
    out = capsys.readouterr()
    assert out.out.strip() == "regds_1"
    assert "imported 2 cases into refunds, now r4 with 4 cases" in out.err


def test_a_refused_import_lists_every_bad_line_and_exits_1(tmp_path: Path, capsys) -> None:
    _signed_in()
    refusal = {
        "success": False,
        "code": "VALIDATION_ERROR",
        "message": "2 of 3 lines are not valid cases; nothing was imported",
        "details": {
            "error_count": 2,
            "errors": [
                {"line": 2, "message": "not valid JSON: Expecting value"},
                {"line": 3, "message": "/expected_features: {} should be non-empty"},
            ],
        },
    }
    api = Api(
        {
            ("GET", "/api/v1/evaluations/datasets"): lambda _: ok([_dataset()]),
            ("POST", "/api/v1/evaluations/datasets/regds_1/import"): lambda _: httpx.Response(400, json=refusal),
        }
    )
    source = tmp_path / "cases.jsonl"
    source.write_text("x\n", encoding="utf-8")

    assert main(["dataset", "import", "regds_1", str(source)], transport=api.transport()) == EXIT_FAILED

    err = capsys.readouterr().err
    assert f"{source}:2: not valid JSON" in err
    assert f"{source}:3: /expected_features" in err
    assert "(2 problems)" in err


def test_dataset_import_can_create_the_dataset_first(tmp_path: Path, capsys) -> None:
    _signed_in()
    created: dict = {}

    def create(request: httpx.Request) -> httpx.Response:
        created.update(json.loads(request.content))
        return ok(_dataset("regds_new", "fresh", revision=1, case_count=0))

    api = Api(
        {
            ("GET", "/api/v1/evaluations/datasets"): lambda _: ok([]),
            ("POST", "/api/v1/evaluations/datasets"): create,
            ("POST", "/api/v1/evaluations/datasets/regds_new/import"): lambda _: ok(
                {"imported": 1, "dataset": _dataset("regds_new", "fresh", revision=2, case_count=1)}
            ),
        }
    )
    source = tmp_path / "cases.jsonl"
    source.write_text('{"name":"a"}\n', encoding="utf-8")

    refused = main(["dataset", "import", "fresh", str(source)], transport=api.transport())
    assert refused == EXIT_FAILED
    assert "pass --create" in capsys.readouterr().err

    code = main(["dataset", "import", "fresh", str(source), "--agent", "agt_1", "--create"], transport=api.transport())

    assert code == EXIT_OK
    assert created == {"subject_id": "agt_1", "name": "fresh", "description": ""}
    assert capsys.readouterr().out.strip() == "regds_new"


def test_eval_run_prints_the_cases_and_names_the_report(capsys) -> None:
    _signed_in()
    api = Api({("POST", "/api/v1/evaluations/run"): lambda _: ok(_report(regressed=["regcase_2"], failed=1))})

    code = main(
        [
            "eval",
            "run",
            "agt_1",
            "--dataset",
            "refunds",
            "--version",
            "ver_9",
            "--model",
            "model:x:y",
            "--max-cases",
            "10",
        ],
        transport=api.transport(),
    )

    assert code == EXIT_OK
    assert json.loads(api.requests[0].content) == {
        "subject_id": "agt_1",
        "dataset": "refunds",
        "subject_version_id": "ver_9",
        "model_ref": "model:x:y",
        "max_cases": 10,
    }
    out = capsys.readouterr()
    assert "tone" in out.out and "FAIL" in out.out and "llm_judge_below_threshold (regressed)" in out.out
    assert "1/2 cases passed (50.0%) on refunds r3, version ver_9; 1 regressed, 0 fixed against regrep_0" in out.out
    assert "report regrep_2" in out.err


def test_eval_run_defaults_to_the_default_dataset(capsys) -> None:
    _signed_in()
    api = Api({("POST", "/api/v1/evaluations/run"): lambda _: ok(_report(regressed=[], failed=0, baseline=None))})

    assert main(["eval", "run", "agt_1"], transport=api.transport()) == EXIT_OK

    assert json.loads(api.requests[0].content) == {"subject_id": "agt_1", "dataset": "default"}
    assert "no comparable baseline yet" in capsys.readouterr().out


def test_eval_run_fails_a_ci_step_on_a_regression_or_on_any_failure(capsys) -> None:
    _signed_in()
    regressing = Api({("POST", "/api/v1/evaluations/run"): lambda _: ok(_report(regressed=["regcase_2"], failed=1))})
    known_gap = Api({("POST", "/api/v1/evaluations/run"): lambda _: ok(_report(regressed=[], failed=1))})

    lenient = main(["eval", "run", "agt_1"], transport=regressing.transport())
    on_regression = main(["eval", "run", "agt_1", "--fail-on-regression", "--json"], transport=regressing.transport())
    gap_on_regression = main(["eval", "run", "agt_1", "--fail-on-regression"], transport=known_gap.transport())
    on_failure = main(["eval", "run", "agt_1", "--fail-on-failure"], transport=known_gap.transport())

    assert (lenient, on_regression, gap_on_regression, on_failure) == (
        EXIT_OK,
        EXIT_REGRESSED,
        EXIT_OK,
        EXIT_REGRESSED,
    )
    assert "1 case(s) passed in the baseline and fail now" in capsys.readouterr().err


def test_eval_with_a_model_still_means_a_replay() -> None:
    _signed_in()
    api = Api({("POST", "/api/v1/evaluations/model-replays"): lambda _: ok(_replay([]))})

    assert main(["eval", "model:openai:gpt-6"], transport=api.transport()) == EXIT_OK
    assert api.requests[0].url.path == "/api/v1/evaluations/model-replays"
