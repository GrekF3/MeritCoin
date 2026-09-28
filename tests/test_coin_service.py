import pytest
from sqlalchemy.orm import Session

from app.models.coin import CoinAccount, CoinTransaction
from app.models.reward import RewardCatalog, RewardRedemption
from app.services.coin_service import CoinService, CoinServiceError
from app.services.settings_service import SettingsService


def account_for(db: Session, user_id: int) -> CoinAccount:
    return (
        db.query(CoinAccount)
        .join(CoinAccount.membership)
        .filter_by(user_id=user_id)
        .one()
    )


def test_admin_grant_increases_balance(db_session: Session, admin, members):
    member, _ = members
    service = CoinService(db_session)
    tx = service.admin_grant(admin, member.memberships[0], 150, "Победа", "grant-1")

    assert tx.amount == 150
    assert account_for(db_session, member.id).balance_cached == 150


def test_admin_revoke_decreases_balance(db_session: Session, admin, members):
    member, _ = members
    service = CoinService(db_session)
    service.admin_grant(admin, member.memberships[0], 150, "Победа", "grant-1")
    service.admin_revoke(admin, member.memberships[0], 40, "Штраф", "revoke-1")

    assert account_for(db_session, member.id).balance_cached == 110


def test_admin_revoke_cannot_overdraw(db_session: Session, admin, members):
    member, _ = members

    with pytest.raises(CoinServiceError):
        CoinService(db_session).admin_revoke(admin, member.memberships[0], 1, "Штраф", "revoke-1")


def test_peer_transfer_moves_amount_and_fee(db_session: Session, admin, members):
    first, second = members
    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 1000, "Старт", "grant-1")
    tx = service.peer_transfer(first, first.memberships[0], second.memberships[0], 100, "Спасибо", "peer-1")

    assert tx.fee == 1
    assert account_for(db_session, first.id).balance_cached == 900
    assert account_for(db_session, second.id).balance_cached == 99


def test_peer_transfer_forbids_more_than_70_percent(db_session: Session, admin, members):
    first, second = members
    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 100, "Старт", "grant-1")

    with pytest.raises(CoinServiceError):
        service.peer_transfer(first, first.memberships[0], second.memberships[0], 70.01, "Слишком много", "peer-1")


def test_peer_transfer_uses_admin_percent_settings(db_session: Session, admin, members):
    first, second = members
    SettingsService(db_session).update_transfer_policy(admin, 2.5, 50)
    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 1000, "Старт", "grant-1")
    tx = service.peer_transfer(first, first.memberships[0], second.memberships[0], 100, "Спасибо", "peer-1")

    assert tx.fee == 2.5
    assert account_for(db_session, first.id).balance_cached == 900
    assert account_for(db_session, second.id).balance_cached == 97.5
    with pytest.raises(CoinServiceError):
        service.peer_transfer(first, first.memberships[0], second.memberships[0], 500, "Слишком много", "peer-2")


def test_peer_transfer_shows_fee_inside_sent_amount(db_session: Session, admin, members):
    first, second = members
    SettingsService(db_session).update_transfer_policy(admin, 99.99, 100)
    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 200, "Старт", "grant-1")

    tx = service.peer_transfer(first, first.memberships[0], second.memberships[0], 123, "Проверка комиссии", "peer-1")

    assert tx.amount == 123
    assert tx.fee == 122.99
    assert account_for(db_session, first.id).balance_cached == 77
    assert account_for(db_session, second.id).balance_cached == 0.01


def test_peer_transfer_forbids_self_transfer(db_session: Session, admin, members):
    first, _ = members
    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 100, "Старт", "grant-1")

    with pytest.raises(CoinServiceError):
        service.peer_transfer(first, first.memberships[0], first.memberships[0], 10, "Самому себе", "peer-1")


def test_reward_redemption_spends_100(db_session: Session, admin, members):
    member, _ = members
    reward = db_session.query(RewardCatalog).filter_by(code="credit").one()
    service = CoinService(db_session)
    service.admin_grant(admin, member.memberships[0], 150, "Старт", "grant-1")
    redemption = service.buy_reward(member, member.memberships[0], reward, "reward-1")

    assert redemption.status == "pending"
    assert account_for(db_session, member.id).balance_cached == 50


def test_reward_redemption_requires_balance(db_session: Session, members):
    member, _ = members
    reward = db_session.query(RewardCatalog).filter_by(code="credit").one()

    with pytest.raises(CoinServiceError):
        CoinService(db_session).buy_reward(member, member.memberships[0], reward, "reward-1")


def test_idempotency_does_not_duplicate(db_session: Session, admin, members):
    member, _ = members
    service = CoinService(db_session)
    first = service.admin_grant(admin, member.memberships[0], 50, "Старт", "same-key")
    second = service.admin_grant(admin, member.memberships[0], 50, "Старт", "same-key")

    assert first.id == second.id
    assert account_for(db_session, member.id).balance_cached == 50
    assert db_session.query(CoinTransaction).filter_by(idempotency_key="same-key").count() == 1


def test_fulfill_redemption(db_session: Session, admin, members):
    member, _ = members
    reward = db_session.query(RewardCatalog).filter_by(code="credit").one()
    service = CoinService(db_session)
    service.admin_grant(admin, member.memberships[0], 100, "Старт", "grant-1")
    redemption = service.buy_reward(member, member.memberships[0], reward, "reward-1")
    fulfilled = service.fulfill_redemption(admin, redemption, "fulfill-1")

    assert fulfilled.status == "fulfilled"
    assert fulfilled.fulfilled_at is not None
