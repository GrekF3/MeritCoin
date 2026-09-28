from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, verify_password
from app.core.csrf import validate_csrf
from app.core.permissions import require_admin
from app.db.session import get_db
from app.models.assessment import Assessment, AssessmentPayment
from app.models.coin import CoinAccount, CoinTransaction
from app.models.group import Group
from app.models.membership import Membership
from app.models.reward import RewardRedemption
from app.models.user import User, UserRole
from app.routers.utils import redirect, render
from app.services.assessment_service import AssessmentService, AssessmentServiceError
from app.services.coin_service import CoinService, CoinServiceError
from app.services.group_service import GroupService
from app.services.settings_service import SettingsService, SettingsServiceError
from app.utils.money import money_float

router = APIRouter()


def _dashboard_context(db: Session, admin: User, error: str | None = None) -> dict[str, object]:
    group_service = GroupService(db)
    groups = group_service.list_groups_with_stats()
    preferred_group = next((row["group"] for row in groups if row["group"].slug == "marketing"), None)
    selected_group = group_service.get_group_with_members((preferred_group or groups[0]["group"]).id) if groups else None
    visible_memberships = [
        item
        for item in (selected_group.memberships if selected_group else [])
        if not item.user.username.startswith("__system__") and item.status == "active"
    ]
    visible_memberships.sort(key=lambda item: item.account.balance_cached if item.account else 0, reverse=True)
    all_memberships = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .options(selectinload(Membership.user), selectinload(Membership.account), selectinload(Membership.group))
        .filter(~User.username.startswith("__system__"), Membership.status == "active")
        .order_by(User.display_name)
        .all()
    )
    total_members = len(all_memberships)
    total_coins = sum(float(row["total_coins"]) for row in groups)
    pending = db.query(Assessment).filter_by(status="active").count()
    transactions = db.query(CoinTransaction).order_by(CoinTransaction.created_at.desc()).limit(8).all()
    payments = (
        db.query(AssessmentPayment)
        .options(selectinload(AssessmentPayment.assessment), selectinload(AssessmentPayment.membership).selectinload(Membership.user))
        .order_by(AssessmentPayment.created_at.desc())
        .limit(8)
        .all()
    )
    return {
        "user": admin,
        "stats": {
            "groups": len(groups),
            "members": total_members,
            "coins": total_coins,
            "pending": pending,
        },
        "transactions": transactions,
        "payments": payments,
        "groups": groups,
        "selected_group": selected_group,
        "visible_memberships": visible_memberships,
        "all_memberships": all_memberships,
        "error": error,
    }


