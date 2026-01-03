"""test_model_scope_audit

Ensure all SQLModel tables (except identity) are tenant/workspace scoped.
"""

from scripts.audit_scope_models import audit


def test_all_tables_are_scoped() -> None:
    issues = audit()
    assert issues == [], f"Missing scope fields: {issues}"
