from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.assessment import Assessment
from app.models.group import Group
from app.models.reward import RewardCatalog
from app.services.assessment_service import AssessmentService
from app.services.auth_service import AuthService, AuthServiceError
from app.services.coin_service import CoinService, CoinServiceError
from app.services.group_service import GroupService, GroupServiceError
from app.services.settings_service import SettingsService, SettingsServiceError


def login(client, username: str, password: str):
    token = client.get("/login").cookies["csrf_token"]
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": token},
    )


def test_settings_service_defaults_fee_and_max_transfer(db_session: Session):
    settings = SettingsService(db_session)

    assert settings.transfer_policy() == {"fee_percent": 1.0, "max_percent": 70.0}
    assert settings.fee_for(123) == 1.23
    assert settings.max_transfer_amount(250) == 175.0


def test_settings_service_rejects_invalid_percent_values(db_session: Session, admin):
    settings = SettingsService(db_session)

    with pytest.raises(SettingsServiceError):
        settings.update_transfer_policy(admin, -1, 70)
    with pytest.raises(SettingsServiceError):
        settings.update_transfer_policy(admin, 1, 0)


def test_admin_settings_page_contains_transfer_and_password_forms(client, admin):
    login(client, "admin", "admin12345")

    response = client.get("/admin/settings")

    assert response.status_code == 200
    assert 'action="/admin/settings"' in response.text
    assert 'name="transfer_fee_percent"' in response.text
    assert 'name="transfer_max_percent"' in response.text
    assert 'action="/admin/settings/password"' in response.text
    assert 'name="current_password"' in response.text
    assert 'name="new_password"' in response.text


def test_admin_password_change_rejects_confirmation_mismatch(client, admin, db_session: Session):
    login(client, "admin", "admin12345")
    token = client.cookies["csrf_token"]

    response = client.post(
        "/admin/settings/password",
        data={
            "current_password": "admin12345",
            "new_password": "new-admin-pass",
            "confirm_password": "different-pass",
            "csrf_token": token,
        },
    )
    db_session.refresh(admin)

    assert response.status_code == 400
    assert "Пароли не совпадают" in response.text
    assert verify_password("admin12345", admin.password_hash)


def test_register_rejects_inactive_group(db_session: Session):
    group = GroupService(db_session).create_group("Closed", "closed", "CLOSED")
    group.is_active = False
    db_session.commit()

    with pytest.raises(AuthServiceError):
        AuthService(db_session).register_member("closed_user", "password123", "Closed User", group.id)


def test_duplicate_group_slug_is_reported(db_session: Session):
    service = GroupService(db_session)
    service.create_group("Design", "design", "DESIGN")

    with pytest.raises(GroupServiceError):
        service.create_group("Design Again", "design", "DESIGN2")


def test_peer_transfer_rejects_cross_group_transfer(db_session: Session, admin, members, other_group_member):
    first, _ = members
    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 200, "Старт", "cross-group-grant")

    with pytest.raises(CoinServiceError):
        service.peer_transfer(
            first,
            first.memberships[0],
            other_group_member.memberships[0],
            20,
            "Wrong group",
            "cross-group-transfer",
        )


def test_inactive_reward_cannot_be_bought(db_session: Session, admin, members):
    member, _ = members
    reward = RewardCatalog(code="inactive", title="Inactive", price=50, is_active=False)
    db_session.add(reward)
    db_session.commit()
    CoinService(db_session).admin_grant(admin, member.memberships[0], 100, "Старт", "inactive-reward-grant")

    with pytest.raises(CoinServiceError):
        CoinService(db_session).buy_reward(member, member.memberships[0], reward, "inactive-reward-buy")


def test_fulfilled_redemption_cannot_be_fulfilled_twice(db_session: Session, admin, members):
    member, _ = members
    reward = db_session.query(RewardCatalog).filter_by(code="credit").one()
    service = CoinService(db_session)
    service.admin_grant(admin, member.memberships[0], 150, "Старт", "double-fulfill-grant")
    redemption = service.buy_reward(member, member.memberships[0], reward, "double-fulfill-buy")
    service.fulfill_redemption(admin, redemption, "double-fulfill")

    with pytest.raises(CoinServiceError):
        service.fulfill_redemption(admin, redemption, "double-fulfill-again")


