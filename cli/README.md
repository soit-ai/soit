# soit: the SOIT command line

A small client for the SOIT API: sign in with an API key, run an agent,
replay regression sets on a new model, run and manage evaluation datasets,
and take evidence out.

```bash
uv tool install soit-cli           # or: pipx install soit-cli
soit login --url https://soit.example.com
```

The package on PyPI is [`soit-cli`](https://pypi.org/project/soit-cli/);
the command it installs is `soit`. To run the checkout instead, for example
to try a change before it is released, install from the repository:

```bash
uv tool install ./cli        # or: pipx install ./cli
```

`soit login` asks for an API key (create one under **Settings › API**), checks
it, and stores it with the address in your configuration directory, readable
by you alone. In CI, set `SOIT_API_URL` and `SOIT_API_KEY` instead; the
environment wins over the stored file. `SOIT_CONFIG` names another file.

| Command | Does |
| ------- | ---- |
| `soit login [--url URL] [--api-key KEY \| --api-key-stdin]` | check a key and remember it |
| `soit whoami` | show who the stored key signs in as |
| `soit logout` | forget the stored key |
| `soit run AGENT_ID "message" [--thread ID] [--json]` | run an agent's published version once; the answer on stdout, the run on stderr |
| `soit eval MODEL_REF [--agent ID]... [--dataset NAME] [--max-cases N] [--json] [--fail-on-regression]` | replay agents' regression sets on a model next to the one they use ([model replays](https://github.com/soit-ai/soit/blob/main/docs/model-replays.md)) |
| `soit eval run AGENT_ID [--dataset NAME] [--version ID] [--model MODEL_REF] [--max-cases N] [--json] [--fail-on-regression] [--fail-on-failure]` | run one dataset on an agent now (the published version unless `--version`), print each case's result and the report it records ([evaluations](https://github.com/soit-ai/soit/blob/main/docs/evaluations.md)) |
| `soit dataset list [--agent ID] [--archived] [--json]` | list the workspace's datasets with revision, case count and latest report |
| `soit dataset export DATASET [--agent ID] [-o FILE]` | write a dataset's cases as JSONL (`DATASET` is its id or name; standard output by default) |
| `soit dataset import DATASET FILE [--agent ID] [--create] [--note TEXT]` | add the cases of a JSONL file, all or none: a file with any bad line imports nothing and every bad line is listed with its number; `--create --agent ID` creates the dataset first |
| `soit agent export AGENT_ID [-o FILE]` | write an agent and its published (or current) version's specification as YAML, without ids |
| `soit agent import FILE [--name NAME]` | create an agent, and its version as a draft, from such a file; the model, tool and knowledge refs it names must exist in the workspace |
| `soit export evidence RUN_ID [-o FILE]` | save a run's evidence bundle, after checking it against the server's SHA-256 ([ledger](https://github.com/soit-ai/soit/blob/main/docs/ledger.md)) |
| `soit export runs\|steps\|costs\|audit\|events --since ISO [--until ISO] [--format jsonl\|csv] [-o FILE\|-]` | save one kind of ledger record for a window |

Exit codes: `0` success, `1` a refusal or failure, `2` a usage error, `3` an
`eval --fail-on-regression` that found cases passing on the current model and
failing on the candidate, so a CI job can stop a model switch:

```bash
soit eval model:openai:gpt-6 --dataset smoke --fail-on-regression
```

`soit eval run` exits `3` the same way: with `--fail-on-regression` when a case
that passed in the report's baseline fails now, and with `--fail-on-failure`
when any case fails, as the publish gate would. A CI job can keep a dataset
in the repository and evaluate every change against it:

```bash
soit dataset import refunds evals/refunds.jsonl --agent agt_123 --create
soit eval run agt_123 --dataset refunds --fail-on-regression
```
