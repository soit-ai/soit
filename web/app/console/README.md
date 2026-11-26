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

## No fixtures

The console carries no invented data. The marketplace fixtures and the
licence tiles that once lived in a `mocks/` directory were removed when the
tiles started reading the licence; every figure on a screen now reads its
service, and anything a service cannot answer is a dash or an inert,
labelled control with a `BACKEND-PENDING` marker.
