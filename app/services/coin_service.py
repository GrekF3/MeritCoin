from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.coin import CoinAccount, CoinTransaction, LedgerEntry, TransactionType
from app.models.assessment import Assessment, AssessmentPayment
from app.models.group import Group
from app.models.membership import Membership
from app.models.reward import RewardCatalog, RewardRedemption
from app.models.user import User, UserRole
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.settings_service import SettingsService
from app.utils.money import money, money_float


class CoinServiceError(ValueError):
    pass


class CoinService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def _existing_transaction(self, idempotency_key: str | None) -> CoinTransaction | None:
        if not idempotency_key:
            return None
        return self.db.query(CoinTransaction).filter_by(idempotency_key=idempotency_key).one_or_none()

    def _validate_amount_reason(self, amount: float, reason: str | None) -> float:
        amount = money_float(amount)
        if amount <= 0:
            raise CoinServiceError("Сумма должна быть больше нуля")
        if not reason or not reason.strip():
            raise CoinServiceError("Укажите причину операции")
        return amount

    def _account_for_membership(self, membership: Membership) -> CoinAccount:
        account = membership.account
        if account is None:
            account = CoinAccount(membership_id=membership.id, balance_cached=0)
            self.db.add(account)
            self.db.flush()
        return account

    def _system_account_for_group(self, group: Group) -> CoinAccount:
        username = f"__system__{group.id}"
        user = self.db.query(User).filter_by(username=username).one_or_none()
        if user is None:
            user = AuthService(self.db).create_user(
                username=username,
                password="system-account-not-for-login",
                display_name=f"System {group.name}",
                role=UserRole.ADMIN,
            )
        membership = (
            self.db.query(Membership)
            .filter_by(user_id=user.id, group_id=group.id)
            .one_or_none()
        )
        if membership is None:
            membership = Membership(user_id=user.id, group_id=group.id, status="active")
            account = CoinAccount(membership=membership, balance_cached=0)
            self.db.add_all([membership, account])
            self.db.flush()
        return self._account_for_membership(membership)

    def _apply_entry(self, tx: CoinTransaction, account: CoinAccount, delta: float) -> None:
        delta = money_float(delta)
        new_balance = money_float(account.balance_cached + delta)
        if new_balance < 0:
            raise CoinServiceError("Недостаточно коинов")
        account.balance_cached = new_balance
        self.db.add(
            LedgerEntry(
                transaction=tx,
                account=account,
                delta=delta,
                balance_after=new_balance,
            )
        )

    def admin_grant(
        self,
        admin: User,
        membership: Membership,
        amount: float,
        reason: str,
        idempotency_key: str | None,
    ) -> CoinTransaction:
        existing = self._existing_transaction(idempotency_key)
        if existing:
            return existing
        amount = self._validate_amount_reason(amount, reason)
        account = self._account_for_membership(membership)
        tx = CoinTransaction(
            type=TransactionType.ADMIN_GRANT,
            initiator_user_id=admin.id,
            group_id=membership.group_id,
            to_account_id=account.id,
            amount=amount,
            fee=0,
            reason=reason.strip(),
            idempotency_key=idempotency_key,
        )
        self.db.add(tx)
        self.db.flush()
        self._apply_entry(tx, account, amount)
        self.audit.log(admin, "coin.admin_grant", "coin_transaction", tx.id, {"amount": amount})
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def admin_revoke(
        self,
        admin: User,
        membership: Membership,
        amount: float,
        reason: str,
        idempotency_key: str | None,
    ) -> CoinTransaction:
        existing = self._existing_transaction(idempotency_key)
        if existing:
            return existing
        amount = self._validate_amount_reason(amount, reason)
        account = self._account_for_membership(membership)
        if account.balance_cached < amount:
            raise CoinServiceError("Нельзя списать больше баланса")
        tx = CoinTransaction(
            type=TransactionType.ADMIN_REVOKE,
            initiator_user_id=admin.id,
            group_id=membership.group_id,
            from_account_id=account.id,
            amount=amount,
            fee=0,
            reason=reason.strip(),
            idempotency_key=idempotency_key,
        )
        self.db.add(tx)
        self.db.flush()
        self._apply_entry(tx, account, -amount)
        self.audit.log(admin, "coin.admin_revoke", "coin_transaction", tx.id, {"amount": amount})
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def peer_transfer(
        self,
        actor: User,
        from_membership: Membership,
        to_membership: Membership,
        amount: float,
        reason: str | None,
        idempotency_key: str | None,
    ) -> CoinTransaction:
        existing = self._existing_transaction(idempotency_key)
        if existing:
            return existing
        amount = money_float(amount)
        if amount <= 0:
            raise CoinServiceError("Сумма должна быть больше нуля")
        if from_membership.id == to_membership.id:
            raise CoinServiceError("Нельзя переводить самому себе")
        if from_membership.group_id != to_membership.group_id:
            raise CoinServiceError("Перевод доступен только внутри группы")
        from_account = self._account_for_membership(from_membership)
        to_account = self._account_for_membership(to_membership)
        settings = SettingsService(self.db)
        fee = settings.fee_for(amount)
        received_amount = money_float(amount - fee)
        if received_amount < 0:
            raise CoinServiceError("Комиссия не может быть больше суммы перевода")
        max_percent = settings.transfer_max_percent()
        max_debit = money_float(money(from_account.balance_cached) * max_percent / 100)
        if amount > max_debit:
            raise CoinServiceError(f"Превышен лимит перевода {max_percent:.2f}% баланса")
        system_account = self._system_account_for_group(from_membership.group)
        tx = CoinTransaction(
            type=TransactionType.PEER_TRANSFER,
            initiator_user_id=actor.id,
            group_id=from_membership.group_id,
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            amount=amount,
            fee=fee,
            reason=reason.strip() if reason else None,
            idempotency_key=idempotency_key,
        )
        self.db.add(tx)
        self.db.flush()
        self._apply_entry(tx, from_account, -amount)
        self._apply_entry(tx, to_account, received_amount)
        self._apply_entry(tx, system_account, fee)
        self.audit.log(
            actor,
            "coin.peer_transfer",
            "coin_transaction",
            tx.id,
            {"amount": amount, "fee": fee, "received_amount": received_amount},
        )
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def buy_reward(
        self,
        actor: User,
        membership: Membership,
        reward: RewardCatalog,
        idempotency_key: str | None,
    ) -> RewardRedemption:
        existing = self._existing_transaction(idempotency_key)
        if existing:
            redemption = self.db.query(RewardRedemption).filter_by(transaction_id=existing.id).one_or_none()
            if redemption:
                return redemption
        if not reward.is_active:
            raise CoinServiceError("Награда недоступна")
        account = self._account_for_membership(membership)
        if account.balance_cached < reward.price:
            raise CoinServiceError("Недостаточно коинов")
        tx = CoinTransaction(
            type=TransactionType.REWARD_REDEMPTION,
            initiator_user_id=actor.id,
            group_id=membership.group_id,
            from_account_id=account.id,
            amount=reward.price,
            fee=0,
            reason=f"Покупка: {reward.title}",
            idempotency_key=idempotency_key,
        )
        self.db.add(tx)
        self.db.flush()
        self._apply_entry(tx, account, -reward.price)
        redemption = RewardRedemption(
            reward_id=reward.id,
            membership_id=membership.id,
            transaction_id=tx.id,
            status="pending",
        )
        self.db.add(redemption)
        self.audit.log(actor, "reward.buy", "reward_redemption", None, {"reward_id": reward.id})
        self.db.commit()
        self.db.refresh(redemption)
        return redemption

    def buy_assessment(
        self,
        actor: User,
        membership: Membership,
        assessment: Assessment,
        idempotency_key: str | None,
    ) -> AssessmentPayment:
        existing = self._existing_transaction(idempotency_key)
        if existing:
            payment = self.db.query(AssessmentPayment).filter_by(transaction_id=existing.id).one_or_none()
            if payment:
                return payment
        if assessment.status != "active":
            raise CoinServiceError("Зачет недоступен")
        if assessment.scope == "group":
            allowed = assessment.group_id == membership.group_id
        else:
            allowed = assessment.student_membership_id == membership.id
        if not allowed:
            raise CoinServiceError("Зачет не назначен этому студенту")
        paid = (
            self.db.query(AssessmentPayment)
            .filter_by(assessment_id=assessment.id, membership_id=membership.id, status="paid")
            .one_or_none()
        )
        if paid:
            raise CoinServiceError("Зачет уже оплачен")
        account = self._account_for_membership(membership)
        if account.balance_cached < assessment.cost:
            raise CoinServiceError("Недостаточно коинов")
        tx = CoinTransaction(
            type=TransactionType.REWARD_REDEMPTION,
            initiator_user_id=actor.id,
            group_id=membership.group_id,
            from_account_id=account.id,
            amount=assessment.cost,
            fee=0,
            reason=f"Оплата зачета: {assessment.title}",
            idempotency_key=idempotency_key,
        )
        self.db.add(tx)
        self.db.flush()
        self._apply_entry(tx, account, -assessment.cost)
        payment = AssessmentPayment(
            assessment_id=assessment.id,
            membership_id=membership.id,
            transaction_id=tx.id,
            status="paid",
        )
        self.db.add(payment)
        self.audit.log(actor, "assessment.pay", "assessment", assessment.id, {"cost": assessment.cost})
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def fulfill_redemption(
        self,
        admin: User,
        redemption: RewardRedemption,
        idempotency_key: str | None = None,
    ) -> RewardRedemption:
        if redemption.status != "pending":
            raise CoinServiceError("Заявка уже обработана")
        redemption.status = "fulfilled"
        redemption.fulfilled_at = datetime.utcnow()
        self.audit.log(admin, "reward.fulfill", "reward_redemption", redemption.id, {})
        self.db.commit()
        self.db.refresh(redemption)
        return redemption
