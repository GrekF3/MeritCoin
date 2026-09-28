from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.csrf import validate_csrf
from app.core.security import sign_session
from app.db.session import get_db
from app.models.user import UserRole
from app.routers.utils import redirect, render
from app.services.auth_service import AuthService, AuthServiceError
from app.services.group_service import GroupService

router = APIRouter()


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "auth/login.html", {"error": None})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    _: str = Depends(validate_csrf),
    db: Session = Depends(get_db),
):
    user = AuthService(db).authenticate(username, password)
    if user is None:
        return render(request, "auth/login.html", {"error": "Неверный логин или пароль"}, status_code=401)
    response = redirect("/admin" if user.role == UserRole.ADMIN else "/me")
    response.set_cookie(
        get_settings().session_cookie,
        sign_session(user.id),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=get_settings().session_max_age,
    )
    return response


@router.get("/register")
def register_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "auth/register.html", {"groups": GroupService(db).active_groups(), "error": None})


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    group_id: int = Form(...),
    _: str = Depends(validate_csrf),
    db: Session = Depends(get_db),
):
    try:
        AuthService(db).register_member(username, password, display_name, group_id)
    except AuthServiceError as exc:
        return render(
            request,
            "auth/register.html",
            {"groups": GroupService(db).active_groups(), "error": str(exc)},
            status_code=400,
        )
    return redirect("/login")


@router.post("/logout")
def logout(_: str = Depends(validate_csrf)):
    response = redirect("/login")
    response.delete_cookie(get_settings().session_cookie)
    return response
