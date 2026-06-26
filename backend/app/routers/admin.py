"""Admin endpoints: user management (super-user only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import hash_password, require_superuser
from ..db import get_db
from ..models_db import User
from ..schemas import AdminCreateUserRequest, AdminUpdateUserRequest, UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_superuser)])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(req: AdminCreateUserRequest, db: Session = Depends(get_db)) -> User:
    email = req.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=email,
        display_name=req.display_name or email.split("@")[0],
        password_hash=hash_password(req.password),
        role=req.role,
        is_active=req.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    req: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_superuser),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and req.role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote yourself"
        )
    if user.id == admin.id and req.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself"
        )
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.role is not None:
        user.role = req.role
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.new_password:
        user.password_hash = hash_password(req.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_superuser),
) -> None:
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself"
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(user)
    db.commit()
