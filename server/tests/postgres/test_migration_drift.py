"""PostgreSQL contract: the migrated schema matches the models.

Unit and entrypoint tests build their SQLite schema from the models with
``create_all``, so a model change without a migration passes them and only
fails on a real database. This compares the database at ``alembic upgrade
head`` with the models and fails on any difference not listed below.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, types
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import UTCDateTime

import app.kernel.runtime.db.models  # noqa: F401
import app.modules  # noqa: F401
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.modules.modelhub.domain import models as _modelhub_models  # noqa: F401

# Differences that predate this check. Each is harmless as it stands; remove
# an entry when a migration or a model change resolves it, and never add one
# to make a new change pass.
KNOWN_DRIFT = {
    # Declared nullable in the model, created NOT NULL with a server default.
    ("modify_nullable", "api_keys", "scopes_json"),
    ("modify_nullable", "policy_revisions", "document_json"),
    ("modify_nullable", "regression_reports", "regressed_case_ids_json"),
    ("modify_nullable", "regression_reports", "fixed_case_ids_json"),
    ("modify_nullable", "schedules", "input_json"),
    ("modify_nullable", "user_mfa", "recovery_hashes_json"),
    ("modify_nullable", "workflow_runs", "inputs_json"),
    ("modify_nullable", "workflow_runs", "request_context_json"),
    # The migration named the index differently from the model's default.
    ("remove_index", "regression_reports", "ix_regression_reports_baseline"),
    ("add_index", "regression_reports", "ix_regression_reports_baseline_report_id"),
}


def _compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):  # noqa: ARG001
    # Timestamp columns are ``timestamp without time zone`` holding UTC by
    # design (see test_session_timezone_postgres); the models declare them
    # with SQLModel's aware UTCDateTime, which converts at the boundary.
    if isinstance(metadata_type, UTCDateTime) and isinstance(inspected_type, types.DateTime):
        return False
    return None  # Alembic's default comparison.


def _key(diff) -> tuple[str, str, str]:
    if isinstance(diff, list):  # Column-level changes come wrapped in a list.
        op = diff[0]
        return (op[0], op[2], op[3])
    op = diff[0]
    if op in {"add_column", "remove_column"}:  # (op, schema, table, column)
        return (op, diff[2], diff[3].name)
    obj = diff[1]
    table = getattr(obj, "table", obj)
    return (op, getattr(table, "name", ""), getattr(obj, "name", ""))


def test_migrated_schema_matches_the_models() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": _compare_type, "compare_server_default": False},
            )
            differences = compare_metadata(context, SQLModel.metadata)
    finally:
        engine.dispose()

    found = {_key(diff) for diff in differences}
    unexpected = sorted(found - KNOWN_DRIFT)
    assert not unexpected, (
        "The migrated schema differs from the models; add a migration "
        f"(alembic revision --autogenerate) for: {unexpected}"
    )
    resolved = sorted(KNOWN_DRIFT - found)
    assert not resolved, f"Drift resolved; remove it from KNOWN_DRIFT: {resolved}"
