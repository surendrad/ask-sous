"""add_upsell_flag_and_campaign_attribution

Revision ID: 4faf13ae1462
Revises: 61f16e68e2d7
Create Date: 2026-07-16 09:50:17.009176

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4faf13ae1462"
down_revision: str | Sequence[str] | None = "61f16e68e2d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "menu_items",
        sa.Column("is_upsell", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("transactions", sa.Column("campaign_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_transactions_campaign_id"), "transactions", ["campaign_id"], unique=False
    )
    op.create_foreign_key(
        "fk_transactions_campaign_id_campaigns",
        "transactions",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_transactions_campaign_id_campaigns", "transactions", type_="foreignkey"
    )
    op.drop_index(op.f("ix_transactions_campaign_id"), table_name="transactions")
    op.drop_column("transactions", "campaign_id")
    op.drop_column("menu_items", "is_upsell")
