from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.csrf import validate_csrf
from app.core.permissions import require_user
from app.db.session import get_db
from app.models.membership import Membership
from app.models.user import User
from app.routers.utils import primary_membership, redirect
from app.services.coin_service import CoinService, CoinServiceError

router = APIRouter()


@router.post("/coins/transfer")
def transfer(
    to_membership_id: int = Form(...),
    amount: float = Form(...),
    reason: str = Form(""),
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    from_membership = primary_membership(user)
    to_membership = db.get(Membership, to_membership_id)
    if from_membership is None or to_membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Участник не найден")
    try:
        CoinService(db).peer_transfer(user, from_membership, to_membership, amount, reason, idempotency_key)
    except CoinServiceError as exc:
        return PlainTextResponse(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
    return redirect("/me")
