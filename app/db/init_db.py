from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.assessment import Assessment
from app.db.session import SessionLocal
from app.models.audit import AppSetting
from app.models.group import Group
from app.models.membership import Membership
from app.models.reward import RewardCatalog
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.coin_service import CoinService
from app.services.group_service import GroupService
from app.services.settings_service import SettingsService


DEMO_GROUPS = [
    ("Маркетинг", "marketing", "MARKET"),
    ("Дизайн", "design", "DESIGN"),
    ("Разработка", "dev", "DEV"),
]

DEMO_REWARDS = [
    ("credit", "Зачёт", "Заявка на зачёт", 100),
    ("lab", "Лабораторная", "Закрытие лабораторной работы", 60),
    ("exam_bonus", "Бонус к экзамену", "Дополнительные баллы к итоговой работе", 180),
]

DEMO_MEMBERS = [
    ("student", "Student", "marketing", 140, "Стартовый баланс"),
    ("ivanov", "Иванов Иван", "marketing", 250, "Активность на семинаре"),
    ("petrov", "Петров Петр", "marketing", 150, "Проектная работа"),
    ("sidorova", "Сидорова Анна", "marketing", 320, "Лидерство в команде"),
    ("kuznetsov", "Кузнецов Алексей", "marketing", 90, "Домашнее задание"),
    ("smirnov", "Смирнов Олег", "marketing", 410, "Дополнительное исследование"),
    ("demo_staff", "Demo User", "operations", 0, ""),
    ("demo_student", "Демо Студент", "marketing", 140, "Стартовый баланс"),
    ("demo_peer", "Демо Однокурсник", "marketing", 0, ""),
    ("volkova", "Волкова Мария", "design", 220, "Макет интерфейса"),
    ("orlov", "Орлов Денис", "design", 175, "Презентация"),
    ("belova", "Белова Кира", "dev", 260, "Backend sprint"),
    ("egorov", "Егоров Павел", "dev", 130, "Code review"),
]

DEMO_ASSESSMENTS = [
    ("Зачет по нейросетям", "Нейронные сети", "Групповой зачет по базовым архитектурам", 100, "group", "marketing", None, "active"),
    ("Практика CRM", "Продуктовые сценарии", "Индивидуальная проверка демо-студента", 80, "student", "marketing", "demo_student", "active"),
    ("Проектный модуль", "Командная работа", "Закрытый прошлый зачет", 120, "group", "design", None, "past"),
    ("Backend sprint", "API и транзакции", "Зачет для группы разработки", 140, "group", "dev", None, "active"),
]

DEMO_SEEDED_KEY = "demo_seeded"


def ensure_admin(db: Session, username: str, password: str, display_name: str | None = None) -> User:
    auth = AuthService(db)
    SettingsService(db).ensure_defaults()
    normalized_username = username.strip().lower()
    if not normalized_username:
        raise ValueError("Admin username is required")
    if not password:
        raise ValueError("Admin password is required")

    admin = db.query(User).filter_by(username=normalized_username).one_or_none()
    if admin is None:
        return auth.create_user(
            normalized_username,
            password,
            display_name.strip() if display_name else normalized_username,
            UserRole.ADMIN,
        )

    admin.display_name = display_name.strip() if display_name else admin.display_name or normalized_username
    admin.password_hash = hash_password(password)
    admin.is_active = True
    admin.role = UserRole.ADMIN
    db.commit()
    db.refresh(admin)
    return admin


def _demo_seeded_setting(db: Session) -> AppSetting | None:
    return db.query(AppSetting).filter_by(key=DEMO_SEEDED_KEY).one_or_none()


def _mark_demo_seeded(db: Session) -> None:
    setting = _demo_seeded_setting(db)
    if setting is None:
        setting = AppSetting(key=DEMO_SEEDED_KEY, value="true")
        db.add(setting)
    else:
        setting.value = "true"
    db.commit()


