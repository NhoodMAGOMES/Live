from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DbSession, get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, UserRole
from app.schemas import LoginRequest, Token, UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: DbSession) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return Token(access_token=create_access_token(user.email, {"role": user.role.value}))


@router.post("/register", response_model=UserRead)
def register(payload: UserCreate, db: DbSession) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=UserRole.VIEWER,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.get("/users", response_model=list[UserRead])
def list_users(db: DbSession, _: Annotated[User, Depends(require_admin)]) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)).all())


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, db: DbSession, _: Annotated[User, Depends(require_admin)]) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, db: DbSession, admin: Annotated[User, Depends(require_admin)]) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes:
        existing = db.scalar(select(User).where(User.email == changes["email"], User.id != user_id))
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
    if changes.get("role") and user.id == admin.id and changes["role"] != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")
    if changes.get("is_active") is False and user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own profile")
    password = changes.pop("password", None)
    if password:
        user.hashed_password = hash_password(password)
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: DbSession, admin: Annotated[User, Depends(require_admin)]) -> dict[str, bool]:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own profile")
    admin_count = db.scalar(select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))) or 0
    if user.role == UserRole.ADMIN and admin_count == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last active admin")
    db.delete(user)
    db.commit()
    return {"ok": True}
