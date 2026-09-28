from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.coin import CoinAccount
from app.models.group import Group
from app.models.membership import Membership
from app.models.user import User, UserRole


class AuthServiceError(ValueError):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str,
        role: UserRole = UserRole.MEMBER,
    ) -> User:
        user = User(
            username=username.strip().lower(),
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            role=role,
        )
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AuthServiceError("Пользователь с таким логином уже существует") from exc
        self.db.refresh(user)
        return user

    def register_member(self, username: str, password: str, display_name: str, group_id: int) -> User:
        group = self.db.get(Group, group_id)
        if group is None or not group.is_active:
            raise AuthServiceError("Группа недоступна")
        user = User(
            username=username.strip().lower(),
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            role=UserRole.MEMBER,
        )
        membership = Membership(user=user, group=group, status="active")
        account = CoinAccount(membership=membership, balance_cached=0)
        self.db.add_all([user, membership, account])
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AuthServiceError("Не удалось зарегистрировать участника") from exc
        self.db.refresh(user)
        return user

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.db.query(User).filter(User.username == username.strip().lower()).one_or_none()
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
