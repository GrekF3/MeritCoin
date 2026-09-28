from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.csrf import validate_csrf
from app.core.permissions import require_user
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.user import User
from app.routers.utils import primary_membership, redirect
from app.services.coin_service import CoinService, CoinServiceError

router = APIRouter()


@router.post("/assessments/{assessment_id}/pay")
def pay_assessment(
    assessment_id: int,
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    membership = primary_membership(user)
    assessment = db.get(Assessment, assessment_id)
    if membership is None or assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зачет не найден")
    try:
        CoinService(db).buy_assessment(user, membership, assessment, idempotency_key)
    except CoinServiceError as exc:
        return PlainTextResponse(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
    return redirect("/me")
