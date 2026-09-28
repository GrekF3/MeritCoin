from sqlalchemy.orm import Session
from pathlib import Path

from app.core.security import verify_password
from app.models.audit import AppSetting
from app.models.group import Group
from app.db.init_db import seed
from app.models.assessment import Assessment, AssessmentPayment
from app.models.coin import CoinTransaction
from app.models.membership import Membership
from app.models.reward import RewardCatalog, RewardRedemption
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.coin_service import CoinService
from app.services.group_service import GroupService


def test_member_sees_only_own_dashboard(client, admin, members, other_group_member):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "alice", "password": "password123", "csrf_token": token},
    )

    response = client.get("/me")

    assert response.status_code == 200
    assert "Alice" in response.text
    assert "Charlie" not in response.text


def test_member_dashboard_uses_mobile_bank_style(client, members):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "alice", "password": "password123", "csrf_token": token},
    )

    response = client.get("/me")

    assert response.status_code == 200
    assert "/static/css/member.css" in response.text
    assert "/static/js/member.js" in response.text
    assert "student-neural-canvas" in response.text
    assert "/static/css/easter.css" in response.text
    assert "/static/js/easter.js" in response.text
    assert "student-bank-card" in response.text
    assert "Привет, Alice" in response.text
    assert "Баланс" in response.text
    assert "История транзакций" in response.text
    assert "Загрузить еще" in response.text
    assert 'data-tab="home"' in response.text
    assert 'data-tooltip="Главная"' in response.text
    assert 'data-lucide="coins"' in response.text
    assert 'data-tab="send"' in response.text
    assert 'data-tooltip="Отправить"' in response.text
    assert "peer-combobox" in response.text
    assert 'name="to_membership_id"' in response.text
    assert 'class="peer-search"' in response.text
    assert 'aria-label="Итог перевода"' in response.text
    assert 'data-value="' in response.text
    assert "Bob" in response.text
    assert 'data-tab="credits"' in response.text
    assert 'data-tooltip="Зачеты"' in response.text
    assert 'data-tab="settings"' in response.text
    assert 'data-tooltip="Настройки"' in response.text
    assert "Отправить" in response.text
    assert "Зачеты" in response.text
    assert "Настройки" in response.text
    assert "Student wallet" not in response.text
    assert "contactless" not in response.text
    assert "coin-stack" not in response.text
    assert "История появится после начислений" not in response.text
    assert "Activity" not in response.text
    assert "Transfer" not in response.text
    assert "Credits" not in response.text
    assert "Completed" not in response.text
    assert "Profile" not in response.text
    assert 'action="/logout"' in response.text
    assert response.text.index('<nav class="mobile-app-menu"') < response.text.index("</main>")
    assert "/static/css/app.css" not in response.text
    assert "Charlie" not in response.text


def test_member_dashboard_reward_states_and_history_batches(client, db_session: Session, admin, members):
    member, _ = members
    membership = member.memberships[0]
    service = CoinService(db_session)

    for index in range(12):
        service.admin_grant(admin, membership, 10, f"История {index}", f"history-{index}")
    assessment = Assessment(
        title="Зачет по продукту",
        topic="CRM",
        description="Демо зачет",
        cost=100,
        scope="group",
        group_id=membership.group_id,
        status="active",
        created_by_user_id=admin.id,
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)
    service.admin_grant(admin, membership, assessment.cost, "На зачет", "assessment-balance")
    service.buy_assessment(member, membership, assessment, "assessment-paid")

    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "alice", "password": "password123", "csrf_token": token},
    )
    pending_response = client.get("/me")

    assert pending_response.status_code == 200
    assert pending_response.text.count('data-history-row') >= 13
    assert 'data-history-row hidden' in pending_response.text
    assert "Оплачено" in pending_response.text
    assert 'disabled class="reward-pay-button paid"' in pending_response.text
    assert "Прошедние" in pending_response.text
    assert "Зачет по продукту" in pending_response.text


def test_member_dashboard_stays_mobile_sized_on_desktop():
    css = Path("app/static/css/member.css").read_text()

    assert "width: min(100%, 31rem);" in css
    assert "@media (min-width: 861px)" in css
    assert "height: min(54rem, calc(100vh - 3rem));" in css
    assert "overflow-y: auto;" in css
    assert "position: sticky;" in css
    assert "bottom: 0;" in css
    assert ".mobile-app-menu span" not in css
    assert ".mobile-app-menu button::after" in css
    assert ".student-section {\n\tmargin-top: 1rem;\n\tpadding: 0;" in css
    assert "background: transparent;" in css
    assert "box-shadow: none;" in css
    assert "min-height: 9.5rem;" in css
    assert "background: var(--app-shell-bg);" in css
    assert "backdrop-filter: blur(18px);" in css
    assert ".transfer-summary::before" in css
    assert "justify-content: center;" in css
    assert ".tab-panel[hidden]" in css
    assert "@media (min-width: 860px)" not in css
    assert "grid-template-columns: minmax(0, 1fr) 14rem" not in css
    assert "width: 24rem;" not in css


