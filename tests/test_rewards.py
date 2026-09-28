from sqlalchemy.orm import Session

from app.models.reward import RewardCatalog
from app.services.coin_service import CoinService


def test_admin_redemptions_page_lists_pending(client, db_session: Session, admin, members):
    member, _ = members
    reward = db_session.query(RewardCatalog).filter_by(code="credit").one()
    service = CoinService(db_session)
    service.admin_grant(admin, member.memberships[0], 100, "Старт", "grant-1")
    service.buy_reward(member, member.memberships[0], reward, "reward-1")

    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )
    response = client.get("/admin/redemptions")

    assert response.status_code == 200
    assert "Alice" in response.text
    assert "pending" in response.text