def seed(db: Session) -> None:
    marker = _demo_seeded_setting(db)
    admin = ensure_admin(db, "admin", "admin", "Admin")

    if marker is not None and marker.value == "true":
        return

    auth = AuthService(db)
    group_service = GroupService(db)
    coin_service = CoinService(db)
    SettingsService(db).ensure_defaults()

    groups: dict[str, Group] = {}
    for name, slug, invite_code in DEMO_GROUPS:
        group = db.query(Group).filter_by(slug=slug).one_or_none()
        if group is None:
            group = group_service.create_group(name, slug, invite_code)
        else:
            group.name = name
            group.invite_code = invite_code
            group.is_active = True
            db.commit()
            db.refresh(group)
        groups[slug] = group

    rewards: dict[str, RewardCatalog] = {}
    for code, title, description, price in DEMO_REWARDS:
        reward = db.query(RewardCatalog).filter_by(code=code).one_or_none()
        if reward is None:
            reward = RewardCatalog(code=code, title=title, description=description, price=price, is_active=True)
            db.add(reward)
        else:
            reward.title = title
            reward.description = description
            reward.price = price
            reward.is_active = True
        db.commit()
        db.refresh(reward)
        rewards[code] = reward

    memberships: dict[str, Membership] = {}
    for username, display_name, group_slug, grant_amount, reason in DEMO_MEMBERS:
        password = "student" if username == "student" else "password123"
        user = db.query(User).filter_by(username=username).one_or_none()
        if user is None:
            user = auth.register_member(username, password, display_name, groups[group_slug].id)
        else:
            user.display_name = display_name
            user.password_hash = hash_password(password)
            user.is_active = True
            user.role = UserRole.MEMBER
            db.commit()
            db.refresh(user)

        membership = (
            db.query(Membership)
            .filter_by(user_id=user.id, group_id=groups[group_slug].id)
            .one_or_none()
        )
        if membership is None:
            membership = Membership(user_id=user.id, group_id=groups[group_slug].id, status="active")
            db.add(membership)
            db.flush()
            coin_service._account_for_membership(membership)
            db.commit()
            db.refresh(membership)
        memberships[username] = membership

        if grant_amount > 0:
            coin_service.admin_grant(
                admin,
                membership,
                grant_amount,
                reason or "Демо начисление",
                f"demo-seed-grant-{username}",
            )

    coin_service.peer_transfer(
        memberships["ivanov"].user,
        memberships["ivanov"],
        memberships["petrov"],
        30,
        "Помощь с конспектом",
        "demo-seed-transfer-ivanov-petrov",
    )
    coin_service.peer_transfer(
        memberships["sidorova"].user,
        memberships["sidorova"],
        memberships["demo_student"],
        45,
        "Командный проект",
        "demo-seed-transfer-sidorova-demo",
    )

    pending = coin_service.buy_reward(memberships["demo_student"].user, memberships["demo_student"], rewards["credit"], "demo-seed-reward-demo")
    fulfilled = coin_service.buy_reward(memberships["smirnov"].user, memberships["smirnov"], rewards["lab"], "demo-seed-reward-smirnov")
    if fulfilled.status == "pending":
        coin_service.fulfill_redemption(admin, fulfilled, "demo-seed-fulfill-smirnov")
    if pending.status != "pending":
        pending.status = "pending"
        pending.fulfilled_at = None
        db.commit()

    assessment_rows: dict[str, Assessment] = {}
    for title, topic, description, cost, scope, group_slug, username, status in DEMO_ASSESSMENTS:
        group = groups[group_slug]
        student_membership = memberships[username] if username else None
        assessment = db.query(Assessment).filter_by(title=title, group_id=group.id).one_or_none()
        if assessment is None:
            assessment = Assessment(
                title=title,
                topic=topic,
                description=description,
                cost=cost,
                scope=scope,
                group_id=group.id,
                student_membership_id=student_membership.id if student_membership else None,
                status=status,
                created_by_user_id=admin.id,
            )
            db.add(assessment)
        else:
            assessment.topic = topic
            assessment.description = description
            assessment.cost = cost
            assessment.scope = scope
            assessment.group_id = group.id
            assessment.student_membership_id = student_membership.id if student_membership else None
            assessment.status = status
        db.commit()
        db.refresh(assessment)
        assessment_rows[title] = assessment

    coin_service.buy_assessment(
        memberships["demo_student"].user,
        memberships["demo_student"],
        assessment_rows["Практика CRM"],
        "demo-seed-assessment-demo-practice",
    )
    assessment_rows["Проектный модуль"].status = "active"
    db.commit()
    coin_service.buy_assessment(
        memberships["volkova"].user,
        memberships["volkova"],
        assessment_rows["Проектный модуль"],
        "demo-seed-assessment-volkova-project",
    )
    assessment_rows["Проектный модуль"].status = "past"
    db.commit()
    _mark_demo_seeded(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Neuro Coin database data.")
    parser.add_argument("--demo", action="store_true", help="Create or update the full demo dataset.")
    parser.add_argument("--admin", help="Create or update an admin account without demo data.")
    parser.add_argument("--admin-password", help="Password for --admin.")
    parser.add_argument("--has-admin", action="store_true", help="Exit with 0 when at least one active admin exists.")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.has_admin:
            has_admin = (
                db.query(User.id)
                .filter(User.role == UserRole.ADMIN, User.is_active.is_(True), ~User.username.like("__system__%"))
                .first()
                is not None
            )
            raise SystemExit(0 if has_admin else 1)
        if args.admin:
            ensure_admin(db, args.admin, args.admin_password or "")
            print(f"Admin account ready: {args.admin}")
            return
        seed(db)
        print("Demo data ready.")


if __name__ == "__main__":
    main()
