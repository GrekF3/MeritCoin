from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_assessments_crm"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("admin_note", sa.Text(), nullable=True))
    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("topic", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("student_membership_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["student_membership_id"], ["memberships.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assessments_created_at"), "assessments", ["created_at"], unique=False)
    op.create_index(op.f("ix_assessments_created_by_user_id"), "assessments", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_assessments_group_id"), "assessments", ["group_id"], unique=False)
    op.create_index(op.f("ix_assessments_scope"), "assessments", ["scope"], unique=False)
    op.create_index(op.f("ix_assessments_status"), "assessments", ["status"], unique=False)
    op.create_index(op.f("ix_assessments_student_membership_id"), "assessments", ["student_membership_id"], unique=False)
    op.create_table(
        "assessment_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"]),
        sa.ForeignKeyConstraint(["transaction_id"], ["coin_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "membership_id", name="uq_assessment_payment_member"),
    )
    op.create_index(op.f("ix_assessment_payments_assessment_id"), "assessment_payments", ["assessment_id"], unique=False)
    op.create_index(op.f("ix_assessment_payments_created_at"), "assessment_payments", ["created_at"], unique=False)
    op.create_index(op.f("ix_assessment_payments_membership_id"), "assessment_payments", ["membership_id"], unique=False)
    op.create_index(op.f("ix_assessment_payments_status"), "assessment_payments", ["status"], unique=False)
    op.create_index(op.f("ix_assessment_payments_transaction_id"), "assessment_payments", ["transaction_id"], unique=False)


def downgrade() -> None:
    op.drop_table("assessment_payments")
    op.drop_table("assessments")
    op.drop_column("memberships", "admin_note")