@router.get("/admin")
def dashboard(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return render(
        request,
        "admin/dashboard.html",
        _dashboard_context(db, admin),
    )


@router.get("/admin/groups")
def groups_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return render(request, "admin/groups.html", {"user": admin, "groups": GroupService(db).list_groups_with_stats(), "error": None})


@router.post("/admin/groups")
def create_group(
    request: Request,
    name: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        GroupService(db).create_group(name)
    except ValueError as exc:
        return render(request, "admin/groups.html", {"user": admin, "groups": GroupService(db).list_groups_with_stats(), "error": str(exc)}, status_code=400)
    return redirect("/admin/groups")


@router.post("/admin/groups/{group_id}/delete")
def delete_group(
    request: Request,
    group_id: int,
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    group_service = GroupService(db)
    try:
        group_service.delete_group(group_id)
    except ValueError as exc:
        return render(
            request,
            "admin/groups.html",
            {"user": admin, "groups": group_service.list_groups_with_stats(), "error": str(exc)},
            status_code=400,
        )
    return redirect("/admin/groups")


def _student_query(db: Session):
    return (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .options(selectinload(Membership.user), selectinload(Membership.group), selectinload(Membership.account))
        .filter(~User.username.startswith("__system__"), User.role == UserRole.MEMBER)
    )


@router.get("/admin/students")
def students_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    students = _student_query(db).order_by(User.display_name).all()
    groups = GroupService(db).active_groups()
    return render(request, "admin/students.html", {"user": admin, "students": students, "groups": groups, "error": None})


def _student_profile_context(db: Session, admin: User, membership: Membership, error: str | None = None) -> dict[str, object]:
    transactions = (
        db.query(CoinTransaction)
        .outerjoin(CoinAccount, (CoinAccount.id == CoinTransaction.from_account_id) | (CoinAccount.id == CoinTransaction.to_account_id))
        .filter(CoinAccount.membership_id == membership.id)
        .order_by(CoinTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    assessments = (
        db.query(Assessment)
        .options(selectinload(Assessment.payments))
        .filter(
            ((Assessment.scope == "group") & (Assessment.group_id == membership.group_id))
            | ((Assessment.scope == "student") & (Assessment.student_membership_id == membership.id))
        )
        .order_by(Assessment.status, Assessment.created_at.desc())
        .all()
    )
    payments = {
        payment.assessment_id: payment
        for payment in db.query(AssessmentPayment).filter_by(membership_id=membership.id).all()
    }
    return {
        "user": admin,
        "membership": membership,
        "groups": GroupService(db).active_groups(),
        "transactions": transactions,
        "assessments": assessments,
        "payments": payments,
        "error": error,
    }


@router.get("/admin/students/{membership_id}")
def student_profile(membership_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    membership = (
        db.query(Membership)
        .options(
            selectinload(Membership.user),
            selectinload(Membership.group),
            selectinload(Membership.account),
        )
        .filter(Membership.id == membership_id)
        .one_or_none()
    )
    if membership is None or membership.user.username.startswith("__system__"):
        raise HTTPException(status_code=404, detail="Студент не найден")
    return render(request, "admin/student_profile.html", _student_profile_context(db, admin, membership))


@router.post("/admin/students/{membership_id}")
def update_student_profile(
    membership_id: int,
    request: Request,
    display_name: str = Form(...),
    username: str = Form(...),
    group_id: int = Form(...),
    status_value: str = Form(..., alias="status"),
    admin_note: str = Form(""),
    password: str = Form(""),
    is_active: str | None = Form(None),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = (
        db.query(Membership)
        .options(selectinload(Membership.user), selectinload(Membership.group), selectinload(Membership.account))
        .filter(Membership.id == membership_id)
        .one_or_none()
    )
    if membership is None or membership.user.username.startswith("__system__"):
        raise HTTPException(status_code=404, detail="Студент не найден")
    if status_value not in {"active", "paused", "archived"}:
        return render(request, "admin/student_profile.html", _student_profile_context(db, admin, membership, "Некорректный статус"), status_code=400)
    membership.user.display_name = display_name.strip()
    membership.user.username = username.strip()
    membership.user.is_active = is_active == "on"
    membership.group_id = group_id
    membership.status = status_value
    membership.admin_note = admin_note.strip() or None
    if password.strip():
        if len(password.strip()) < 8:
            return render(request, "admin/student_profile.html", _student_profile_context(db, admin, membership, "Пароль должен быть не короче 8 символов"), status_code=400)
        membership.user.password_hash = hash_password(password.strip())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.refresh(membership)
        return render(request, "admin/student_profile.html", _student_profile_context(db, admin, membership, "Логин или группа уже заняты"), status_code=400)
    return redirect(f"/admin/students/{membership.id}")


@router.post("/admin/students/{membership_id}/grant")
def student_grant(
    request: Request,
    membership_id: int,
    amount: float = Form(...),
    reason: str = Form(...),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Студент не найден")
    try:
        CoinService(db).admin_grant(admin, membership, amount, reason, idempotency_key)
    except CoinServiceError as exc:
        membership = db.get(Membership, membership_id)
        return render(request, "admin/student_profile.html", _student_profile_context(db, admin, membership, str(exc)), status_code=400)
    return redirect(f"/admin/students/{membership.id}")


@router.post("/admin/students/{membership_id}/revoke")
def student_revoke(
    request: Request,
    membership_id: int,
    amount: float = Form(...),
    reason: str = Form(...),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Студент не найден")
    try:
        CoinService(db).admin_revoke(admin, membership, amount, reason, idempotency_key)
    except CoinServiceError as exc:
        membership = db.get(Membership, membership_id)
        return render(request, "admin/student_profile.html", _student_profile_context(db, admin, membership, str(exc)), status_code=400)
    return redirect(f"/admin/students/{membership.id}")


@router.get("/admin/assessments")
def assessments_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    students = _student_query(db).order_by(User.display_name).all()
    context = {
        "user": admin,
        "groups": GroupService(db).active_groups(),
        "students": students,
        "assessments": AssessmentService(db).list_assessments(),
        "error": None,
    }
    return render(request, "admin/assessments.html", context)


@router.post("/admin/assessments")
def create_assessment(
    request: Request,
    title: str = Form(...),
    topic: str = Form(...),
    description: str = Form(""),
    cost: float = Form(...),
    scope: str = Form(...),
    group_id: int = Form(...),
    student_membership_id: str = Form(""),
    due_at: str = Form(""),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    due = datetime.fromisoformat(due_at) if due_at else None
    try:
        parsed_student_id = int(student_membership_id) if student_membership_id else None
        AssessmentService(db).create_assessment(admin, title, topic, description, cost, scope, group_id, parsed_student_id, due)
    except (AssessmentServiceError, ValueError) as exc:
        students = _student_query(db).order_by(User.display_name).all()
        context = {
            "user": admin,
            "groups": GroupService(db).active_groups(),
            "students": students,
            "assessments": AssessmentService(db).list_assessments(),
            "error": str(exc),
        }
        return render(request, "admin/assessments.html", context, status_code=400)
    return redirect("/admin/assessments")


@router.post("/admin/assessments/{assessment_id}/status")
def update_assessment_status(
    assessment_id: int,
    status_value: str = Form(..., alias="status"),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Зачет не найден")
    if status_value not in {"active", "past"}:
        raise HTTPException(status_code=400, detail="Некорректный статус")
    assessment.status = status_value
    db.commit()
    return redirect("/admin/assessments")


@router.post("/admin/coins/grant")
def dashboard_grant(
    request: Request,
    membership_id: int = Form(...),
    amount: float = Form(...),
    reason: str = Form(...),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if membership is None:
        return render(request, "admin/dashboard.html", _dashboard_context(db, admin, "Участник не найден"), status_code=404)
    try:
        CoinService(db).admin_grant(admin, membership, amount, reason, idempotency_key)
    except CoinServiceError as exc:
        return render(request, "admin/dashboard.html", _dashboard_context(db, admin, str(exc)), status_code=400)
    return redirect("/admin")


@router.post("/admin/coins/revoke")
def dashboard_revoke(
    request: Request,
    membership_id: int = Form(...),
    amount: float = Form(...),
    reason: str = Form(...),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if membership is None:
        return render(request, "admin/dashboard.html", _dashboard_context(db, admin, "Участник не найден"), status_code=404)
    try:
        CoinService(db).admin_revoke(admin, membership, amount, reason, idempotency_key)
    except CoinServiceError as exc:
        return render(request, "admin/dashboard.html", _dashboard_context(db, admin, str(exc)), status_code=400)
    return redirect("/admin")


def _parse_due_date(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@router.get("/admin/groups/{group_id}")
def group_detail(
    group_id: int,
    request: Request,
    assessment_id: int | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    group = GroupService(db).get_group_with_members(group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Группа не найдена")
    memberships = [membership for membership in group.memberships if not membership.user.username.startswith("__system__")]
    balances = [membership.account.balance_cached for membership in memberships if membership.account]
    assessments = (
        db.query(Assessment)
        .options(selectinload(Assessment.payments).selectinload(AssessmentPayment.membership))
        .filter_by(group_id=group.id)
        .order_by(Assessment.created_at.desc())
        .limit(8)
        .all()
    )
    selected_assessment = None
    assessment_memberships = []
    assessment_payments = {}
    if assessment_id:
        selected_assessment = (
            db.query(Assessment)
            .options(selectinload(Assessment.payments).selectinload(AssessmentPayment.membership))
            .filter(Assessment.id == assessment_id, Assessment.group_id == group.id)
            .one_or_none()
        )
        if selected_assessment is None:
            raise HTTPException(status_code=404, detail="Зачет не найден")
        if selected_assessment.scope == "student" and selected_assessment.student_membership_id:
            assessment_memberships = [
                membership for membership in memberships if membership.id == selected_assessment.student_membership_id
            ]
        else:
            assessment_memberships = memberships
        assessment_payments = {payment.membership_id: payment for payment in selected_assessment.payments}
    return render(
        request,
        "admin/group_detail.html",
        {
            "user": admin,
            "group": group,
            "participants": len(memberships),
            "total_coins": sum(balances),
            "avg_balance": round(sum(balances) / len(balances), 1) if balances else 0,
            "assessments": assessments,
            "selected_assessment": selected_assessment,
            "assessment_memberships": assessment_memberships,
            "assessment_payments": assessment_payments,
        },
    )


@router.post("/admin/groups/{group_id}/assessments/{assessment_id}")
def update_group_assessment(
    group_id: int,
    assessment_id: int,
    title: str = Form(...),
    topic: str = Form(...),
    description: str = Form(""),
    cost: float = Form(...),
    status_value: str = Form(..., alias="status"),
    due_at: str = Form(""),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    assessment = db.query(Assessment).filter(Assessment.id == assessment_id, Assessment.group_id == group_id).one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Зачет не найден")
    if status_value not in {"active", "past"}:
        raise HTTPException(status_code=400, detail="Некорректный статус")
    cost = money_float(cost)
    if cost <= 0:
        raise HTTPException(status_code=400, detail="Стоимость должна быть больше нуля")
    assessment.title = title.strip()
    assessment.topic = topic.strip()
    assessment.description = description.strip() or None
    assessment.cost = cost
    assessment.status = status_value
    assessment.due_at = _parse_due_date(due_at)
    db.commit()
    return redirect(f"/admin/groups/{group_id}?assessment_id={assessment.id}")


@router.post("/admin/members/{membership_id}/grant")
def grant(
    membership_id: int,
    amount: float = Form(...),
    reason: str = Form(...),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    CoinService(db).admin_grant(admin, membership, amount, reason, idempotency_key)
    return redirect(f"/admin/groups/{membership.group_id}")


@router.post("/admin/members/{membership_id}/revoke")
def revoke(
    membership_id: int,
    amount: float = Form(...),
    reason: str = Form(...),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Участник не найден")
    CoinService(db).admin_revoke(admin, membership, amount, reason, idempotency_key)
    return redirect(f"/admin/groups/{membership.group_id}")


@router.get("/admin/transactions")
def transactions_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    transactions = db.query(CoinTransaction).order_by(CoinTransaction.created_at.desc()).limit(100).all()
    return render(request, "admin/transactions.html", {"user": admin, "transactions": transactions})


@router.get("/admin/settings")
def settings_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return render(
        request,
        "admin/settings.html",
        {
            "user": admin,
            "transfer_policy": SettingsService(db).transfer_policy(),
            "error": None,
            "password_error": None,
            "password_success": request.query_params.get("password_updated") == "1",
        },
    )


@router.post("/admin/settings")
def update_settings(
    request: Request,
    transfer_fee_percent: float = Form(...),
    transfer_max_percent: float = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings_service = SettingsService(db)
    try:
        settings_service.update_transfer_policy(admin, transfer_fee_percent, transfer_max_percent)
    except SettingsServiceError as exc:
        return render(
            request,
            "admin/settings.html",
            {
                "user": admin,
                "transfer_policy": settings_service.transfer_policy(),
                "error": str(exc),
                "password_error": None,
                "password_success": False,
            },
            status_code=400,
        )
    return redirect("/admin/settings")


@router.post("/admin/settings/password")
def update_admin_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings_service = SettingsService(db)

    def render_password_error(message: str):
        return render(
            request,
            "admin/settings.html",
            {
                "user": admin,
                "transfer_policy": settings_service.transfer_policy(),
                "error": None,
                "password_error": message,
                "password_success": False,
            },
            status_code=400,
        )

    if not verify_password(current_password, admin.password_hash):
        return render_password_error("Текущий пароль указан неверно")
    if not new_password:
        return render_password_error("Введите новый пароль")
    if new_password != confirm_password:
        return render_password_error("Пароли не совпадают")

    admin.password_hash = hash_password(new_password)
    db.commit()
    return redirect("/admin/settings?password_updated=1")


@router.get("/admin/redemptions")
def redemptions_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    redemptions = db.query(RewardRedemption).order_by(RewardRedemption.created_at.desc()).limit(100).all()
    return render(request, "admin/redemptions.html", {"user": admin, "redemptions": redemptions})


@router.post("/admin/redemptions/{redemption_id}/fulfill")
def fulfill_redemption(
    redemption_id: int,
    _: str = Depends(validate_csrf),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    redemption = db.get(RewardRedemption, redemption_id)
    if redemption is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    CoinService(db).fulfill_redemption(admin, redemption)
    return redirect("/admin/redemptions")
