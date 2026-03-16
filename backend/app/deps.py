"""Shared dependencies for all route modules."""
from fastapi import Depends, HTTPException, Cookie, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from passlib.context import CryptContext
import os
import logging

from app.models.database import get_db, User, StudentProfile
from app.services.auth_service import decode_jwt_token

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Global OTP store (in production, use Redis with TTL)
OTP_STORE = {}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def get_current_user(
    token: Optional[str] = Cookie(None, alias="auth_token"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.replace("Bearer ", "")
    if not auth_token and token:
        auth_token = token
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_jwt_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == payload['user_id']))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_optional_user(
    token: Optional[str] = Cookie(None, alias="auth_token"),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    payload = decode_jwt_token(token)
    if not payload:
        return None
    result = await db.execute(select(User).where(User.id == payload['user_id']))
    return result.scalars().first()


async def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != 'teacher':
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_user_school(user: User, db: AsyncSession) -> Optional[str]:
    if user.role == 'admin':
        return None
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == str(user.id))
    )
    profile = result.scalars().first()
    return profile.school_name if profile else None
