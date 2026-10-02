# Gateway pilot kit

A repeatable way to stand up a SOIT gateway pilot and show, with evidence,
that it governs the calls an application makes: a model call is answered and
priced, keys and budgets refuse what they should, a failing provider fails
over, an unpriced call can be refused, a repeated tool call runs once, the
ledger reconciles per currency, and a run's evidence bundle checks itself.

| File | What it is |
| --- | --- |
| [`pilot_acceptance.py`](pilot_acceptance.py) | `setup`, `check` and `teardown` over the SOIT HTTP API. Needs Python 3.11+ and `httpx`. |
| [`pilot.example.json`](pilot.example.json) | The pilot's provider, models, prices and budget. Points at the mock by default. |
| [`mock_upstream.py`](mock_upstream.py) | A stand-in OpenAI-compatible provider, standard library only, to rehearse without real credentials. |
| [`pilot-record-template.md`](pilot-record-template.md) | What to record per pilot: onboarding time, failures and causes, upgrade and restore time, effort. |

## Rehearse it against the mock

1. Run SOIT with `EGRESS_PRIVATE_NETWORKS=["127.0.0.1/32"]` on the API
   process, so it may reach a provider on this machine. (Not needed for a
   real provider on a public address.)
2. Start the mock provider:

   ```bash
   python mock_upstream.py --port 9311
   ```

3. Sign in as a workspace owner or admin, then set up, check and clean up:

   ```bash
   export SOIT_ADMIN_EMAIL=owner@example.com SOIT_ADMIN_PASSWORD=...
   cp pilot.example.json pilot.json
   python pilot_acceptance.py setup --config pilot.json
   python pilot_acceptance.py check --state pilot-state.json
   python pilot_acceptance.py teardown --state pilot-state.json
   ```

   `SOIT_ADMIN_TOKEN` (a session token, or an API key with the `admin`
   scope) can replace the email and password; `SOIT_WORKSPACE_ID` picks a
   workspace other than the default one.

`setup` writes `pilot-state.json` with everything it created, including the
pilot API key's secret. Keep the file private; `teardown` revokes the key,
deletes the rest and removes the file.

## Run it for a real pilot

Copy `pilot.example.json` and change:

- `provider`: the customer's provider. `base_url` is its OpenAI-compatible
  address; `api_key_env` names the environment variable that holds its key,
  which `setup` stores as a SOIT secret and never writes to the state file.
- `models.primary`: a model the pilot calls, priced with `pricing` in the
  provider's own currency and rates (`mtok` is per million tokens; chat needs
  both an input and an output rate, or the calls are unpriced).
- `models.failing`: optional. A model id the provider refuses (for example
  one it does not serve), so the failover check sees a target fail and the
  next one answer. Without it the failover check is skipped.
- `models.unpriced`: optional. A second model registered without a price, for
  the unpriced-call check. Without it that check is skipped.
- `budget`: a small daily amount in the pricing currency. The budget check
  calls the primary model until the budget refuses, so this bounds what the
  check spends with the provider.

The application under pilot then points its OpenAI client at
`<soit_url>/v1` with its own SOIT API key; see [the gateway examples](../gateway/README.md).

## What `check` verifies

| Check | Passes when |
| --- | --- |
| API ready | `/health/ready` answers 200 |
| Allowed call | the primary model answers, the run is recorded, and its cost entry is `priced`, with the provider's ids when it gave them |
| Streamed call | the stream ends with a usage chunk and `[DONE]` |
| Invalid key | `401` |
| Model outside the key's list | `403` |
| Failover | the virtual model answers and its step records the failed target, then the one that answered |
| Unpriced call | with the workspace's unpriced call policy set to `refuse`, the unpriced model is refused with `403 pricing_not_configured`; the policy is put back after |
| Idempotent tool call | the same idempotency key twice opens one run and the second is a replay |
| Budget | the key's daily budget refuses with `402 budget_exhausted` once spent |
| Cost reconciliation | the key's entries since the run started have a priced total in the budget's currency and no unpriced model calls (the built-in tool is unpriced by design) |
| Evidence | the first run's evidence bundle downloads and its SHA-256 matches `X-SOIT-Evidence-SHA256` |

The report lands in `pilot-report.json` and `pilot-report.md`, one row per
check with its detail and timing; attach it to the [pilot record](pilot-record-template.md).
The checks call the gateway as the pilot application would, so they also
exercise the customer's network path to SOIT and SOIT's to the provider.

## Not covered by the script

Run these by hand and note them in the pilot record:

- An upstream timeout: point `models.primary` at a slow model (the mock's
  `pilot-slow`) with a short provider timeout and confirm the run fails with
  `TIMEOUT` and an estimated charge only when the provider was asked.
- Process recovery: stop the API during a long streamed call and confirm the
  run is closed and charged once after restart ([ledger](../../docs/ledger.md#charges-soit-estimates)).
- Backup, upgrade and restore: follow the [backup and restore runbook](../../docs/operations/backup-restore.md)
  and record the times.
- The provider's bill: compare it with `GET /api/v1/runs/costs/reconciliation`
  or **Observe › Costs** for the same window ([checking costs against a bill](../../docs/ledger.md#checking-costs-against-a-bill)).
