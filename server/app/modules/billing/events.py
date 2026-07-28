"""Billing domain event types."""

CREDIT_BALANCE_LOW = "billing.credit.balance_low"
"""Published when a deduction crosses the low-balance or exhaustion threshold.

Payload: state ("low" | "exhausted"), balance, threshold, currency, run_id,
ledger_entry_id. Consumers must be idempotent per event_id.
"""
