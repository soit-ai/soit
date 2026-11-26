# docs/ (web)

Frontend engineering docs and structure notes.

- `PROJECT_STRUCTURE.md`: frontend directory layout and the route map
- `CHAT.md`: web chat module overview and gaps
- Pages are declared in `app/routes.ts`; console pages live under `app/console/routes/`, grouped as build, execute, observe and govern
- Old top-level URLs redirect to their console pages through `app/console/routes/redirects/`
