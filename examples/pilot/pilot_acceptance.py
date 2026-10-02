"""Set up, accept and tear down a SOIT gateway pilot over HTTP.

    python pilot_acceptance.py setup    --config pilot.json   # provider, models, failover, key, budget
    python pilot_acceptance.py check    --state pilot-state.json
    python pilot_acceptance.py teardown --state pilot-state.json

``setup`` signs in as a workspace owner or admin (``SOIT_ADMIN_EMAIL`` and
``SOIT_ADMIN_PASSWORD``, or ``SOIT_ADMIN_TOKEN``) and creates what a gateway
pilot needs: the provider's credential as a secret, the provider, a priced
model, a failing or standby model and an unpriced one when configured, a
virtual model that fails over to the priced model, a pilot API key limited to
those models and one built-in tool, and a small daily hard-stop budget on that
key. Everything it created is written to the state file, the pilot key's
secret included: keep that file private and run ``teardown`` when done.

``check`` runs the acceptance checks against that setup and writes
``pilot-report.json`` and ``pilot-report.md``. ``teardown`` revokes the key and
deletes what ``setup`` created. Needs ``httpx`` (``pip install httpx``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

TOOL_REF = "tool:function:time_now"
TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class PilotError(RuntimeError):
    pass


# --- HTTP ------------------------------------------------------------------


class Soit:
    """The SOIT API, as an admin (JWT or admin-scope key) or as the pilot key."""

    def __init__(self, base_url: str, token: str, workspace_id: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        if workspace_id:
            self.headers["X-Workspace-Id"] = workspace_id
        self.http = httpx.Client(base_url=self.base_url, timeout=TIMEOUT)

    def raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        return self.http.request(method, path, headers=headers, **kwargs)

    def api(self, method: str, path: str, *, json_body: Any = None, params: Any = None) -> Any:
        response = self.raw(method, path, json=json_body, params=params)
        if response.status_code == 204:
            return None
        try:
            body = response.json()
        except ValueError as exc:
            raise PilotError(f"{method} {path}: HTTP {response.status_code}, not JSON") from exc
        if response.status_code >= 400 or (isinstance(body, dict) and body.get("success") is False):
            raise PilotError(f"{method} {path}: HTTP {response.status_code} {body.get('code')}: {body.get('message')}")
        return body.get("data") if isinstance(body, dict) and "data" in body else body


def admin_session(base_url: str) -> tuple[Soit, str]:
    """An admin session and its workspace id, from SOIT_ADMIN_TOKEN or email and password."""
    token = os.environ.get("SOIT_ADMIN_TOKEN")
    workspace_id = os.environ.get("SOIT_WORKSPACE_ID")
    if not token:
        email, password = os.environ.get("SOIT_ADMIN_EMAIL"), os.environ.get("SOIT_ADMIN_PASSWORD")
        if not (email and password):
            raise PilotError("Set SOIT_ADMIN_TOKEN, or SOIT_ADMIN_EMAIL and SOIT_ADMIN_PASSWORD")
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/v1/login", json={"email": email, "password": password}, timeout=TIMEOUT
        )
        data = (response.json() or {}).get("data") or {}
        if response.status_code != 200 or not data.get("access_token"):
            raise PilotError(f"Sign-in failed: HTTP {response.status_code}{' (two-factor is on)' if data.get('mfa_required') else ''}")
        token = data["access_token"]
        workspace_id = workspace_id or data.get("workspace_id")
    session = Soit(base_url, token, workspace_id)
    me = session.api("GET", "/api/v1/me")
    workspace_id = workspace_id or me.get("workspace_id")
    if not workspace_id:
        raise PilotError("No workspace: set SOIT_WORKSPACE_ID")
    return Soit(base_url, token, workspace_id), workspace_id


# --- setup -----------------------------------------------------------------


def _is_private(host: str) -> bool:
    try:
        address = ip_address(host)
    except ValueError:
        return host == "localhost"
    return address.is_private or address.is_loopback


def setup(config_path: Path, state_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_url = config["soit_url"]
    admin, workspace_id = admin_session(base_url)
    provider = config["provider"]
    slug = provider["slug"]
    state: dict[str, Any] = {
        "soit_url": base_url,
        "workspace_id": workspace_id,
        "created_at": datetime.now(UTC).isoformat(),
        "pricing": config["pricing"],
        "budget": config["budget"],
    }

    def save() -> None:
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        try:
            os.chmod(state_path, 0o600)
        except OSError:
            pass

    try:
        host = urlparse(provider["base_url"]).hostname or ""
        if _is_private(host):
            egress = admin.api("GET", "/api/v1/security/egress/workspace")
            allowlist = list(egress.get("allowlist") or [])
            if host not in allowlist:
                admin.api(
                    "PUT",
                    "/api/v1/security/egress/workspace",
                    json_body={"allowlist": [*allowlist, host], "blocklist": list(egress.get("blocklist") or [])},
                )
                state["egress_host_added"] = host
            print(f"egress: {host} allowed (the API also needs EGRESS_PRIVATE_NETWORKS to name it)")

        key_env = provider.get("api_key_env")
        credential = os.environ.get(key_env) if key_env else "unused-by-the-mock"
        if not credential:
            raise PilotError(f"Set {key_env} to the provider's API key")
        secret = admin.api(
            "POST", "/api/v1/secrets", json_body={"name": f"pilot-{slug}-{uuid.uuid4().hex[:6]}", "value": credential}
        )
        state["secret_id"] = secret["id"]
        save()

        created = admin.api(
            "POST",
            "/api/v1/modelhub/providers",
            json_body={
                "kind": provider.get("kind", "openai_compatible"),
                "name": provider["name"],
                "slug": slug,
                "base_url": provider["base_url"],
                "credential_secret_id": secret["id"],
                # Fail over at once instead of retrying a failing target first.
                "connection_config_json": {"retry_policy": {"max_retries": 0}},
            },
        )
        state["provider_id"] = created["id"]
        save()

        models: dict[str, dict[str, str]] = {}
        for role, model_id, pricing in (
            ("primary", config["models"]["primary"], config["pricing"]),
            ("failing", config["models"].get("failing"), config["pricing"]),
            ("unpriced", config["models"].get("unpriced"), None),
        ):
            if not model_id:
                continue
            body: dict[str, Any] = {"model_id": model_id, "display_name": f"Pilot {role}"}
            if pricing:
                body["pricing_json"] = pricing
            model = admin.api("POST", f"/api/v1/modelhub/providers/{created['id']}/models", json_body=body)
            models[role] = {"id": model["id"], "ref": model["model_ref"]}
            state["models"] = models
            save()

        allowed = [models["primary"]["ref"]]
        if "failing" in models:
            virtual = admin.api(
                "POST",
                "/api/v1/modelhub/virtual-models",
                json_body={
                    "slug": f"{slug}-failover",
                    "name": "Pilot failover",
                    "targets": [models["failing"]["ref"], models["primary"]["ref"]],
                },
            )
            state["virtual_model"] = {"id": virtual["id"], "ref": virtual["model_ref"]}
            allowed.append(virtual["model_ref"])
            save()
        if "unpriced" in models:
            allowed.append(models["unpriced"]["ref"])

        key = admin.api(
            "POST",
            "/api/v1/api-keys",
            json_body={
                "name": f"pilot-{slug}",
                "scopes": ["write"],
                "expires_in_days": int(config.get("key_days", 7)),
                "allowed_models": allowed,
                "allowed_tools": [TOOL_REF],
            },
        )
        state["api_key"] = {"id": key["item"]["id"], "secret": key["api_key"]}
        save()

        budget = admin.api(
            "POST",
            "/api/v1/billing/budgets",
            json_body={
                "name": f"Pilot {slug} daily",
                "scope_kind": "api_key",
                "scope_id": key["item"]["id"],
                "period": "day",
                "amount": str(config["budget"]["amount"]),
                "currency": config["budget"]["currency"],
                "hard_stop": True,
            },
        )
        state["budget_id"] = budget["id"]
        save()
    except Exception:
        save()
        print(f"setup stopped; what it created is in {state_path}, run teardown to remove it", file=sys.stderr)
        raise
    print(f"setup done: {state_path} (holds the pilot key, keep it private)")
    for role, model in state.get("models", {}).items():
        print(f"  {role}: {model['ref']}")
    if state.get("virtual_model"):
        print(f"  failover: {state['virtual_model']['ref']}")


# --- checks ----------------------------------------------------------------


@dataclass
class Check:
    name: str
    status: str = "pass"
    detail: str = ""
    seconds: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)


class Acceptance:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.admin, _ = admin_session(state["soit_url"])
        self.key = Soit(state["soit_url"], state["api_key"]["secret"])
        self.started = datetime.now(UTC)
        self.checks: list[Check] = []
        self.first_run_id: str | None = None
        self.call_cost: str | None = None

    def run(self, name: str, fn: Any) -> None:
        check = Check(name)
        start = time.monotonic()
        try:
            result = fn(check)
            if result == "skip":
                check.status = "skip"
        except AssertionError as exc:
            check.status, check.detail = "fail", str(exc) or check.detail
        except Exception as exc:  # noqa: BLE001 - a check that errors is a failed check
            check.status, check.detail = "fail", f"{type(exc).__name__}: {exc}"
        check.seconds = round(time.monotonic() - start, 2)
        self.checks.append(check)
        print(f"[{check.status.upper():4}] {name}{' - ' + check.detail if check.detail else ''}", flush=True)

    def chat(self, model: str, *, key: Soit | None = None, stream: bool = False) -> httpx.Response:
        body: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": "Pilot check: say hello."}]}
        if stream:
            body.update(stream=True, stream_options={"include_usage": True})
        return (key or self.key).raw("POST", "/v1/chat/completions", json=body)

    def run_detail(self, run_id: str) -> dict[str, Any]:
        return self.admin.api("GET", f"/api/v1/runs/{run_id}")

    # Each check takes its Check, fills detail and evidence, and asserts.

    def ready(self, check: Check) -> None:
        response = self.admin.raw("GET", "/health/ready")
        data = (response.json() or {}).get("data") or {}
        check.evidence = data
        assert response.status_code == 200, f"/health/ready answered {response.status_code}: {data}"
        check.detail = ", ".join(f"{k}={v}" for k, v in data.items() if k != "status")

    def allowed_call(self, check: Check) -> None:
        primary = self.state["models"]["primary"]["ref"]
        response = self.chat(primary)
        assert response.status_code == 200, f"{primary}: HTTP {response.status_code} {response.text[:200]}"
        run_id = response.headers.get("x-soit-run-id")
        assert run_id, "no x-soit-run-id header"
        self.first_run_id = run_id
        detail = self.run_detail(run_id)
        costs = detail.get("costs") or []
        assert costs, "the run has no cost entry"
        cost = costs[0]
        check.evidence = {
            "run_id": run_id,
            "amount": cost.get("amount"),
            "currency": cost.get("currency"),
            "pricing_status": cost.get("pricing_status"),
            "upstream_id": cost.get("upstream_id"),
            "upstream_request_id": cost.get("upstream_request_id"),
            "tokens": [cost.get("prompt_tokens"), cost.get("completion_tokens")],
        }
        assert cost.get("pricing_status") == "priced", f"cost is {cost.get('pricing_status')}, expected priced"
        self.call_cost = cost.get("amount")
        check.detail = f"run {run_id}, {cost.get('amount')} {cost.get('currency')}, provider id {cost.get('upstream_id') or '-'}"

    def streamed_call(self, check: Check) -> None:
        primary = self.state["models"]["primary"]["ref"]
        response = self.chat(primary, stream=True)
        assert response.status_code == 200, f"HTTP {response.status_code} {response.text[:200]}"
        text = response.text
        assert "data: [DONE]" in text, "the stream did not end with [DONE]"
        assert '"usage"' in text, "no usage chunk at the end of the stream"
        check.detail = f"run {response.headers.get('x-soit-run-id')}"

    def invalid_key(self, check: Check) -> None:
        stranger = Soit(self.state["soit_url"], "sk_not_a_real_key_" + uuid.uuid4().hex)
        response = self.chat(self.state["models"]["primary"]["ref"], key=stranger)
        assert response.status_code == 401, f"expected 401, got {response.status_code}"
        check.detail = "401 authentication_error"

    def model_not_allowed(self, check: Check) -> None:
        provider_slug = self.state["models"]["primary"]["ref"].split(":")[1]
        response = self.chat(f"model:{provider_slug}:not-on-the-keys-list")
        error = (response.json() or {}).get("error") or {}
        assert response.status_code == 403, f"expected 403, got {response.status_code}"
        check.detail = f"403 {error.get('type')} {error.get('code')}"

    def failover(self, check: Check) -> str | None:
        virtual = self.state.get("virtual_model")
        if not virtual:
            check.detail = "no failing model configured"
            return "skip"
        response = self.chat(virtual["ref"])
        assert response.status_code == 200, f"HTTP {response.status_code} {response.text[:200]}"
        run_id = response.headers.get("x-soit-run-id")
        steps = self.run_detail(run_id).get("steps") or []
        attempts = next(
            ((step.get("metrics_json") or {}).get("attempts") for step in steps if (step.get("metrics_json") or {}).get("attempts")),
            None,
        )
        check.evidence = {"run_id": run_id, "attempts": attempts}
        assert attempts and attempts[0].get("outcome") in {"failed", "unavailable"}, f"attempts: {attempts}"
        assert attempts[-1].get("outcome") == "succeeded", f"attempts: {attempts}"
        check.detail = " -> ".join(f"{a.get('model_ref')} {a.get('outcome')}" for a in attempts)
        return None

    def unpriced_refused(self, check: Check) -> str | None:
        unpriced = (self.state.get("models") or {}).get("unpriced")
        if not unpriced:
            check.detail = "no unpriced model configured"
            return "skip"
        workspace_path = f"/api/v1/workspaces/{self.state['workspace_id']}"
        before = self.admin.api("GET", workspace_path).get("unpriced_call_policy") or "allow"
        self.admin.api("PATCH", workspace_path, json_body={"unpriced_call_policy": "refuse"})
        try:
            response = self.chat(unpriced["ref"])
        finally:
            self.admin.api("PATCH", workspace_path, json_body={"unpriced_call_policy": before})
        error = (response.json() or {}).get("error") or {}
        check.evidence = {"policy_restored": before, "error": error}
        assert response.status_code == 403, f"expected 403, got {response.status_code}"
        assert error.get("code") == "pricing_not_configured", f"code {error.get('code')}"
        check.detail = f"403 pricing_not_configured, policy back to {before}"
        return None

    def idempotent_tool(self, check: Check) -> None:
        key = f"pilot-{uuid.uuid4().hex}"
        path = f"/api/v1/tools/{quote(TOOL_REF, safe=':')}/invoke"
        first = self.key.api("POST", path, json_body={"arguments": {}, "idempotency_key": key})
        second = self.key.api("POST", path, json_body={"arguments": {}, "idempotency_key": key})
        check.evidence = {"first": first.get("run_id"), "second": second.get("run_id"), "replayed": second.get("replayed")}
        assert first.get("run_id") == second.get("run_id"), "the repeated call opened another run"
        assert second.get("replayed") is True, "the repeated call was not a replay"
        costs = self.run_detail(first["run_id"]).get("costs") or []
        assert len(costs) <= 1, f"{len(costs)} cost entries for one call"
        check.detail = f"run {first.get('run_id')} once, replayed"

    def budget_exhausted(self, check: Check) -> None:
        primary = self.state["models"]["primary"]["ref"]
        for attempt in range(1, 41):
            response = self.chat(primary)
            if response.status_code == 402:
                error = (response.json() or {}).get("error") or {}
                status = self.admin.api("GET", f"/api/v1/billing/budgets/{self.state['budget_id']}/status")
                check.evidence = {
                    "calls_before_refusal": attempt - 1,
                    "error": error,
                    "spent": status.get("spent"),
                    "remaining": status.get("remaining"),
                }
                assert error.get("code") == "budget_exhausted", f"code {error.get('code')}"
                # Nothing else calls with the pilot key, so a refusal as held
                # while a whole call's cost remains means a hold outlived its call.
                held = "held by calls in flight" in str(error.get("message"))
                if held and self.call_cost is not None:
                    assert Decimal(str(status.get("remaining"))) < Decimal(self.call_cost), (
                        f"refused with {status.get('remaining')} left, held by calls no longer running: "
                        f"{error.get('message')}"
                    )
                check.detail = f"402 budget_exhausted after {attempt - 1} more calls: {error.get('message')}"
                return
            assert response.status_code == 200, f"call {attempt}: HTTP {response.status_code} {response.text[:200]}"
        raise AssertionError("40 calls and the budget never refused one; is its amount small enough?")

    def reconciliation(self, check: Check) -> None:
        data = self.admin.api(
            "GET",
            "/api/v1/runs/costs/reconciliation",
            params={
                "since": self.started.isoformat(),
                "api_key_id": self.state["api_key"]["id"],
                "group_by": "model",
            },
        )
        check.evidence = data
        assert data["entry_count"] > 0, "no cost entries for the pilot key"
        currency = self.state["budget"]["currency"]
        assert currency in data["amounts"], f"nothing priced in {currency}: {data['amounts']}"
        unpriced_models = [g for g in data["groups"] if g["unpriced_count"] and g["key"]]
        assert not unpriced_models, f"model calls recorded without a price: {unpriced_models}"
        check.detail = (
            f"{data['entry_count']} entries, priced {data['amounts']}, "
            f"unpriced {data['status_counts'].get('unpriced', 0)} (tool calls), bill {data['external_reconciliation']}"
        )

    def evidence_bundle(self, check: Check) -> str | None:
        if not self.first_run_id:
            check.detail = "no run from the allowed call"
            return "skip"
        response = self.admin.raw("GET", f"/api/v1/runs/{self.first_run_id}/evidence")
        assert response.status_code == 200, f"HTTP {response.status_code}"
        digest = hashlib.sha256(response.content).hexdigest()
        stated = response.headers.get("x-soit-evidence-sha256")
        check.evidence = {"run_id": self.first_run_id, "bytes": len(response.content), "sha256": digest}
        assert stated == digest, f"header {stated} != body {digest}"
        check.detail = f"{len(response.content)} bytes, sha256 {digest[:16]}..."
        return None

    def all(self) -> None:
        self.run("API ready", self.ready)
        self.run("Allowed call answered, run recorded, cost priced", self.allowed_call)
        self.run("Streamed call ends with usage", self.streamed_call)
        self.run("Invalid key refused (401)", self.invalid_key)
        self.run("Model outside the key's list refused (403)", self.model_not_allowed)
        self.run("Failover to the next target recorded as attempts", self.failover)
        self.run("Unpriced call refused under the workspace policy (403)", self.unpriced_refused)
        self.run("Repeated tool call with one idempotency key runs once", self.idempotent_tool)
        self.run("Budget exhausted refused (402)", self.budget_exhausted)
        self.run("Cost reconciliation for the pilot key", self.reconciliation)
        self.run("Evidence bundle downloaded and its SHA-256 matches", self.evidence_bundle)


def write_report(acceptance: Acceptance, out_dir: Path) -> int:
    failed = [c for c in acceptance.checks if c.status == "fail"]
    report = {
        "soit_url": acceptance.state["soit_url"],
        "started_at": acceptance.started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "result": "fail" if failed else "pass",
        "checks": [asdict(c) for c in acceptance.checks],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pilot-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Pilot acceptance report",
        "",
        f"- SOIT: {report['soit_url']}",
        f"- Run: {report['started_at']} to {report['finished_at']}",
        f"- Result: **{report['result']}**",
        "",
        "| Check | Result | Detail | Seconds |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {c.name} | {c.status} | {c.detail.replace('|', '/')} | {c.seconds} |" for c in acceptance.checks]
    (out_dir / "pilot-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {out_dir / 'pilot-report.md'} ({report['result']})")
    return 1 if failed else 0


# --- teardown --------------------------------------------------------------


def teardown(state_path: Path) -> None:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    admin, _ = admin_session(state["soit_url"])
    steps: list[tuple[str, str, str, Any]] = []
    if state.get("api_key"):
        steps.append(("revoke key", "POST", f"/api/v1/api-keys/{state['api_key']['id']}/revoke", None))
    if state.get("budget_id"):
        steps.append(("delete budget", "DELETE", f"/api/v1/billing/budgets/{state['budget_id']}", None))
    if state.get("virtual_model"):
        steps.append(("delete virtual model", "DELETE", f"/api/v1/modelhub/virtual-models/{state['virtual_model']['id']}", None))
    for role, model in (state.get("models") or {}).items():
        steps.append((f"delete {role} model", "DELETE", f"/api/v1/modelhub/providers/{state['provider_id']}/models/{model['id']}", None))
    if state.get("provider_id"):
        steps.append(("delete provider", "DELETE", f"/api/v1/modelhub/providers/{state['provider_id']}", None))
    if state.get("secret_id"):
        steps.append(("delete secret", "DELETE", f"/api/v1/secrets/{state['secret_id']}", None))
    failed = False
    for label, method, path, body in steps:
        try:
            admin.api(method, path, json_body=body)
            print(f"ok   {label}")
        except PilotError as exc:
            failed = True
            print(f"FAIL {label}: {exc}", file=sys.stderr)
    host = state.get("egress_host_added")
    if host:
        egress = admin.api("GET", "/api/v1/security/egress/workspace")
        admin.api(
            "PUT",
            "/api/v1/security/egress/workspace",
            json_body={
                "allowlist": [entry for entry in egress.get("allowlist") or [] if entry != host],
                "blocklist": list(egress.get("blocklist") or []),
            },
        )
        print(f"ok   egress {host} removed")
    if failed:
        raise PilotError("teardown left something behind; see above")
    state_path.unlink()
    print(f"teardown done; {state_path} removed")


def main() -> int:
    parser = argparse.ArgumentParser(description="SOIT gateway pilot: setup, check, teardown")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--config", type=Path, default=Path("pilot.json"))
    s.add_argument("--state", type=Path, default=Path("pilot-state.json"))
    c = sub.add_parser("check")
    c.add_argument("--state", type=Path, default=Path("pilot-state.json"))
    c.add_argument("--out", type=Path, default=Path("."))
    t = sub.add_parser("teardown")
    t.add_argument("--state", type=Path, default=Path("pilot-state.json"))
    args = parser.parse_args()
    try:
        if args.command == "setup":
            setup(args.config, args.state)
            return 0
        if args.command == "check":
            acceptance = Acceptance(json.loads(args.state.read_text(encoding="utf-8")))
            acceptance.all()
            return write_report(acceptance, args.out)
        teardown(args.state)
        return 0
    except PilotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
