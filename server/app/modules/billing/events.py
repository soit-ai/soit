"""Billing domain event types."""

CREDIT_BALANCE_LOW = "billing.credit.balance_low"
"""Published when a deduction crosses the low-balance or exhaustion threshold.

Payload: state ("low" | "exhausted"), balance, threshold, currency, run_id,
ledger_entry_id. Consumers must be idempotent per event_id.
"""

BUDGET_THRESHOLD_REACHED = "billing.budget.threshold_reached"
"""Published when a cost carries a budget's spend across one of its thresholds.

Payload: budget_id, budget_name, scope_kind, scope_id, period, period_start,
threshold (percent), percent, spent, amount, currency, hard_stop. One event per
budget, period and threshold: the event id is derived from the three.
"""
