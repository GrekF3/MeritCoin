from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class TransactionType(str, enum.Enum):
    ADMIN_GRANT = "ADMIN_GRANT"
    ADMIN_REVOKE = "ADMIN_REVOKE"
    PEER_TRANSFER = "PEER_TRANSFER"
    REWARD_REDEMPTION = "REWARD_REDEMPTION"
    REFUND = "REFUND"


class CoinAccount(Base):
    __tablename__ = "coin_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id"), unique=True, index=True)
    balance_cached: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    membership = relationship("Membership", back_populates="account")
    ledger_entries = relationship("LedgerEntry", back_populates="account")


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), index=True)
    initiator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    from_account_id: Mapped[int | None] = mapped_column(ForeignKey("coin_accounts.id"), nullable=True)
    to_account_id: Mapped[int | None] = mapped_column(ForeignKey("coin_accounts.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    initiator = relationship("User")
    group = relationship("Group")
    from_account = relationship("CoinAccount", foreign_keys=[from_account_id])
    to_account = relationship("CoinAccount", foreign_keys=[to_account_id])
    ledger_entries = relationship("LedgerEntry", back_populates="transaction", cascade="all, delete-orphan")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("coin_transactions.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("coin_accounts.id"), index=True)
    delta: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    transaction = relationship("CoinTransaction", back_populates="ledger_entries")
    account = relationship("CoinAccount", back_populates="ledger_entries")
