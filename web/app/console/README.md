# Console

The operator console. Every figure on a screen is either a measurement read
from a service, or it is absent — a zero that was never counted reads as a
quiet day, which is worse than a dash.

## `BACKEND-PENDING`

Where the design shows something no service can answer yet, the code carries a
`BACKEND-PENDING` comment naming what is missing. Grep for it to see the whole
list:

```bash
grep -rn "BACKEND-PENDING" app/console
```

Each marker falls into one of two kinds, and says which:

- **Edition boundary.** The capability belongs to SOIT Enterprise or SOIT Cloud
  and Community will not grow it — SSO, seat licensing and invoicing, settable
  audit-log access. See "Open source and commercial editions" in the repository
  README. These markers are permanent.
- **Not built.** The capability fits Community but no endpoint exists yet. The
  marker names the endpoint that has to ship. These are removed by shipping it,
  not by deleting the comment.

A marker is not a licence to invent a figure. Where a control has no backend it
is inert and labelled, and where a number has no source the cell shows a dash.

## `mocks/`

Fixtures live in `mocks/` rather than inline, so that a grep for `mocks/` finds
every invented figure in the console and deleting a file is enough to retire
one. What remains here is the design of features that do not exist server-side:

- `build-agents.ts` — the agent marketplace. No catalogue or install endpoint
  exists.
- `tiles.ts` — the seat cap and renewal date on the Settings seats tile. Its
  numerator is the live member count; licensing is a Cloud concern.

Anything else that once lived here now reads its service.
