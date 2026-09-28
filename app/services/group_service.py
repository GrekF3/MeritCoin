from __future__ import annotations

import re

from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.assessment import Assessment, AssessmentPayment
from app.models.coin import CoinAccount, CoinTransaction, LedgerEntry
from app.models.group import Group
from app.models.membership import Membership
from app.models.reward import RewardRedemption
from app.models.user import User, UserRole


class GroupServiceError(ValueError):
    pass


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9а-яё]+", "-", value)
    return value.strip("-") or "group"


class GroupService:
    def __init__(self, db: Session):
        self.db = db

    def create_group(self, name: str, slug: str | None = None, invite_code: str | None = None) -> Group:
        group = Group(
            name=name.strip(),
            slug=slugify(slug or name),
            invite_code=invite_code.strip() if invite_code else None,
            is_active=True,
        )
        self.db.add(group)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise GroupServiceError("Группа с таким slug или кодом уже существует") from exc
        self.db.refresh(group)
        return group

    def active_groups(self) -> list[Group]:
        return self.db.query(Group).filter_by(is_active=True).order_by(Group.name).all()

    def get_group_with_members(self, group_id: int) -> Group | None:
        return (
            self.db.query(Group)
            .options(selectinload(Group.memberships).selectinload(Membership.user), selectinload(Group.memberships).selectinload(Membership.account))
            .filter(Group.id == group_id)
            .one_or_none()
        )

    def list_groups_with_stats(self) -> list[dict[str, object]]:
        real_member = (
            (User.role == UserRole.MEMBER)
            & (User.is_active.is_(True))
            & (Membership.status == "active")
            & (~User.username.like("__system__%"))
        )
        rows = (
            self.db.query(
                Group,
                func.coalesce(func.sum(case((real_member, 1), else_=0)), 0).label("participants_count"),
                func.coalesce(
                    func.sum(case((real_member, func.coalesce(CoinAccount.balance_cached, 0)), else_=0)),
                    0,
                ).label("total_coins"),
            )
            .outerjoin(Membership, Membership.group_id == Group.id)
            .outerjoin(User, User.id == Membership.user_id)
            .outerjoin(CoinAccount, CoinAccount.membership_id == Membership.id)
            .group_by(Group.id)
            .order_by(Group.name)
            .all()
        )
        return [
            {
                "group": group,
                "participants_count": participants_count,
                "total_coins": total_coins,
            }
            for group, participants_count, total_coins in rows
        ]

    def delete_group(self, group_id: int) -> str:
        group = self.db.get(Group, group_id)
        if group is None:
            raise GroupServiceError("Группа не найдена")

        group_name = group.name
        users_to_archive = (
            self.db.query(User)
            .join(Membership, Membership.user_id == User.id)
            .filter(
                Membership.group_id == group_id,
                User.role == UserRole.MEMBER,
                ~User.username.like("__system__%"),
            )
            .all()
        )
        membership_ids = [row[0] for row in self.db.query(Membership.id).filter(Membership.group_id == group_id).all()]
        account_ids = []
        if membership_ids:
            account_ids = [
                row[0]
                for row in self.db.query(CoinAccount.id)
                .filter(CoinAccount.membership_id.in_(membership_ids))
                .all()
            ]
        assessment_ids = [row[0] for row in self.db.query(Assessment.id).filter(Assessment.group_id == group_id).all()]

        transaction_query = self.db.query(CoinTransaction.id).filter(CoinTransaction.group_id == group_id)
        if account_ids:
            transaction_query = transaction_query.union(
                self.db.query(CoinTransaction.id).filter(
                    (CoinTransaction.from_account_id.in_(account_ids)) | (CoinTransaction.to_account_id.in_(account_ids))
                )
            )
        transaction_ids = [row[0] for row in transaction_query.all()]

        try:
            if assessment_ids or membership_ids or transaction_ids:
                payment_query = self.db.query(AssessmentPayment)
                payment_filters = []
                if assessment_ids:
                    payment_filters.append(AssessmentPayment.assessment_id.in_(assessment_ids))
                if membership_ids:
                    payment_filters.append(AssessmentPayment.membership_id.in_(membership_ids))
                if transaction_ids:
                    payment_filters.append(AssessmentPayment.transaction_id.in_(transaction_ids))
                if payment_filters:
                    payment_query.filter(or_(*payment_filters)).delete(synchronize_session=False)

            if membership_ids or transaction_ids:
                redemption_query = self.db.query(RewardRedemption)
                redemption_filters = []
                if membership_ids:
                    redemption_filters.append(RewardRedemption.membership_id.in_(membership_ids))
                if transaction_ids:
                    redemption_filters.append(RewardRedemption.transaction_id.in_(transaction_ids))
                if redemption_filters:
                    redemption_query.filter(or_(*redemption_filters)).delete(synchronize_session=False)

            if transaction_ids:
                self.db.query(LedgerEntry).filter(LedgerEntry.transaction_id.in_(transaction_ids)).delete(synchronize_session=False)
            if account_ids:
                self.db.query(LedgerEntry).filter(LedgerEntry.account_id.in_(account_ids)).delete(synchronize_session=False)
            if assessment_ids:
                self.db.query(Assessment).filter(Assessment.id.in_(assessment_ids)).delete(synchronize_session=False)
            if transaction_ids:
                self.db.query(CoinTransaction).filter(CoinTransaction.id.in_(transaction_ids)).delete(synchronize_session=False)
            if account_ids:
                self.db.query(CoinAccount).filter(CoinAccount.id.in_(account_ids)).delete(synchronize_session=False)
            if membership_ids:
                self.db.query(Membership).filter(Membership.id.in_(membership_ids)).delete(synchronize_session=False)
            for user in users_to_archive:
                remaining_memberships = self.db.query(Membership.id).filter(Membership.user_id == user.id).count()
                if remaining_memberships == 0 and user.role == UserRole.MEMBER and not user.username.startswith("__system__"):
                    old_username = user.username
                    prefix = f"deleted_{user.id}_"
                    user.username = f"{prefix}{old_username}"[:80]
                    user.is_active = False
            self.db.delete(group)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise GroupServiceError("Не удалось удалить группу из-за связанных данных") from exc

        return group_name
