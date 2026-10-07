from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User


bearer = HTTPBearer(auto_error=False)


def _require_jwt_secret() -> str:
    if not settings.jwt_secret_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication is not configured. Copy .env.example to .env in the project root "
                "or backend folder and set JWT_SECRET_KEY to a long random secret."
            ),
        )
    return settings.jwt_secret_key


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        _require_jwt_secret(),
        algorithm="HS256",
    )


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    database: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, _require_jwt_secret(), algorithms=["HS256"])
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError, RuntimeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in to continue.")
    user = database.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Please log in again.")
    return user


def require_user(user: User | None = Depends(get_optional_user)) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in to continue.")
    return user


def ensure_learner_access(learner, user: User | None) -> None:
    if learner.user_id is not None and (not user or learner.user_id != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This learner profile is not available to your account.")