# Archived specs

These cover the pre-rebuild pages backed up in `app/routes_old/`. The console
replaced those routes, so the specs drive URLs the app no longer serves and are
excluded from the suite by `testIgnore` in `playwright.config.ts`.

They are kept, not deleted, for the same reason the routes are: if something the
console has not absorbed turns out to be needed, the behaviour it had is written
down here. Delete this directory in the same change that deletes
`app/routes_old/`.

`workflow-pages.spec.ts` is a split: the sixteen tests covering the pre-rebuild
workflow list, settings and permissions pages moved here, while the builder
tests stayed in `e2e/workflow.spec.ts` because the builder itself moved into
`app/features/workflow-builder/` and still ships. Its preamble is duplicated
rather than shared, since this directory is deleted as a unit.

Not archived, because they still cover live code:

- `e2e/workflow.spec.ts` — the builder the console mounts.
- `e2e/auth-extension.spec.ts` — sign-in was never replaced, and it is what
  caught the console shipping with no way to log out.
