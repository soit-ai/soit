# Archived specs

These cover the pre-rebuild pages backed up in `app/routes_old/`. The console
replaced those routes, so the specs drive URLs the app no longer serves and are
excluded from the suite by `testIgnore` in `playwright.config.ts`.

They are kept, not deleted, for the same reason the routes are: if something the
console has not absorbed turns out to be needed, the behaviour it had is written
down here. Delete this directory in the same change that deletes
`app/routes_old/`.

Not archived, because they still cover live code:

- `e2e/workflow.spec.ts` — the builder moved into `app/features/workflow-builder/`
  and the console mounts it, so these still exercise shipping code.
- `e2e/auth-extension.spec.ts` — sign-in was never replaced.
