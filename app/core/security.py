from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import get_settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="neurocoin-session")


def sign_session(user_id: int) -> str:
    return get_serializer().dumps({"user_id": user_id})


def unsign_session(value: str | None) -> int | None:
    if not value:
        return None
    try:
        payload = get_serializer().loads(value, max_age=get_settings().session_max_age)
    except BadSignature:
        return None
    return int(payload.get("user_id")) if payload.get("user_id") else None
