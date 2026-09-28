from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.permissions import require_user
from app.db.session import get_db
from app.models.user import User
from app.models.assessment import AssessmentPayment
from app.routers.utils import member_transactions, primary_membership, render
from app.services.assessment_service import AssessmentService
from app.services.settings_service import SettingsService

router = APIRouter()


@router.get("/me")
def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    membership = primary_membership(user)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    balance = membership.account.balance_cached if membership.account else 0
    peers = [
        item
        for item in membership.group.memberships
        if item.id != membership.id and not item.user.username.startswith("__system__") and item.status == "active"
    ]
    assessment_service = AssessmentService(db)
    settings_service = SettingsService(db)
    assessments = assessment_service.assigned_to(membership)
    payment_by_assessment = assessment_service.payment_map_for(membership)
    active_assessment_cards = []
    past_assessment_cards = []
    for assessment in assessments:
        payment = payment_by_assessment.get(assessment.id)
        card = {"assessment": assessment, "payment": payment}
        if payment or assessment.status != "active":
            past_assessment_cards.append(card)
        else:
            active_assessment_cards.append(card)
    return render(
        request,
        "member/dashboard.html",
        {
            "user": user,
            "membership": membership,
            "balance": balance,
            "transfer_limit": settings_service.max_transfer_amount(balance),
            "transfer_policy": settings_service.transfer_policy(),
            "transactions": member_transactions(db, membership, 100),
            "active_assessment_cards": active_assessment_cards,
            "past_assessment_cards": past_assessment_cards,
            "peers": peers,
        },
    )


@router.get("/me/history")
def history(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    membership = primary_membership(user)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    return render(
        request,
        "member/history.html",
        {"user": user, "membership": membership, "transactions": member_transactions(db, membership, 100)},
    )
