from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0003_float_money_and_transfer_settings"
down_revision = "0002_assessments_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("coin_accounts") as batch:
        batch.alter_column("balance_cached", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("coin_transactions") as batch:
        batch.alter_column("amount", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
        batch.alter_column("fee", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("ledger_entries") as batch:
        batch.alter_column("delta", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
        batch.alter_column("balance_after", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("reward_catalog") as batch:
        batch.alter_column("price", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("assessments") as batch:
        batch.alter_column("cost", existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)

    settings = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("updated_at", sa.DateTime),
    )
    connection = op.get_bind()
    for key, value in (
        ("transfer_fee_percent", "1.00"),
        ("transfer_max_percent", "70.00"),
    ):
        exists = connection.execute(sa.select(settings.c.key).where(settings.c.key == key)).first()
        if exists is None:
            connection.execute(settings.insert().values(key=key, value=value, updated_at=datetime.utcnow()))


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key IN ('transfer_fee_percent', 'transfer_max_percent')")
    with op.batch_alter_table("assessments") as batch:
        batch.alter_column("cost", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
    with op.batch_alter_table("reward_catalog") as batch:
        batch.alter_column("price", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
    with op.batch_alter_table("ledger_entries") as batch:
        batch.alter_column("balance_after", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
        batch.alter_column("delta", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
    with op.batch_alter_table("coin_transactions") as batch:
        batch.alter_column("fee", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
        batch.alter_column("amount", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
    with op.batch_alter_table("coin_accounts") as batch:
        batch.alter_column("balance_cached", existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)
