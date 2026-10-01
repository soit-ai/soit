# Evaluation datasets

An evaluation asks whether an agent still does what a set of cases says it
must. The set is a **dataset**: a named, versioned list of cases for one
agent. Running it produces a **report** that says which cases passed, and,
against the last comparable report, which ones a change broke.

Datasets are the regression sets the publish gate and
[model replays](model-replays.md) already use, made into objects you can
create, edit, import, export and read the history of. Nothing about how those
runs work changed.

## Datasets and cases

- A dataset belongs to one agent and has a name, unique for that agent, and an
  optional description. The name cannot be changed: reports and the publish
  gate refer to a dataset by it.
- A **case** is an input and what a run must satisfy. Cases come from three
  places: written in the console or through the API, imported from a JSONL
  file, or frozen from a past run with
  `POST /api/v1/evaluations/regression-cases/from-run`. A case frozen from a
  run keeps a link to it; the others have none.
- A case is never deleted. Removing one, or archiving a dataset, takes it out
  of every run, the publish gate included, and keeps the row so reports and
  annotations that name it still read. Restoring an archived dataset puts back
  exactly the cases archiving took out.
- The publish gate runs the dataset named `default`. Cases frozen from a run
  always go there, and the dataset is created with the first one. A workspace
  whose cases all sit in other datasets has nothing in `default` for the gate
  to run.

## What a case asserts

`expected_features` holds at least one of:

| Key | Passes when |
| --- | ----------- |
| `minimum_output_terms` | every term appears in the output, compared case-insensitively |
| `max_latency_ms` | the run took no longer |
| `max_cost_amount` | the run cost no more |
| `llm_judge` | a judge model scores the output against `rubric` at or above `min_score` (default 0.7); `model` picks the judge |

A case that asserts nothing passes whatever the agent says, so one is refused.
A run that fails outright fails its case whatever it expected, and a case that
asks for a judge fails when no judge is configured rather than passing
unmeasured.

## The JSONL format

One case per line, each a JSON object validated against
`server/app/kernel/specs/v1/dataset_case_spec.schema.json`:

```jsonl
{"name":"refund-window","input":"How long do refunds take?","expected_features":{"minimum_output_terms":["14 days"],"max_latency_ms":4000}}
{"name":"angry-customer","input":{"messages":[{"role":"user","content":"This is the third time I am asking."}]},"expected_features":{"llm_judge":{"rubric":"Stays calm and offers a concrete next step","min_score":0.8}}}
```

- `name`: 1 to 255 characters, unique within the dataset.
- `input`: a string is the text sent to the agent. An object is stored as it
  is, and the agent is asked the content of the last user message of its
  `messages`, else its `input_summary`, else its `input`, else the object
  serialised as JSON.
- `expected_features`: as above; unknown keys are refused, so a misspelt
  expectation cannot quietly assert nothing.

Blank lines are skipped. Line numbers in errors count from 1 over the whole
file, blanks included. An export writes the same format back, so exporting a
dataset and importing the file into another reproduces the same cases and the
same content hash. A case frozen from a run whose input was empty exports with
an empty input, which an import refuses.

## Importing

`POST /api/v1/evaluations/datasets/{id}/import` takes `{"content": "<the
file's text>", "note": "…"}`. It is all or nothing: every line is checked
first, and a file with any invalid line imports nothing and answers `400` with
the line and message of every problem:

```json
{"success": false, "code": "VALIDATION_ERROR",
 "message": "2 of 3 lines are not valid cases; nothing was imported",
 "details": {"error_count": 2, "errors": [{"line": 2, "message": "not valid JSON: Expecting value"}, {"line": 3, "message": "/expected_features: {} should be non-empty"}]}}
```

Names that already exist in the dataset are refused together (`409`), as are
names repeated within the file. A file holds at most 1,000 cases and 2 MB, and
a dataset at most 5,000 active cases.

## Revisions and versions

Every change made through the dataset (adding, editing, removing or importing
cases) advances the dataset's **revision**, stamps the cases it touched with
it, and stores a **version**: the cases the dataset held at that revision, a
SHA-256 content hash that does not depend on their order, and how many were
added, removed and changed since the revision before. Editing a case keeps its
id, so reports that ran it still name it. Archiving and restoring change no
revision, since the cases are not edited.

A report records the revision it ran. Two reports are only comparable when
they ran the same one, so the baseline a run is compared against is the latest
report of the same dataset at the same revision (reports on another model are
never baselines). Change a dataset and the next run starts a new baseline.

`GET /api/v1/evaluations/datasets/{id}/versions` lists the revisions, newest
first; `…/versions/{revision}` returns one with its cases. Datasets that
existed before this feature were given one version at their current revision
by the migration.

## Running and reports

`POST /api/v1/evaluations/run` runs a dataset by name on an agent version, as
described in [model replays](model-replays.md#running-a-regression-set-on-demand):
every case runs as a rehearsal and the report is recorded. A dataset name with
cases but no dataset row (cases written directly) still runs.

- `GET /api/v1/evaluations/reports` lists reports, newest first, filtered by
  `subject_id`, `dataset` and `passed`, without per-case results; `with_total`
  adds the count.
- `GET /api/v1/evaluations/reports/{id}` returns one with every case's result,
  its `dataset`, `dataset_revision`, `baseline_report_id`, and the ids of the
  cases that **regressed** (passed in the baseline, fail now) and were
  **fixed**. A case that never passed is a known gap, not a regression.
- `GET /api/v1/evaluations/regression-reports/trend` is the pass-rate series
  the console draws.

## In the console

**Observe › Evaluations** lists datasets with their agent, revision, case
count and how the latest report went, and whether the dataset has changed since
it ran. **New dataset** can seed one from a JSONL file. A dataset opens to:

- **Cases**: add, edit and remove cases; the editor covers each expectation
  above. **Import JSONL** and **Export** are in the header.
- **Reports**: pass rate per report, and for the one picked each case's
  result, the judge's score, and the cases that regressed or were fixed
  against its baseline.
- **Versions**: each revision's size, content hash and change counts, with the
  cases it held.

**Run evaluation** runs the dataset on the published version, or a version
named, optionally on another model, and opens the report it records.

## Command line

```bash
soit dataset list [--agent ID]
soit dataset export refunds -o refunds.jsonl
soit dataset import refunds refunds.jsonl [--agent ID --create]
soit eval run AGENT_ID --dataset refunds --fail-on-regression
```

`eval run` exits `3` when a case that passed in the baseline fails now
(`--fail-on-regression`) or when any case fails (`--fail-on-failure`). See
[the CLI](../cli/README.md).

## Access and audit

Reading datasets, cases, versions, reports and exports needs workspace read
access; every change and every run needs write access. Datasets, cases and
reports are scoped to the workspace. Creating, changing, archiving, restoring,
importing and exporting a dataset, and adding, editing and removing a case,
are written to the audit ledger as `evaluation.dataset.created|updated|
archived|restored|imported|exported` and `evaluation.case.created|updated|
removed`, with the dataset, its revision and the caller.

## Limits

- Datasets are for agents; workflows have none yet.
- A run answers when every case has run, so keep a dataset within a few dozen
  cases per run, or raise `max_cases` knowingly (at most 200).
- A dataset's name cannot be changed.
