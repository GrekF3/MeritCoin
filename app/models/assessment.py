from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.coin import CoinTransaction
from app.models.group import Group
from app.models.membership import Membership
from app.models.user import User


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    topic: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[float] = mapped_column(Float)
    scope: Mapped[str] = mapped_column(String(20), default="group", index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    student_membership_id: Mapped[int | None] = mapped_column(ForeignKey("memberships.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship(Group)
    student_membership = relationship(Membership, foreign_keys=[student_membership_id])
    created_by = relationship(User)
    payments = relationship("AssessmentPayment", back_populates="assessment")


class AssessmentPayment(Base):
    __tablename__ = "assessment_payments"
    __table_args__ = (UniqueConstraint("assessment_id", "membership_id", name="uq_assessment_payment_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("coin_transactions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="paid", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    assessment = relationship("Assessment", back_populates="payments")
    membership = relationship(Membership)
    transaction = relationship(CoinTransaction)
