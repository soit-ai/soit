# routes/tasks/

Runtime task center routes.

- `/tasks`: task center with workbench metrics, priority cards, and runtime ledger.
- `/tasks/processing`: task handling list; clicking a row opens the right-side handling drawer.
- `/tasks/:taskId`: detailed runtime task, events, and checkpoints.

Non-goals:

- Knowledge ingest tasks stay in the knowledge module UI.
- This route does not aggregate non-runtime task models.
