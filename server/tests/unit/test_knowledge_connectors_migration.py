"""The knowledge connectors migration creates what the models declare."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.modules.knowledge.domain.models import (
    KnowledgeSource,
    KnowledgeSourceItem,
    KnowledgeSyncRun,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20261001110000_knowledge_connectors.py"
)
MODELS = (KnowledgeSource, KnowledgeSourceItem, KnowledgeSyncRun)


def _load():
    spec = importlib.util.spec_from_file_location("knowledge_connectors", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def migrated(monkeypatch):
    migration = _load()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        yield migration, connection


def test_revision_chain_follows_the_current_head() -> None:
    migration = _load()
    assert migration.revision == "20261001110000"
    assert migration.down_revision == "20260927190000"


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__tablename__)
def test_migrated_tables_match_the_model_columns(migrated, model) -> None:
    _migration, connection = migrated
    inspector = sa.inspect(connection)
    migrated_columns = {column["name"] for column in inspector.get_columns(model.__tablename__)}
    assert migrated_columns == {column.name for column in model.__table__.columns}


@pytest.mark.parametrize("model", MODELS, ids=lambda model: model.__tablename__)
def test_migrated_tables_have_indexed_tenant_and_workspace(migrated, model) -> None:
    _migration, connection = migrated
    indexed = {
        column
        for index in sa.inspect(connection).get_indexes(model.__tablename__)
        for column in index["column_names"]
    }
    assert {"tenant_id", "workspace_id"} <= indexed


def test_migrated_indexes_match_the_model_indexes(migrated) -> None:
    _migration, connection = migrated
    inspector = sa.inspect(connection)
    for model in MODELS:
        migrated_indexes = {index["name"] for index in inspector.get_indexes(model.__tablename__)}
        model_indexes = {index.name for index in model.__table__.indexes}
        assert migrated_indexes == model_indexes, model.__tablename__


def test_active_run_index_allows_one_queued_or_running_run_per_source(migrated) -> None:
    _migration, connection = migrated
    runs = sa.Table(KnowledgeSyncRun.__tablename__, sa.MetaData(), autoload_with=connection)

    def insert(run_id: str, status: str) -> None:
        connection.execute(
            runs.insert().values(
                id=run_id,
                tenant_id="t",
                workspace_id="w",
                knowledge_id="k",
                source_id="s",
                status=status,
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )

    insert("r1", "succeeded")
    insert("r2", "failed")
    insert("r3", "running")
    with pytest.raises(sa.exc.IntegrityError):
        insert("r4", "queued")


def test_downgrade_removes_the_tables(migrated) -> None:
    migration, connection = migrated
    migration.downgrade()
    tables = set(sa.inspect(connection).get_table_names())
    assert not tables & {model.__tablename__ for model in MODELS}
