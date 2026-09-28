import secrets

from fastapi import Form, HTTPException, Request, Response, status

from app.core.config import get_settings


def ensure_csrf_cookie(request: Request, response: Response) -> str:
    settings = get_settings()
    token = request.cookies.get(settings.csrf_cookie) or secrets.token_urlsafe(32)
    response.set_cookie(
        settings.csrf_cookie,
        token,
        httponly=False,
        samesite="lax",
        secure=False,
    )
    return token


def validate_csrf(request: Request, csrf_token: str = Form(...)) -> str:
    expected = request.cookies.get(get_settings().csrf_cookie)
    if not expected or not secrets.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return csrf_token