def test_inactive_assessment_cannot_be_paid(db_session: Session, admin, members):
    member, _ = members
    membership = member.memberships[0]
    assessment = AssessmentService(db_session).create_assessment(
        admin,
        "Past assessment",
        "Archive",
        None,
        50,
        "group",
        membership.group_id,
        None,
        None,
    )
    assessment.status = "past"
    db_session.commit()
    CoinService(db_session).admin_grant(admin, membership, 100, "Старт", "inactive-assessment-grant")

    with pytest.raises(CoinServiceError):
        CoinService(db_session).buy_assessment(member, membership, assessment, "inactive-assessment-pay")


def test_student_assessment_cannot_be_paid_by_another_student(db_session: Session, admin, members):
    first, second = members
    assessment = AssessmentService(db_session).create_assessment(
        admin,
        "Personal assessment",
        "Individual",
        None,
        60,
        "student",
        first.memberships[0].group_id,
        first.memberships[0].id,
        None,
    )
    CoinService(db_session).admin_grant(admin, second.memberships[0], 100, "Старт", "wrong-student-grant")

    with pytest.raises(CoinServiceError):
        CoinService(db_session).buy_assessment(second, second.memberships[0], assessment, "wrong-student-pay")


def test_member_transfer_route_returns_plain_error_for_invalid_amount(client, db_session: Session, admin, members):
    first, second = members
    CoinService(db_session).admin_grant(
        admin,
        first.memberships[0],
        100,
        "Старт",
        "route-invalid-transfer-grant",
    )
    login(client, "alice", "password123")
    token = client.cookies["csrf_token"]

    response = client.post(
        "/coins/transfer",
        data={
            "to_membership_id": str(second.memberships[0].id),
            "amount": "0",
            "reason": "Invalid",
            "idempotency_key": "route-invalid-transfer",
            "csrf_token": token,
        },
    )

    assert response.status_code == 400
    assert "Сумма должна быть больше нуля" in response.text


def test_windows_launch_scripts_match_readme_contract():
    start_script = Path("start.bat").read_text(encoding="utf-8")
    app_script = Path("app.bat").read_text(encoding="utf-8")
    reset_script = Path("reset_data.bat").read_text(encoding="utf-8")

    assert "first setup" in start_script
    assert "Create demo data? Default is Y" in start_script
    assert "--has-admin" in start_script
    assert "app launcher" in app_script
    assert "Please run start.bat first" in app_script
    assert "Type DELETE to confirm" in reset_script
    assert "data\\neurocoin.db" in reset_script


def test_submission_documents_are_present():
    expected = [
        "README.md",
        "AUTHORS.md",
        "docs/checklist.md",
        "docs/test-cases.md",
        "docs/bug-reports.md",
        "docs/testing-report.md",
    ]

    for path in expected:
        assert Path(path).exists(), path


def test_project_mark_script_is_loaded_on_public_and_private_pages(client, admin, members):
    for path in ("/", "/login", "/register"):
        response = client.get(path)
        assert response.status_code == 200
        assert "/static/js/credits.js" in response.text

    login(client, "admin", "admin12345")
    admin_response = client.get("/admin")
    assert admin_response.status_code == 200
    assert "/static/js/credits.js" in admin_response.text

    client.post("/logout", data={"csrf_token": client.cookies["csrf_token"]})
    login(client, "alice", "password123")
    member_response = client.get("/me")
    assert member_response.status_code == 200
    assert "/static/js/credits.js" in member_response.text


def test_project_mark_script_contains_authors_without_public_brand_reference():
    script = Path("app/static/js/credits.js").read_text(encoding="utf-8")

    assert "Карелин Михаил" in script
    assert "Бусарев Дмитрий" in script
    assert "Абдуллоев Умеджон" in script
    assert "Проект выполнен" in script
    assert "CLICK_THRESHOLD = 5" in script
    forbidden_brand = "re" + "made"
    assert forbidden_brand not in script.lower()
    assert "credits" not in script.lower()
