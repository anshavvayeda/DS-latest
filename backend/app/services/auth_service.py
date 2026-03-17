import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import User
import logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))


async def get_or_create_user(db: AsyncSession, email: Optional[str] = None, phone: Optional[str] = None, role: str = 'student') -> User:
    if email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
    elif phone:
        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalars().first()
    else:
        return None
    
    if not user:
        # Determine role based on email pattern for new users
        if email and ('teacher' in email.lower() or email.lower().startswith('admin')):
            role = 'teacher'
        
        # New user - profile_completed is False by default for students
        user = User(
            email=email, 
            phone=phone, 
            role=role,
            profile_completed=False if role == 'student' else True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user

def create_jwt_token(user_id: str, role: str) -> str:
    payload = {
        'user_id': str(user_id),
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
