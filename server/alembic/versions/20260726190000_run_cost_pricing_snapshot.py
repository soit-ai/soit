"""Add pricing snapshots and consolidate historical usage/charge pairs.

Revision ID: 20260726190000
Revises: 20260723160000
Create Date: 2026-07-26 19:00:00
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260726190000"
down_revision: Union[str, Sequence[str], None] = "20260723160000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _decimal_text(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _legacy_snapshot(row: Mapping[str, object]) -> dict[str, object]:
    quantities: dict[str, object] = {
        "quantity": _decimal_text(row["quantity"]),
    }
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if row[key] is not None:
            quantities[key] = int(row[key])
    amount = _decimal_text(row["amount"])
    return {
        "schema_version": 1,
        "source": "legacy_migration",
        "priced": row["amount"] is not None,
        "reason": "pricing_configuration_unavailable_for_legacy_entry",
        "migration_action": row.get("_migration_action", "snapshot_backfilled"),
        "model": {
            "requested": row["model_ref"],
            "resolved": row["model_ref"],
            "upstream": row["upstream_model"],
        },
        "provider": {
            "name": row["provider"],
            "id": row["provider_id"],
            "slug": row["provider_slug"],
            "kind": row["provider_kind"],
        },
        "billing_basis": row["unit"],
        "billing_unit": None,
        "unit_size": None,
        "rates": {},
        "quantities": quantities,
        "currency": row["currency"],
        "amount": amount,
        "configured_pricing": {},
    }


def _candidate_score(
    charge: Mapping[str, object],
    usage: Mapping[str, object],
) -> int | None:
    if usage["entry_type"] != "usage":
        return None
    if charge["run_id"] != usage["run_id"] or charge["step_id"] != usage["step_id"]:
        return None
    if usage["unit"] in {"ms", "milliseconds"}:
        return None

    score = 0
    has_signal = False
    for key in (
        "provider_id",
        "provider_slug",
        "provider_kind",
        "provider",
        "model_ref",
        "upstream_model",
        "tool_ref",
    ):
        charge_value = charge[key]
        usage_value = usage[key]
        if charge_value is not None and usage_value is not None:
            if charge_value != usage_value:
                return None
            score += 4
            has_signal = True
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        charge_value = charge[key]
        usage_value = usage[key]
        if charge_value is not None and usage_value is not None:
            if charge_value != usage_value:
                return None
            score += 3
            has_signal = True
    if charge["unit"] == usage["unit"]:
        score += 2
        has_signal = True
    if charge["quantity"] == usage["quantity"]:
        score += 1
        has_signal = True

    if charge["step_id"] is None and not has_signal:
        return None
    return score


def _choose_usage_candidate(
    charge: Mapping[str, object],
    usage_rows: list[dict[str, object]],
) -> dict[str, object] | None:
    scored = [
        (score, usage)
        for usage in usage_rows
        if (score := _candidate_score(charge, usage)) is not None
    ]
    if not scored:
        return None
    return max(scored, key=lambda item: item[0])[1]


def _amount_sum(left: object | None, right: object | None) -> Decimal | None:
    if left is None and right is None:
        return None
    return Decimal(str(left or 0)) + Decimal(str(right or 0))


def upgrade() -> None:
    op.add_column(
        "run_cost_entries",
        sa.Column(
            "pricing_snapshot_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    cost_entries = sa.table(
        "run_cost_entries",
        sa.column("id", sa.String()),
        sa.column("run_id", sa.String()),
        sa.column("step_id", sa.String()),
        sa.column("entry_type", sa.String()),
        sa.column("currency", sa.String()),
        sa.column("amount", sa.Numeric(18, 6)),
        sa.column("unit", sa.String()),
        sa.column("quantity", sa.Numeric(18, 6)),
        sa.column("provider", sa.String()),
        sa.column("provider_id", sa.String()),
        sa.column("provider_slug", sa.String()),
        sa.column("provider_kind", sa.String()),
        sa.column("model_ref", sa.String()),
        sa.column("upstream_model", sa.String()),
        sa.column("tool_ref", sa.String()),
        sa.column("prompt_tokens", sa.Integer()),
        sa.column("completion_tokens", sa.Integer()),
        sa.column("total_tokens", sa.Integer()),
        sa.column("pricing_snapshot_json", sa.JSON()),
    )
    connection = op.get_bind()
    rows = [dict(row) for row in connection.execute(sa.select(cost_entries)).mappings()]
    usage_rows = [row for row in rows if row["entry_type"] == "usage"]
    remaining_rows = {str(row["id"]): row for row in rows}

    for charge in (row for row in rows if row["entry_type"] == "charge"):
        candidate = _choose_usage_candidate(charge, usage_rows)
        charge_currency = charge["currency"]
        candidate_currency = candidate["currency"] if candidate else None
        currencies_compatible = (
            not charge_currency
            or not candidate_currency
            or charge_currency == candidate_currency
        )
        if candidate is not None and currencies_compatible:
            candidate["currency"] = candidate_currency or charge_currency
            candidate["amount"] = _amount_sum(candidate["amount"], charge["amount"])
            candidate["_migration_action"] = "usage_charge_merged"
            connection.execute(
                cost_entries.update()
                .where(cost_entries.c.id == candidate["id"])
                .values(
                    currency=candidate["currency"],
                    amount=candidate["amount"],
                )
            )
            connection.execute(
                cost_entries.delete().where(cost_entries.c.id == charge["id"])
            )
            remaining_rows.pop(str(charge["id"]), None)
            continue

        charge["entry_type"] = "usage"
        charge["_migration_action"] = "orphan_charge_converted"
        update_values: dict[str, object] = {"entry_type": "usage"}
        if candidate is not None:
            charge["unit"] = "charge_adjustment"
            charge["quantity"] = Decimal("0")
            charge["prompt_tokens"] = None
            charge["completion_tokens"] = None
            charge["total_tokens"] = None
            charge["_migration_action"] = "currency_conflict_preserved_as_adjustment"
            update_values.update(
                unit="charge_adjustment",
                quantity=Decimal("0"),
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
            )
        connection.execute(
            cost_entries.update()
            .where(cost_entries.c.id == charge["id"])
            .values(**update_values)
        )
        usage_rows.append(charge)

    for row in remaining_rows.values():
        connection.execute(
            cost_entries.update()
            .where(cost_entries.c.id == row["id"])
            .values(pricing_snapshot_json=_legacy_snapshot(row))
        )


def downgrade() -> None:
    op.drop_column("run_cost_entries", "pricing_snapshot_json")
