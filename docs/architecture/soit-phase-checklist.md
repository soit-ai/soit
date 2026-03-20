# SOIT Phase Checklist

Use this checklist at the end of every refactor phase.

## Required Output

- Migrated objects
- Unmigrated objects
- Transitional aliases
- Removal plan
- Risks
- Verification status

## Review Questions

1. Did this phase reduce dependence on retired platform families?
2. Did this phase avoid adding new transitional-first concepts?
3. Did this phase move execution closer to a single Runtime Core?
4. Did tests or scripts validate the new boundary?
5. Is there a documented rollback point?

## Acceptance Template

```text
Phase:
Date:

Migrated objects:
- ...

Unmigrated objects:
- ...

Transitional aliases:
- ...

Removal plan:
- ...

Risks:
- ...

Verification:
- tests:
- scripts:
- manual:

Decision:
- accepted / needs follow-up
```
