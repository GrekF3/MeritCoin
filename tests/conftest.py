import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.group import Group
from app.models.reward import RewardCatalog
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.group_service import GroupService


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        group = Group(name="Core Team", slug="core", invite_code="CORE")
        reward = RewardCatalog(code="credit", title="Зачёт", price=100, is_active=True)
        db.add_all([group, reward])
        db.commit()
        yield db


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin(db_session: Session) -> User:
    return AuthService(db_session).create_user(
        username="admin",
        password="admin12345",
        display_name="Admin",
        role=UserRole.ADMIN,
    )


@pytest.fixture()
def members(db_session: Session) -> tuple[User, User]:
    auth = AuthService(db_session)
    group = db_session.query(Group).filter_by(slug="core").one()
    first = auth.register_member("alice", "password123", "Alice", group.id)
    second = auth.register_member("bob", "password123", "Bob", group.id)
    return first, second


@pytest.fixture()
def other_group_member(db_session: Session) -> User:
    group = GroupService(db_session).create_group("Second Team", "second", "SECOND")
    return AuthService(db_session).register_member("charlie", "password123", "Charlie", group.id)
