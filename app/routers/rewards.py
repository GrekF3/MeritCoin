from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.csrf import validate_csrf
from app.core.permissions import require_user
from app.db.session import get_db
from app.models.reward import RewardCatalog
from app.models.user import User
from app.routers.utils import primary_membership, redirect
from app.services.coin_service import CoinService, CoinServiceError

router = APIRouter()


@router.post("/rewards/{reward_id}/buy")
def buy_reward(
    reward_id: int,
    idempotency_key: str = Form(...),
    _: str = Depends(validate_csrf),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    membership = primary_membership(user)
    reward = db.get(RewardCatalog, reward_id)
    if membership is None or reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Награда не найдена")
    try:
        CoinService(db).buy_reward(user, membership, reward, idempotency_key)
    except CoinServiceError as exc:
        return PlainTextResponse(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
    return redirect("/me")
