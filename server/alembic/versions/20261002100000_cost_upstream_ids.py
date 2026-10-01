"""Provider ids on cost entries: the provider's response id and request id.

``run_cost_entries.upstream_id`` keeps the id the provider gave its response
(``chatcmpl-…``, ``msg_…``, Gemini's ``responseId``) and
``upstream_request_id`` the request id from its response headers
(``x-request-id``, ``request-id``), so a cost entry can be found from a
provider's request log. Both are nullable and not unique: self-hosted
OpenAI-compatible servers and caching proxies repeat ids, and ``source_ref``
keeps its unique index for SOIT's own idempotency keys. Existing rows keep
NULL; nothing is backfilled.

Revision ID: 20261002100000
Revises: 20261001110000
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002100000"
down_revision: str | Sequence[str] | None = "20261001110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "run_cost_entries"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("upstream_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("upstream_request_id", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column("upstream_request_id")
        batch.drop_column("upstream_id")
