from __future__ import annotations

import uuid
import secrets

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.coin import CoinAccount, CoinTransaction, LedgerEntry
from app.models.membership import Membership
from app.models.user import User
from app.utils.money import format_neuro, format_signed_neuro

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["new_key"] = lambda: str(uuid.uuid4())
templates.env.filters["neuro"] = format_neuro
templates.env.filters["signed_neuro"] = format_signed_neuro


def render(request: Request, template: str, context: dict, status_code: int = 200) -> HTMLResponse:
    settings = get_settings()
    csrf_token = request.cookies.get(settings.csrf_cookie) or secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request,
        template,
        {**context, "csrf_token": csrf_token, "idempotency_key": str(uuid.uuid4())},
        status_code=status_code,
    )
    response.set_cookie(settings.csrf_cookie, csrf_token, httponly=False, samesite="lax", secure=False)
    return response


def redirect(location: str) -> RedirectResponse:
    return RedirectResponse(location, status_code=303)


def primary_membership(user: User) -> Membership | None:
    active = [membership for membership in user.memberships if membership.status == "active"]
    return active[0] if active else (user.memberships[0] if user.memberships else None)


def member_transactions(db: Session, membership: Membership, limit: int = 50) -> list[dict[str, object]]:
    account = membership.account
    if account is None:
        return []
    entries = (
        db.query(LedgerEntry)
        .join(CoinTransaction)
        .filter(LedgerEntry.account_id == account.id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"entry": entry, "tx": entry.transaction} for entry in entries]
