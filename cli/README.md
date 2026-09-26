# soit: the SOIT command line

A small client for the SOIT API: sign in with an API key, run an agent,
replay regression sets on a new model, and take evidence out.

```bash
uv tool install ./cli        # or: pipx install ./cli
soit login --url https://soit.example.com
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
| `soit eval MODEL_REF [--agent ID]... [--dataset NAME] [--max-cases N] [--json] [--fail-on-regression]` | replay agents' regression sets on a model next to the one they use ([model replays](../docs/model-replays.md)) |
| `soit export evidence RUN_ID [-o FILE]` | save a run's evidence bundle, after checking it against the server's SHA-256 ([ledger](../docs/ledger.md)) |
| `soit export runs\|steps\|costs\|audit\|events --since ISO [--until ISO] [--format jsonl\|csv] [-o FILE\|-]` | save one kind of ledger record for a window |

Exit codes: `0` success, `1` a refusal or failure, `2` a usage error, `3` an
`eval --fail-on-regression` that found cases passing on the current model and
failing on the candidate, so a CI job can stop a model switch:

```bash
soit eval model:openai:gpt-6 --dataset smoke --fail-on-regression
```
