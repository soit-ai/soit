# Replaying regression sets on a new model

When a new model generation arrives, the question is not whether it is better
in general but whether your agents still do what their regression sets say
they must. A model replay answers that in one step: every regression case of
every agent (or the ones you pick) runs on the model the agent uses today and
on the candidate model, and the two are compared on pass rate, latency and
cost.

## What runs

- An agent's regression cases are the cases of its [datasets](evaluations.md):
  written in the console, imported from JSONL, or frozen from a past run with
  `POST /api/v1/evaluations/regression-cases/from-run`. They are the same cases
  that gate the agent's publishes.
- Each case runs twice, against the agent's **published** version: once on
  the model that version binds, once on the candidate. Both run now, so
  neither side is measured against a stale report.
- Every run is a rehearsal (`sandbox`): tools are answered at the boundary
  and never called, and the runs are kept out of spend, dashboards and
  alerts, like a publish gate's.
- Cases are judged exactly as in a publish gate: required output terms,
  latency and cost ceilings, and the LLM judge when a case asks for one. A
  run that fails outright fails its case.
- Agents without a published version, or without cases, are listed as
  skipped.

## Running a regression set on demand

The evaluation the publish gate makes can be run at any time, on the version
that is published or on a draft, and its report is recorded the same way:

```
POST /api/v1/evaluations/run
{"subject_id": "agt_…", "subject_version_id": "ver_…", "dataset": "smoke", "model_ref": "model:openai:gpt-6", "max_cases": 50}
```

Only `subject_id` is required: the published version and the `default`
dataset are taken when nothing else is named, and an agent with no published
version needs `subject_version_id`. Every case runs as a rehearsal before the
request answers with the report (`201`, the same shape as
`regression-reports/latest`), compared to the last comparable report as a
publish would be. With `model_ref` the cases run on that model instead of the
version's own: the report carries `model_ref` in its summary and is never a
baseline, since it measures another model. An evaluation that would run more
than `max_cases` cases (at most 200), or has no cases to run, is refused
before anything runs. The request needs workspace write access.

## Starting one

In the console: **Build › Models › Regression replays**, **Replay on a
model**, pick the candidate, optionally one dataset and a cap on the number
of cases. Or through the API:

```
POST /api/v1/evaluations/model-replays
{"model_ref": "model:openai:gpt-6", "agent_ids": ["agt_…"], "dataset": "smoke", "max_cases": 50}
```

`agent_ids` and `dataset` are optional: without them every agent with cases,
and every dataset, is replayed. A replay that would run more cases than
`max_cases` (at most 200; each runs on both models) is refused before
anything runs, with the count. A candidate that cannot serve at all (not
configured, disabled, not allowed for the key) stops the replay with that
error rather than failing every case.

The request answers when every case has run. It needs workspace write
access.

## Reading the result

A replay records, per agent and dataset:

| Field | Meaning |
| ----- | ------- |
| `baseline_model_ref` | the model the published version binds |
| `baseline`, `candidate` | cases, passed, pass rate, average latency, total cost, run errors |
| `regressed` | cases that pass on the current model and fail on the candidate |
| `fixed` | cases that fail on the current model and pass on the candidate |
| `cases` | each case on both sides: result, latency, cost, run id, why it failed |

`totals` sums both sides over every agent, with the difference (candidate
minus baseline) in pass rate, average latency and cost, and lists the
skipped agents. `GET /api/v1/evaluations/model-replays` lists past replays;
`GET /api/v1/evaluations/model-replays/{id}` returns one with its agents.

A replay is evidence for a decision, not a gate: it never becomes the
baseline a publish is compared against, and it changes no agent. Switching
an agent to the new model is still a new version, which its own publish gate
then checks.

## Limits

- The request runs every case before it answers; keep replays within a few
  dozen cases, or narrow them by agent and dataset.
- Only agents' regression sets are replayed; workflows have none yet.
