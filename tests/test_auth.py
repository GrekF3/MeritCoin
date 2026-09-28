from pathlib import Path

from sqlalchemy.orm import Session

from app.models.coin import CoinAccount
from app.models.group import Group
from app.models.membership import Membership
from app.models.user import User


def test_registration_creates_user_membership_and_account(client, db_session: Session):
    group = db_session.query(Group).filter_by(slug="core").one()
    response = client.post(
        "/register",
        data={
            "username": "newmember",
            "display_name": "New Member",
            "password": "secret12345",
            "group_id": str(group.id),
            "csrf_token": client.get("/register").cookies.get("csrf_token", ""),
        },
    )

    assert response.status_code == 303
    user = db_session.query(User).filter_by(username="newmember").one()
    membership = db_session.query(Membership).filter_by(user_id=user.id, group_id=group.id).one()
    account = db_session.query(CoinAccount).filter_by(membership_id=membership.id).one()
    assert account.balance_cached == 0


def test_login_works(client, admin):
    token = client.get("/login").cookies["csrf_token"]
    login_page = client.get("/login")
    assert "/static/css/easter.css" in login_page.text
    assert "/static/js/easter.js" in login_page.text
    assert Path("app/static/img/easter/tractor.mp4").exists()
    assert "BOOM_DELAY_MS = 950" in Path("app/static/js/easter.js").read_text()
    assert 'playsinline loop' in Path("app/static/js/easter.js").read_text()
    assert 'controls' not in Path("app/static/js/easter.js").read_text()
    assert ".easter-blast" in Path("app/static/css/easter.css").read_text()
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert "session" in response.cookies


def test_root_serves_landing_and_login_redirects_by_role(client, admin, members):
    anonymous = client.get("/")
    assert anonymous.status_code == 200
    assert "NEURO COIN" in anonymous.text
    assert "Присоединиться" in anonymous.text

    token = client.get("/login").cookies["csrf_token"]
    admin_response = client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )
    assert admin_response.headers["location"] == "/admin"
    admin_root = client.get("/")
    assert admin_root.status_code == 200
    assert "NEURO COIN" in admin_root.text

    client.post("/logout", data={"csrf_token": client.cookies["csrf_token"]})
    token = client.get("/login").cookies["csrf_token"]
    member_response = client.post(
        "/login",
        data={"username": "alice", "password": "password123", "csrf_token": token},
    )
    assert member_response.headers["location"] == "/me"
    member_root = client.get("/")
    assert member_root.status_code == 200
    assert "NEURO COIN" in member_root.text


def test_landing_page_is_separate_from_app_root(client):
    root_response = client.get("/")
    landing_response = client.get("/landing")

    assert root_response.status_code == 200
    assert "Присоединиться" in root_response.text
    assert landing_response.status_code == 200
    assert "NEURO COIN" in landing_response.text
    assert "NEURO COIN / STUDENTS" not in landing_response.text
    assert "neuro-logo" not in landing_response.text
    assert "Это будущее студентов" in landing_response.text
    assert "Закрывайте свои зачеты с помощью коинов" in landing_response.text
    assert "Обменивайтесь коинами со своими однокурсниками" in landing_response.text
    assert 'href="/login"' in landing_response.text
    assert "Присоединиться" in landing_response.text
    assert "REALTIME" not in landing_response.text
    assert "WEBGL" not in landing_response.text
    assert "The future" not in landing_response.text
    assert "/static/css/landing.css" in landing_response.text


def test_public_pages_use_local_assets(client):
    for path in ("/", "/login", "/register"):
        response = client.get(path)
        assert response.status_code == 200
        assert "cdn.jsdelivr.net" not in response.text
        assert "raw.githubusercontent.com" not in response.text
        assert "REALTIME" not in response.text
        assert "WEBGL" not in response.text


def test_auth_pages_match_landing_brand_and_keep_forms(client):
    login_response = client.get("/login")
    register_response = client.get("/register")

    assert "/static/css/auth.css" in login_response.text
    assert "/static/css/auth.css" in register_response.text
    assert "/static/js/auth.js" in login_response.text
    assert "/static/js/auth.js" in register_response.text
    assert "NEURO COIN" in login_response.text
    assert "NEURO COIN" in register_response.text
    assert "auth-neural-canvas" in login_response.text
    assert "auth-neural-canvas" in register_response.text
    assert 'action="/login"' in login_response.text
    assert 'name="username"' in login_response.text
    assert 'name="password"' in login_response.text
    assert 'action="/register"' in register_response.text
    assert 'name="display_name"' in register_response.text
    assert 'name="group_id"' in register_response.text
    assert 'name="group_search"' in register_response.text
    assert 'class="auth-panel"' not in login_response.text
    assert 'class="auth-panel"' not in register_response.text
    assert "<h1" not in login_response.text
    assert "<h1" not in register_response.text
    assert 'class="auth-submit-text"' in login_response.text
    assert 'class="auth-submit-text"' in register_response.text


def test_auth_button_uses_refined_sheen_not_bright_fill():
    css = Path("app/static/css/auth.css").read_text()

    assert ".auth-submit::before" in css
    assert ".auth-submit::after" in css
    assert "backdrop-filter: blur" in css
    assert "0 0.7rem 0" not in css
    assert "background:\n\t\tlinear-gradient(100deg, var(--blue)" not in css
    assert "background-clip: text" not in css
    assert "-webkit-background-clip: text" not in css
    assert "color: transparent" not in css


def test_member_cannot_access_admin(client, members):
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "alice", "password": "password123", "csrf_token": token},
    )

    response = client.get("/admin")

    assert response.status_code == 403
