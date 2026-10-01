"""``soit``: sign in, run an agent, evaluate it, manage datasets, export evidence.

Results go to standard output, progress and errors to standard error. Exit
codes: 0 success, 1 a refusal or failure, 2 a usage error, 3 a model replay or
an evaluation run that found regressions (or failures) when
``--fail-on-regression`` (or ``--fail-on-failure``) asked to fail on them.
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
import yaml

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


def _eval_run(client: SoitClient, args: argparse.Namespace) -> int:
    target = f" on {args.model}" if args.model else ""
    print(f"Running dataset {args.dataset}{target}...", file=sys.stderr)
    report = client.run_evaluation(
        args.agent_id,
        dataset=args.dataset,
        version_id=args.version,
        model_ref=args.model,
        max_cases=args.max_cases,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_report(report)
    regressed = len(report.get("regressed_case_ids_json") or [])
    failed = int((report.get("summary_json") or {}).get("failed") or 0)
    if args.fail_on_regression and regressed:
        _err(f"{regressed} case(s) passed in the baseline and fail now")
        return EXIT_REGRESSED
    if args.fail_on_failure and failed:
        _err(f"{failed} case(s) failed")
        return EXIT_REGRESSED
    return EXIT_OK


def _print_report(report: dict[str, Any]) -> None:
    regressed = set(report.get("regressed_case_ids_json") or [])
    fixed = set(report.get("fixed_case_ids_json") or [])
    rows = [("CASE", "RESULT", "LATENCY", "WHY")]
    for case in report.get("case_results_json") or []:
        marks = [mark for mark, ids in (("regressed", regressed), ("fixed", fixed)) if case.get("case_id") in ids]
        reasons = "; ".join(case.get("failure_reasons") or [])
        why = " ".join(part for part in (reasons, f"({', '.join(marks)})" if marks else "") if part)
        rows.append(
            (
                str(case.get("name") or case.get("case_id")),
                "pass" if case.get("passed") else "FAIL",
                f"{case.get('latency_ms', 0)}ms",
                why,
            )
        )
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip())
    summary = report.get("summary_json") or {}
    total = int(summary.get("total") or 0)
    passed = int(summary.get("passed") or 0)
    baseline = report.get("baseline_report_id")
    print(
        f"\n{passed}/{total} cases passed ({_percent(passed / total if total else None)})"
        f" on {report.get('dataset')} r{report.get('dataset_revision')},"
        f" version {report.get('subject_version_id')};"
        + (
            f" {len(regressed)} regressed, {len(fixed)} fixed against {baseline}"
            if baseline
            else " no comparable baseline yet"
        )
    )
    if summary.get("model_ref"):
        print(f"ran on {summary['model_ref']}: this report is never a baseline", file=sys.stderr)
    print(f"report {report.get('id')}", file=sys.stderr)


def _find_dataset(client: SoitClient, reference: str, agent_id: str | None) -> dict[str, Any] | None:
    """A dataset by id, or by name (for one agent when several share it); None if there is none."""
    matches = [
        item
        for item in client.list_datasets(agent_id=agent_id)
        if item["id"] == reference or item["name"] == reference
    ]
    if len(matches) > 1:
        agents = ", ".join(sorted(item["subject_id"] for item in matches))
        raise SoitError(f"{len(matches)} datasets are named {reference!r} (agents {agents}); name one with --agent")
    return matches[0] if matches else None


def _resolve_dataset(client: SoitClient, reference: str, agent_id: str | None) -> dict[str, Any]:
    dataset = _find_dataset(client, reference, agent_id)
    if dataset is None:
        raise SoitError(f"no dataset {reference!r}" + (f" for agent {agent_id}" if agent_id else ""))
    return dataset


def _dataset_list(client: SoitClient, args: argparse.Namespace) -> int:
    datasets = client.list_datasets(agent_id=args.agent, archived=args.archived)
    if args.json:
        print(json.dumps(datasets, indent=2, ensure_ascii=False))
        return EXIT_OK
    rows = [("ID", "NAME", "AGENT", "REV", "CASES", "LATEST REPORT")]
    for item in datasets:
        latest = item.get("latest_report")
        if latest:
            state = "pass" if latest["passed"] else "FAIL"
            summary = f"{state} {latest['passed_count']}/{latest['total']} (r{latest['dataset_revision']})"
        else:
            summary = "never run"
        revision, cases = f"r{item['revision']}", str(item["case_count"])
        rows.append((item["id"], item["name"], item["subject_id"], revision, cases, summary))
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip())
    return EXIT_OK


def _dataset_export(client: SoitClient, args: argparse.Namespace) -> int:
    dataset = _resolve_dataset(client, args.dataset, args.agent)
    content = client.export_dataset(dataset["id"])
    if not args.output or args.output == "-":
        sys.stdout.write(content)
        return EXIT_OK
    path = _write(Path(args.output), content.encode("utf-8"))
    print(path)
    print(f"{dataset['case_count']} cases from {dataset['name']} r{dataset['revision']}", file=sys.stderr)
    return EXIT_OK


def _dataset_import(client: SoitClient, args: argparse.Namespace) -> int:
    content = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    dataset = _find_dataset(client, args.dataset, args.agent)
    if dataset is None:
        if not (args.create and args.agent):
            raise SoitError(f"no dataset {args.dataset!r}; name its agent with --agent and pass --create to create it")
        dataset = client.create_dataset(args.agent, args.dataset)
        print(f"created dataset {dataset['name']} ({dataset['id']})", file=sys.stderr)
    try:
        result = client.import_dataset(dataset["id"], content, note=args.note or "")
    except SoitError as exc:
        # A refused file is refused whole; list every line so one run fixes them all.
        errors = exc.details.get("errors")
        if isinstance(errors, list) and errors:
            for item in errors:
                line = item.get("line")
                where = f"{args.file}:{line}" if line else args.file
                print(f"{where}: {item.get('message')}", file=sys.stderr)
            total = exc.details.get("error_count", len(errors))
            _err(f"{exc.args[0]} ({total} problem{'s' if total != 1 else ''})")
            return EXIT_FAILED
        raise
    imported = result["dataset"]
    print(dataset["id"])
    print(
        f"imported {result['imported']} cases into {imported['name']}, now r{imported['revision']}"
        f" with {imported['case_count']} cases",
        file=sys.stderr,
    )
    return EXIT_OK


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


def _agent_export(client: SoitClient, args: argparse.Namespace) -> int:
    document = client.export_agent(args.agent_id)
    # YAML, for people and version control; the API speaks the same document as JSON.
    text = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
    if not args.output or args.output == "-":
        sys.stdout.write(text)
        return EXIT_OK
    path = _write(Path(args.output), text.encode("utf-8"))
    print(path)
    return EXIT_OK


def _agent_import(client: SoitClient, args: argparse.Namespace) -> int:
    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    document = yaml.safe_load(raw)
    if not isinstance(document, dict):
        _err(f"{args.file} is not an agent file")
        return EXIT_FAILED
    if args.name:
        agent = document.setdefault("agent", {})
        if isinstance(agent, dict):
            agent["name"] = args.name
    result = client.import_agent(document)
    agent_id = result.get("agent", {}).get("id", "")
    version = result.get("version") or {}
    print(agent_id)
    what = f"version {version.get('version')} as a draft" if version else "no version"
    print(f"imported {result.get('agent', {}).get('name', '')} as {agent_id}, {what}", file=sys.stderr)
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
        "eval",
        help="replay agents' regression sets on a model next to the one they use (`eval run`: run one dataset)",
        epilog="`soit eval run AGENT_ID` runs one dataset on one agent; see `soit eval run --help`.",
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

    agent = commands.add_parser("agent", help="move an agent in or out as a file")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True, metavar="ACTION")
    agent_export = agent_commands.add_parser("export", help="write an agent and its version's spec as YAML")
    agent_export.add_argument("agent_id")
    agent_export.add_argument("-o", "--output", help="the file to write (default: standard output)")
    agent_export.set_defaults(handler=_agent_export, signed_in=True)
    agent_import = agent_commands.add_parser("import", help="create an agent, and its draft version, from a file")
    agent_import.add_argument("file", help="the YAML or JSON agent file; '-' reads standard input")
    agent_import.add_argument("--name", help="the name for the new agent, instead of the file's")
    agent_import.set_defaults(handler=_agent_import, signed_in=True)

    dataset = commands.add_parser("dataset", help="list, export and import evaluation datasets")
    dataset_commands = dataset.add_subparsers(dest="dataset_command", required=True, metavar="ACTION")
    dataset_list = dataset_commands.add_parser("list", help="list the workspace datasets")
    dataset_list.add_argument("--agent", help="only this agent's datasets")
    dataset_list.add_argument("--archived", action="store_true", help="list archived datasets instead")
    dataset_list.add_argument("--json", action="store_true", help="print the datasets as JSON")
    dataset_list.set_defaults(handler=_dataset_list, signed_in=True)
    dataset_export = dataset_commands.add_parser("export", help="write a dataset as JSONL")
    dataset_export.add_argument("dataset", help="the dataset id or name")
    dataset_export.add_argument("--agent", help="the agent, when several have a dataset of that name")
    dataset_export.add_argument("-o", "--output", help="the file to write (default: standard output)")
    dataset_export.set_defaults(handler=_dataset_export, signed_in=True)
    dataset_import = dataset_commands.add_parser(
        "import", help="add the cases of a JSONL file to a dataset, all or none"
    )
    dataset_import.add_argument("dataset", help="the dataset id or name")
    dataset_import.add_argument("file", help="the JSONL file; '-' reads standard input")
    dataset_import.add_argument("--agent", help="the agent, when several have a dataset of that name")
    dataset_import.add_argument(
        "--create", action="store_true", help="create the dataset first if it does not exist (needs --agent)"
    )
    dataset_import.add_argument("--note", help="a note for the dataset's new revision")
    dataset_import.set_defaults(handler=_dataset_import, signed_in=True)

    export = commands.add_parser("export", help="export a run's evidence bundle, or ledger records")
    export.add_argument("what", choices=("evidence", *LEDGER_KINDS))
    export.add_argument("run_id", nargs="?", help="the run, for evidence")
    export.add_argument("--since", help="ledger exports: the window's start (ISO 8601)")
    export.add_argument("--until", help="ledger exports: the window's end (default now)")
    export.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    export.add_argument("-o", "--output", help="the file to write; '-' writes ledger records to standard output")
    export.set_defaults(handler=_export, signed_in=True)
    return parser


def _eval_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soit eval run",
        description="Run a dataset on an agent version now and print the report it records.",
    )
    parser.add_argument("agent_id")
    parser.add_argument("--dataset", default="default", help="the dataset name (default: default)")
    parser.add_argument("--version", help="the agent version to run (default: the published one)")
    parser.add_argument("--model", help="run on this model; the report is then never a baseline")
    parser.add_argument("--max-cases", type=int, help="refuse a run with more cases (server default 50, at most 200)")
    parser.add_argument("--json", action="store_true", help="print the whole report as JSON")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help=f"exit {EXIT_REGRESSED} when a case that passed in the baseline fails now",
    )
    parser.add_argument(
        "--fail-on-failure",
        action="store_true",
        help=f"exit {EXIT_REGRESSED} when any case fails, as the publish gate would",
    )
    parser.set_defaults(handler=_eval_run, signed_in=True)
    return parser


def main(argv: Sequence[str] | None = None, *, transport: httpx.BaseTransport | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    # `eval run` is a second use of `eval`, whose own argument is a model ref
    # (never "run"), so it is told apart here rather than inside argparse.
    if arguments[:2] == ["eval", "run"]:
        args = _eval_run_parser().parse_args(arguments[2:])
    else:
        args = _parser().parse_args(arguments)
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
