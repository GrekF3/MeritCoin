from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.reward import RewardCatalog, RewardRedemption


class RewardService:
    def __init__(self, db: Session):
        self.db = db

    def active_rewards(self) -> list[RewardCatalog]:
        return self.db.query(RewardCatalog).filter_by(is_active=True).order_by(RewardCatalog.price).all()

    def pending_redemptions(self) -> list[RewardRedemption]:
        return (
            self.db.query(RewardRedemption)
            .filter_by(status="pending")
            .order_by(RewardRedemption.created_at.desc())
            .all()
        )