def test_admin_can_see_groups_and_group_members(client, admin, members, db_session: Session):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )
    group = db_session.query(Group).filter_by(slug="core").one()

    groups_response = client.get("/admin/groups")
    detail_response = client.get(f"/admin/groups/{group.id}")

    assert groups_response.status_code == 200
    assert "Core Team" in groups_response.text
    assert 'data-admin-modal-open="create-group-modal"' in groups_response.text
    assert 'id="create-group-modal"' in groups_response.text
    assert "Создать группу" in groups_response.text
    assert f'action="/admin/groups/{group.id}/delete"' in groups_response.text
    assert "Код ссылки" not in groups_response.text
    assert "Код приглашения" not in groups_response.text
    assert detail_response.status_code == 200
    assert "Alice" in detail_response.text
    assert "Bob" in detail_response.text
    assert "Удалить группу" in detail_response.text
    assert "mini-avatar" not in detail_response.text


def test_admin_can_delete_group_with_related_records(client, admin, db_session: Session):
    group = GroupService(db_session).create_group("Delete Me", "delete-me", "DELETE")
    member = AuthService(db_session).register_member("delete_user", "password123", "Delete User", group.id)
    membership = member.memberships[0]
    service = CoinService(db_session)
    service.admin_grant(admin, membership, 200, "Seed", "delete-grant")
    assessment = Assessment(
        title="Delete assessment",
        topic="Cleanup",
        description="Temporary",
        cost=50,
        scope="group",
        group_id=group.id,
        status="active",
        created_by_user_id=admin.id,
    )
    db_session.add(assessment)
    db_session.commit()
    db_session.refresh(assessment)
    service.buy_assessment(member, membership, assessment, "delete-assessment-payment")

    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )
    response = client.post(f"/admin/groups/{group.id}/delete", data={"csrf_token": token})

    assert response.status_code == 303
    assert db_session.get(Group, group.id) is None
    assert db_session.query(Membership).filter_by(group_id=group.id).count() == 0
    assert db_session.query(Assessment).filter_by(group_id=group.id).count() == 0
    assert db_session.query(AssessmentPayment).count() == 0
    assert db_session.query(CoinTransaction).filter_by(group_id=group.id).count() == 0


def test_group_stats_exclude_system_commission_membership(db_session: Session, admin):
    group = GroupService(db_session).create_group("Marketing", "marketing", "MARKETING")
    auth = AuthService(db_session)
    first = auth.register_member("first_student", "password123", "First Student", group.id)
    second = auth.register_member("second_student", "password123", "Second Student", group.id)
    auth.register_member("third_student", "password123", "Third Student", group.id)

    service = CoinService(db_session)
    service.admin_grant(admin, first.memberships[0], 1000, "Start", "stats-grant")
    service.peer_transfer(first, first.memberships[0], second.memberships[0], 100, "Share", "stats-transfer")

    stats = next(row for row in GroupService(db_session).list_groups_with_stats() if row["group"].id == group.id)

    assert stats["participants_count"] == 3
    assert stats["total_coins"] == 999


def test_admin_delete_group_frees_member_login(client, admin, db_session: Session):
    group_service = GroupService(db_session)
    group = group_service.create_group("Archive Me", "archive-me", "ARCHIVE")
    member = AuthService(db_session).register_member("reuse_login", "password123", "Reuse Login", group.id)

    group_service.delete_group(group.id)
    archived_user = db_session.get(User, member.id)
    new_group = group_service.create_group("Fresh Group", "fresh-group", "FRESH")
    new_user = AuthService(db_session).register_member("reuse_login", "password456", "Reuse Login", new_group.id)

    assert archived_user is not None
    assert archived_user.is_active is False
    assert archived_user.username.startswith(f"deleted_{member.id}_")
    assert new_user.id != member.id
    assert new_user.username == "reuse_login"


def test_seed_does_not_resurrect_deleted_demo_groups(db_session: Session):
    AuthService(db_session).create_user("gluhov", "real-password", "Глухов", role=UserRole.ADMIN)

    seed(db_session)
    marketing = db_session.query(Group).filter_by(slug="marketing").one()
    GroupService(db_session).delete_group(marketing.id)

    seed(db_session)

    assert db_session.query(AppSetting).filter_by(key="demo_seeded", value="true").one_or_none() is not None
    assert db_session.query(Group).filter_by(slug="marketing").one_or_none() is None


def test_seed_creates_demo_admin_without_resetting_existing_admin(db_session: Session):
    existing_admin = AuthService(db_session).create_user("gluhov", "real-password", "Глухов", role=UserRole.ADMIN)

    seed(db_session)
    db_session.refresh(existing_admin)
    demo_admin = db_session.query(User).filter_by(username="admin").one()

    assert verify_password("real-password", existing_admin.password_hash)
    assert verify_password("admin", demo_admin.password_hash)
    assert db_session.query(User).filter_by(username="gluhov").one_or_none() is not None


