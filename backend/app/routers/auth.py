from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from ..security import create_access_token, hash_password, require_user, verify_password


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, database: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower().strip()
    if database.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    user = User(email=email, password_hash=hash_password(payload.password))
    database.add(user)
    database.commit()
    database.refresh(user)
    return AuthResponse(access_token=create_access_token(user.id), user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, database: Session = Depends(get_db)) -> AuthResponse:
    user = database.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return AuthResponse(access_token=create_access_token(user.id), user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(require_user)) -> UserResponse:
    return UserResponse.model_validate(user)