"""Tests for the database unit-of-work boundary."""

import pytest

from app.infra.db import session as session_module
from app.infra.db import transaction as transaction_module
from app.modules.identity.domain.models import Tenant


def test_transaction_module_exposes_sqlalchemy_unit_of_work() -> None:
    assert hasattr(transaction_module, "SQLAlchemyUnitOfWork")


def test_unit_of_work_commits_successful_transaction(db) -> None:
    tenant = Tenant(id="tenant-uow", name="Unit of Work")

    with transaction_module.SQLAlchemyUnitOfWork(db):
        db.add(tenant)

    db.expire_all()
    assert db.get(Tenant, tenant.id) is not None


def test_unit_of_work_rolls_back_failed_transaction(db) -> None:
    tenant = Tenant(id="tenant-uow-rollback", name="Rollback")

    with pytest.raises(RuntimeError, match="abort"):
        with transaction_module.SQLAlchemyUnitOfWork(db):
            db.add(tenant)
            db.flush()
            raise RuntimeError("abort")

    assert db.get(Tenant, tenant.id) is None


def test_request_session_commits_at_dependency_boundary(monkeypatch) -> None:
    class _Session:
        commits = 0
        rollbacks = 0
        closes = 0

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

        def close(self) -> None:
            self.closes += 1

    db = _Session()
    monkeypatch.setattr(session_module, "get_session_local", lambda: lambda: db)
    dependency = session_module.get_db()

    assert next(dependency) is db
    with pytest.raises(StopIteration):
        next(dependency)

    assert db.commits == 1
    assert db.rollbacks == 0
    assert db.closes == 1


def test_request_session_rolls_back_dependency_failure(monkeypatch) -> None:
    class _Session:
        commits = 0
        rollbacks = 0
        closes = 0

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

        def close(self) -> None:
            self.closes += 1

    db = _Session()
    monkeypatch.setattr(session_module, "get_session_local", lambda: lambda: db)
    dependency = session_module.get_db()
    next(dependency)

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert db.commits == 0
    assert db.rollbacks == 1
    assert db.closes == 1
