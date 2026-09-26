"""``soit``: sign in, run an agent, replay regressions on a model, export evidence.

Results go to standard output, progress and errors to standard error. Exit
codes: 0 success, 1 a refusal or failure, 2 a usage error, 3 a model replay
that found regressions when ``--fail-on-regression`` asked to fail on them.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from soit_cli import __version__, config
from soit_cli.client import SoitClient, SoitError
from soit_cli.config import Credentials

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REGRESSED = 3
LEDGER_KINDS = ("runs", "steps", "costs", "audit", "events")


def _err(message: str) -> None:
    print(f"soit: {message}", file=sys.stderr)


def _percent(rate: float | None) -> str:
    return "-" if rate is None else f"{rate * 100:.1f}%"


def _signed(value: float | None, unit: str = "", digits: int = 0) -> str:
    if value is None:
        return "-"
    return f"{value:+.{digits}f}{unit}"


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _login(args: argparse.Namespace, transport: httpx.BaseTransport | None) -> int:
    stored = config.load()
    url = (args.url or (stored.url if stored else config.DEFAULT_URL)).rstrip("/")
    if args.api_key_stdin:
        api_key = sys.stdin.readline().strip()
    else:
        api_key = args.api_key or getpass.getpass("SOIT API key: ").strip()
    if not api_key:
        _err("an API key is required")
        return EXIT_FAILED
    credentials = Credentials(url=url, api_key=api_key, workspace_id=args.workspace)
    client = SoitClient(credentials, transport=transport)
    try:
        who = _identity(client)
    finally:
        client.close()
    path = config.save(credentials)
    print(f"Signed in to {url} as {who}")
    print(f"Saved to {path}", file=sys.stderr)
    return EXIT_OK


def _identity(client: SoitClient) -> str:
    try:
        me = client.me()
    except SoitError as exc:
        if exc.status != 404:
            raise
        # A key issued to a service principal has no user profile to show.
        client.tools()
        return "a service principal"
    workspace = me.get("workspace_id") or "-"
    role = me.get("workspace_role") or "-"
    return f"{me.get('email') or me.get('id')} (workspace {workspace}, {role})"


def _logout(_args: argparse.Namespace, _transport: httpx.BaseTransport | None) -> int:
    print("Signed out" if config.remove() else "Not signed in")
    return EXIT_OK


def _whoami(client: SoitClient, _args: argparse.Namespace) -> int:
    print(f"{client.url}: {_identity(client)}")
    return EXIT_OK


def _run(client: SoitClient, args: argparse.Namespace) -> int:
    result = client.run_agent(args.agent_id, args.input, thread_id=args.thread)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result.get("output") or "")
        tokens = int(result.get("tokens_prompt") or 0) + int(result.get("tokens_completion") or 0)
        print(
            f"run {result.get('run_id')}, {result.get('model')}, {tokens} tokens"
            f", cost {result.get('cost_total') or 0}, thread {result.get('thread_id')}",
            file=sys.stderr,
        )
    return EXIT_OK


def _eval(client: SoitClient, args: argparse.Namespace) -> int:
    print(f"Replaying regression sets on {args.model_ref}...", file=sys.stderr)
    replay = client.model_replay(
        args.model_ref,
        agent_ids=args.agent or None,
        dataset=args.dataset,
        max_cases=args.max_cases,
    )
    totals = replay.get("totals") or {}
    if args.json:
        print(json.dumps(replay, indent=2, ensure_ascii=False))
    else:
        _print_replay(replay)
    regressed = int(totals.get("regressed") or 0)
    if args.fail_on_regression and regressed:
        _err(f"{regressed} case(s) pass on the current model and fail on {args.model_ref}")
        return EXIT_REGRESSED
    return EXIT_OK


def _print_replay(replay: dict[str, Any]) -> None:
    rows = [("AGENT/DATASET", "CURRENT MODEL", "PASS RATE", "AVG LATENCY", "COST", "REGRESSED", "FIXED")]
    for subject in replay.get("subjects") or []:
        before, after = subject["baseline"], subject["candidate"]
        rows.append(
            (
                f"{subject['agent_name']}/{subject['dataset']}",
                subject.get("baseline_model_ref") or "-",
                f"{_percent(before['pass_rate'])} -> {_percent(after['pass_rate'])}",
                f"{before['avg_latency_ms']}ms -> {after['avg_latency_ms']}ms",
                f"{before['total_cost_amount']} -> {after['total_cost_amount']}",
                str(len(subject.get("regressed") or [])),
                str(len(subject.get("fixed") or [])),
            )
        )
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip())
    totals = replay.get("totals") or {}
    delta = totals.get("delta") or {}
    print(
        f"\n{replay.get('case_count')} cases on {replay.get('model_ref')}:"
        f" pass rate {_percent((totals.get('baseline') or {}).get('pass_rate'))}"
        f" -> {_percent((totals.get('candidate') or {}).get('pass_rate'))}"
        f" ({_signed(None if delta.get('pass_rate') is None else delta['pass_rate'] * 100, ' pt', 1)}),"
        f" latency {_signed(delta.get('avg_latency_ms'), 'ms')},"
        f" cost {_signed(delta.get('total_cost_amount'), '', 6)};"
        f" {totals.get('regressed', 0)} regressed, {totals.get('fixed', 0)} fixed"
    )
    for skipped in totals.get("skipped") or []:
        print(f"skipped {skipped['agent_name']}: {skipped['reason']}", file=sys.stderr)
    print(f"replay {replay.get('id')}", file=sys.stderr)


def _export(client: SoitClient, args: argparse.Namespace) -> int:
    if args.what == "evidence":
        if not args.run_id:
            _err("export evidence needs a run id")
            return EXIT_FAILED
        filename, content, digest = client.evidence(args.run_id)
        path = _write(Path(args.output) if args.output else Path(filename), content)
        print(path)
        print(f"sha256 {digest}, checked against the server's digest", file=sys.stderr)
        return EXIT_OK
    if not args.since:
        _err(f"export {args.what} needs --since")
        return EXIT_FAILED
    filename, content, schema = client.export(args.what, since=args.since, until=args.until, fmt=args.format)
    if args.output == "-":
        sys.stdout.buffer.write(content)
        return EXIT_OK
    path = _write(Path(args.output) if args.output else Path(filename), content)
    print(path)
    if schema:
        print(f"ledger contract {schema}", file=sys.stderr)
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soit", description="Command-line client for SOIT.")
    parser.add_argument("--version", action="version", version=f"soit {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    login = commands.add_parser("login", help="sign in with an API key and remember it")
    login.add_argument("--url", help=f"the SOIT API address (default {config.DEFAULT_URL})")
    key = login.add_mutually_exclusive_group()
    key.add_argument("--api-key", help="the API key; prompted for when omitted")
    key.add_argument("--api-key-stdin", action="store_true", help="read the API key from standard input")
    login.add_argument("--workspace", help="the workspace, for a session token that spans several")
    login.set_defaults(handler=_login, signed_in=False)

    logout = commands.add_parser("logout", help="forget the stored API key")
    logout.set_defaults(handler=_logout, signed_in=False)

    whoami = commands.add_parser("whoami", help="show who the stored key signs in as")
    whoami.set_defaults(handler=_whoami, signed_in=True)

    run = commands.add_parser("run", help="run an agent's published version once")
    run.add_argument("agent_id")
    run.add_argument("input", help="the message for the agent")
    run.add_argument("--thread", help="continue this thread")
    run.add_argument("--json", action="store_true", help="print the whole result as JSON")
    run.set_defaults(handler=_run, signed_in=True)

    evaluate = commands.add_parser(
        "eval", help="replay agents' regression sets on a model next to the one they use"
    )
    evaluate.add_argument("model_ref", help="the candidate model, e.g. model:openai:gpt-6")
    evaluate.add_argument("--agent", action="append", help="replay this agent only (repeatable)")
    evaluate.add_argument("--dataset", help="replay this dataset only")
    evaluate.add_argument("--max-cases", type=int, help="refuse a replay that would run more cases (server default 50)")
    evaluate.add_argument("--json", action="store_true", help="print the whole replay as JSON")
    evaluate.add_argument(
        "--fail-on-regression",
        action="store_true",
        help=f"exit {EXIT_REGRESSED} when a case passes on the current model and fails on the candidate",
    )
    evaluate.set_defaults(handler=_eval, signed_in=True)

    export = commands.add_parser("export", help="export a run's evidence bundle, or ledger records")
    export.add_argument("what", choices=("evidence", *LEDGER_KINDS))
    export.add_argument("run_id", nargs="?", help="the run, for evidence")
    export.add_argument("--since", help="ledger exports: the window's start (ISO 8601)")
    export.add_argument("--until", help="ledger exports: the window's end (default now)")
    export.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    export.add_argument("-o", "--output", help="the file to write; '-' writes ledger records to standard output")
    export.set_defaults(handler=_export, signed_in=True)
    return parser


def main(argv: Sequence[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.signed_in:
            return args.handler(args, transport)
        credentials = config.load()
        if credentials is None:
            _err("not signed in: run `soit login`, or set SOIT_API_URL and SOIT_API_KEY")
            return EXIT_FAILED
        client = SoitClient(credentials, transport=transport)
        try:
            return args.handler(client, args)
        finally:
            client.close()
    except SoitError as exc:
        _err(str(exc))
        return EXIT_FAILED
    except KeyboardInterrupt:
        _err("interrupted")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