def test_admin_pages_use_dark_teacher_shell(client, admin, members):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )

    response = client.get("/admin")

    assert response.status_code == 200
    assert "/static/css/admin.css" in response.text
    assert "/static/css/app.css" not in response.text
    assert 'class="admin-body"' in response.text
    assert 'class="admin-shell"' in response.text
    assert 'class="admin-sidebar"' in response.text
    assert 'class="crm-dashboard-grid"' in response.text
    assert "Быстрые разделы" not in response.text
    assert "Профили, балансы, пароли и заметки" not in response.text
    assert 'class="pagination"' not in response.text
    assert 'class="tabs"' not in response.text
    assert "NEURO COIN" in response.text
    assert "Преподавательская панель" in response.text
    assert "System Access" not in response.text
    assert "Invite code" not in response.text
    assert "confirm-modal" in response.text


def test_admin_can_update_transfer_percent_settings(client, admin, members):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )

    page = client.get("/admin/settings")
    assert page.status_code == 200
    assert "Комиссия, %" in page.text
    assert "Максимум перевода, % от баланса" in page.text

    response = client.post(
        "/admin/settings",
        data={
            "transfer_fee_percent": "2.50",
            "transfer_max_percent": "55.00",
            "csrf_token": token,
        },
    )
    assert response.status_code == 303

    updated = client.get("/admin/settings")
    assert 'value="2.50"' in updated.text
    assert 'value="55.00"' in updated.text


def test_admin_can_change_own_password_from_settings(client, admin, db_session: Session):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )

    bad_response = client.post(
        "/admin/settings/password",
        data={
            "current_password": "wrong-password",
            "new_password": "new-admin-pass",
            "confirm_password": "new-admin-pass",
            "csrf_token": token,
        },
    )
    db_session.refresh(admin)

    assert bad_response.status_code == 400
    assert verify_password("admin12345", admin.password_hash)

    good_response = client.post(
        "/admin/settings/password",
        data={
            "current_password": "admin12345",
            "new_password": "new-admin-pass",
            "confirm_password": "new-admin-pass",
            "csrf_token": token,
        },
    )
    db_session.refresh(admin)

    assert good_response.status_code == 303
    assert verify_password("new-admin-pass", admin.password_hash)


def test_admin_styles_define_black_sidebar_grid():
    css = Path("app/static/css/admin.css").read_text()

    assert "background: #000;" in css
    assert ".admin-sidebar" in css
    assert "grid-template-columns: 17.5rem minmax(0, 1fr);" in css
    assert ".crm-dashboard-grid" in css
    assert ".profile-grid" in css
    assert ".admin-combobox" in css
    assert ".admin-combobox.is-open {\n\tz-index: 80;\n}" in css
    assert ".native-select" in css
    assert ".access-toggle" in css
    assert ".mini-avatar" not in css
    assert "window.confirm" not in Path("app/static/js/app.js").read_text()
    assert "studentSelect.value = \"\";" in Path("app/static/js/app.js").read_text()
    assert 'input.addEventListener("click", openOptions);' in Path("app/static/js/app.js").read_text()
    assert 'button.addEventListener("pointerdown"' in Path("app/static/js/app.js").read_text()
    assert 'button.addEventListener("mousedown"' in Path("app/static/js/app.js").read_text()
    assert 'document.addEventListener("pointerdown", (event) => {' in Path("app/static/js/app.js").read_text()
    assert 'input.addEventListener("blur"' not in Path("app/static/js/app.js").read_text()
    assert 'select.addEventListener("change", () => {\n      input.value = selectedText();\n      rebuild();' not in Path("app/static/js/app.js").read_text()
    assert "@media (max-width: 900px)" in css
    assert "--admin-type-page: 2.35rem;" in css
    assert "--student-type-title: 1.65rem;" in Path("app/static/css/member.css").read_text()


def test_seed_creates_full_demo_dataset(db_session: Session):
    AuthService(db_session).create_user("gluhov", "real-password", "Глухов", role=UserRole.ADMIN)

    seed(db_session)
    seed(db_session)

    assert db_session.query(Group).count() >= 3
    assert db_session.query(RewardCatalog).count() >= 3
    assert db_session.query(Assessment).count() >= 4
    assert db_session.query(AssessmentPayment).count() >= 2
    assert db_session.query(CoinTransaction).count() >= 8
    assert db_session.query(RewardRedemption).count() >= 2
    groups = GroupService(db_session).list_groups_with_stats()
    demo_group_names = {row["group"].name for row in groups}
    assert {"Маркетинг", "Дизайн", "Разработка"}.issubset(demo_group_names)
    assert sum(int(row["participants_count"]) for row in groups) >= 12
    assert sum(int(row["total_coins"]) for row in groups) > 0


def test_group_service_reports_admin_views(db_session: Session, admin, members):
    groups = GroupService(db_session).list_groups_with_stats()

    assert groups[0]["participants_count"] == 2
    assert groups[0]["total_coins"] == 0
