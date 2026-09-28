from sqlalchemy.orm import Session

from app.models.assessment import AssessmentPayment
from app.services.assessment_service import AssessmentService
from app.services.coin_service import CoinService, CoinServiceError
import pytest


def test_group_assessment_is_visible_to_group_only(db_session: Session, admin, members, other_group_member):
    first, second = members
    first_membership = first.memberships[0]
    second_membership = second.memberships[0]
    other_membership = other_group_member.memberships[0]
    service = AssessmentService(db_session)
    assessment = service.create_assessment(
        admin,
        "Зачет группы",
        "Командная тема",
        None,
        100,
        "group",
        first_membership.group_id,
        None,
        None,
    )

    assert assessment in service.assigned_to(first_membership)
    assert assessment in service.assigned_to(second_membership)
    assert assessment not in service.assigned_to(other_membership)


def test_student_assessment_is_visible_only_to_selected_student(db_session: Session, admin, members):
    first, second = members
    first_membership = first.memberships[0]
    second_membership = second.memberships[0]
    service = AssessmentService(db_session)
    assessment = service.create_assessment(
        admin,
        "Личный зачет",
        "Индивидуальная тема",
        None,
        80,
        "student",
        first_membership.group_id,
        first_membership.id,
        None,
    )

    assert assessment in service.assigned_to(first_membership)
    assert assessment not in service.assigned_to(second_membership)


def test_assessment_payment_spends_balance_and_blocks_duplicates(db_session: Session, admin, members):
    member, _ = members
    membership = member.memberships[0]
    assessment = AssessmentService(db_session).create_assessment(
        admin,
        "Оплачиваемый зачет",
        "Проверка оплаты",
        None,
        100,
        "group",
        membership.group_id,
        None,
        None,
    )
    coin_service = CoinService(db_session)
    coin_service.admin_grant(admin, membership, 120, "Старт", "assessment-grant")
    payment = coin_service.buy_assessment(member, membership, assessment, "assessment-pay")

    assert payment.status == "paid"
    assert membership.account.balance_cached == 20
    assert db_session.query(AssessmentPayment).filter_by(assessment_id=assessment.id, membership_id=membership.id).count() == 1
    with pytest.raises(CoinServiceError):
        coin_service.buy_assessment(member, membership, assessment, "assessment-pay-duplicate")


def test_admin_can_create_assessment_and_edit_student_password(client, admin, members):
    member, _ = members
    membership = member.memberships[0]
    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )

    create_response = client.post(
        "/admin/assessments",
        data={
            "title": "Новый зачет",
            "topic": "Тестовая тема",
            "description": "",
            "cost": "90",
            "scope": "group",
            "group_id": str(membership.group_id),
            "student_membership_id": "",
            "due_at": "",
            "csrf_token": token,
        },
    )
    assert create_response.status_code == 303
    list_response = client.get("/admin/assessments")
    assert list_response.status_code == 200
    assert 'data-admin-modal-open="create-assessment-modal"' in list_response.text
    assert 'id="create-assessment-modal"' in list_response.text
    assert "Список зачетов" in list_response.text
    assert "<table>" in list_response.text
    assert "<th>Зачет</th>" in list_response.text
    assert "data-confirm-heading=\"Изменить статус зачета?\"" in list_response.text
    assert "data-confirm-modal" in list_response.text

    update_response = client.post(
        f"/admin/students/{membership.id}",
        data={
            "display_name": "Alice Updated",
            "username": "alice_updated",
            "group_id": str(membership.group_id),
            "status": "active",
            "admin_note": "Хорошая динамика",
            "password": "newpassword123",
            "is_active": "on",
            "csrf_token": token,
        },
    )
    assert update_response.status_code == 303

    token = client.get("/login").cookies["csrf_token"]
    login_response = client.post(
        "/login",
        data={"username": "alice_updated", "password": "newpassword123", "csrf_token": token},
    )
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/me"


def test_group_assessment_detail_lists_students_payments_and_updates(client, db_session: Session, admin, members):
    first, second = members
    first_membership = first.memberships[0]
    second_membership = second.memberships[0]
    assessment = AssessmentService(db_session).create_assessment(
        admin,
        "Групповой зачет",
        "CRM",
        "Описание",
        50,
        "group",
        first_membership.group_id,
        None,
        None,
    )
    coin_service = CoinService(db_session)
    coin_service.admin_grant(admin, first_membership, 100, "Старт", "group-detail-grant")
    coin_service.buy_assessment(first, first_membership, assessment, "group-detail-pay")

    token = client.get("/login").cookies["csrf_token"]
    client.post(
        "/login",
        data={"username": "admin", "password": "admin12345", "csrf_token": token},
    )

    response = client.get(f"/admin/groups/{first_membership.group_id}?assessment_id={assessment.id}")

    assert response.status_code == 200
    assert "Редактирование зачета" in response.text
    assert "Студенты в зачете" in response.text
    assert "Alice" in response.text
    assert "Bob" in response.text
    assert "Оплачен" in response.text
    assert "Не оплачен" in response.text
    assert f'/admin/groups/{first_membership.group_id}?assessment_id={assessment.id}' in response.text

    update_response = client.post(
        f"/admin/groups/{first_membership.group_id}/assessments/{assessment.id}",
        data={
            "title": "Обновленный зачет",
            "topic": "CRM 2",
            "description": "Новая заметка",
            "cost": "75",
            "status": "past",
            "due_at": "",
            "csrf_token": token,
        },
    )

    assert update_response.status_code == 303
    db_session.refresh(assessment)
    assert assessment.title == "Обновленный зачет"
    assert assessment.topic == "CRM 2"
    assert assessment.cost == 75
    assert assessment.status == "past"
    assert second_membership.id != first_membership.id
