# SOIT 1.0 Owner UI Spot-check

Updated: March 11, 2026

## Goal

Provide a short, deterministic release-owner UI sweep before final sign-off.

## Spot-check Route List

1. `/`
   - Confirm dashboard loads and main navigation shows `Dashboard / Agents / Workflows / Knowledge / Chat / Tasks / Runs / Models / Settings`.
2. `/models`
   - Confirm provider list loads.
   - Confirm healthcheck and sync actions are visible.
3. `/knowledge`
   - Create a knowledge base.
   - Open its detail page and confirm `Manage Documents`, `Applications`, `Query Test`, `Analytics`, and `Settings` entries are present.
4. `/agents`
   - Create an agent.
   - Open detail page and confirm version creation and publish actions are available.
5. `/chat`
   - Confirm agent selector is available.
   - Start a thread and verify a response appears.
6. `/runs`
   - Filter by `subject_id` or `workflow_id`.
   - Open a run detail and confirm status, error, steps, and artifacts sections render.
7. `/workflow`
   - Create or open a workflow.
   - Save a builder version and open log/monitor views.
8. `/tasks`
   - Confirm list page loads with filters and detail navigation.
   - Open one task detail if runtime tasks exist.
9. `/settings`
   - Confirm overview loads.
   - Open `Team`, `API`, `Secrets`, and `Security`.

## Pass Criteria

- No blocking broken route.
- No blank core page.
- No missing primary navigation entry.
- No page trapped in an unrecoverable loading or error state.
- Main cross-links open the expected destination.

## Sign-off Record

- Date:
- Reviewer:
- Environment:
- Result: `Pass / Blocked / Needs follow-up`
- Notes:
