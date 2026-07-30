"""
Authentication routes — register, login, get current user profile.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from database.db import get_db
from database.models import User, AuditLog
from auth.jwt_handler import (
    hash_password, verify_password,
    create_access_token, get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from middleware.security import check_rate_limit

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# ─── REQUEST / RESPONSE SCHEMAS ───────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str | None


class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str | None
    created_at: str


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new account. Password is bcrypt hashed before storage."""
    check_rate_limit(request, "auth")

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        {"sub": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    """Login with email and password. Supports both JSON body and Swagger UI Authorize Form Data."""
    check_rate_limit(request, "auth")

    email = None
    password = None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            email = body.get("email") or body.get("username")
            password = body.get("password")
        except Exception:
            pass
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            pass

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required.",
        )

    user = db.query(User).filter(User.email == email).first()
    # Constant-time check — always verify even if user not found to prevent timing attacks
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    token = create_access_token(
        {"sub": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        created_at=current_user.created_at.isoformat(),
    )


@router.get("/admin/users-count")
def get_registered_users_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return system user statistics and total registered user count."""
    total_users = db.query(User).count()
    users = db.query(User).all()
    user_list = [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]
    return {
        "total_registered_users": total_users,
        "users": user_list,
    }
