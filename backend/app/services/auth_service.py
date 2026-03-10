import os
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
import boto3
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import User, OTPCode, get_redis
import logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_EXPIRATION_HOURS = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
OTP_EXPIRATION_MINUTES = int(os.getenv('OTP_EXPIRATION_MINUTES', '5'))
OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', '3'))
MOCK_OTP_MODE = os.getenv('MOCK_OTP_MODE', 'false').lower() == 'true'

ses_client = None
sns_client = None

# Only initialize AWS clients if credentials are properly configured
if not MOCK_OTP_MODE and os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_REGION'):
    try:
        ses_client = boto3.client(
            'ses',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        sns_client = boto3.client(
            'sns',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        logger.info("✅ AWS SES/SNS clients initialized")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize AWS clients: {e}. Falling back to MOCK mode.")
        MOCK_OTP_MODE = True

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

async def send_email_otp(email: str, otp: str) -> bool:
    if MOCK_OTP_MODE:
        logger.info(f"MOCK OTP for {email}: {otp}")
        print(f"\n📧 MOCK EMAIL OTP for {email}: {otp}\n")
        return True
    
    try:
        response = ses_client.send_email(
            Source='noreply@ncertlearning.com',
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': 'Your NCERT Learning OTP'},
                'Body': {
                    'Text': {
                        'Data': f'Your OTP for NCERT Class 5 Smart Learning is: {otp}\n\nThis OTP will expire in {OTP_EXPIRATION_MINUTES} minutes.'
                    }
                }
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error sending email OTP: {e}")
        return False

async def send_sms_otp(phone: str, otp: str) -> bool:
    if MOCK_OTP_MODE:
        logger.info(f"MOCK OTP for {phone}: {otp}")
        print(f"\n📱 MOCK SMS OTP for {phone}: {otp}\n")
        return True
    
    try:
        response = sns_client.publish(
            PhoneNumber=phone,
            Message=f'Your OTP for NCERT Learning is: {otp}. Valid for {OTP_EXPIRATION_MINUTES} minutes.'
        )
        return True
    except Exception as e:
        logger.error(f"Error sending SMS OTP: {e}")
        return False

async def create_otp(db: AsyncSession, identifier: str, identifier_type: str) -> Optional[str]:
    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRATION_MINUTES)
    
    otp_record = OTPCode(
        identifier=identifier,
        code=otp,
        expires_at=expires_at
    )
    db.add(otp_record)
    await db.commit()
    
    try:
        redis = await get_redis()
        if redis:
            redis.setex(f"otp:{identifier}", OTP_EXPIRATION_MINUTES * 60, otp)
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
    
    if identifier_type == 'email':
        success = await send_email_otp(identifier, otp)
    else:
        success = await send_sms_otp(identifier, otp)
    
    return otp if success else None

async def verify_otp(db: AsyncSession, identifier: str, code: str) -> bool:
    # Development mode: Accept test OTPs ONLY if explicitly provided via env vars
    if MOCK_OTP_MODE:
        mock_otp = os.getenv('MOCK_OTP_VALUE', '')
        if mock_otp and code == mock_otp:
            logger.info(f"✅ MOCK_OTP accepted for {identifier}")
            return True
    
    try:
        redis = await get_redis()
        cached_otp = None
        if redis:
            cached_otp = redis.get(f"otp:{identifier}")
        
        if cached_otp and cached_otp == code:
            if redis:
                redis.delete(f"otp:{identifier}")
            
            result = await db.execute(
                select(OTPCode).where(
                    OTPCode.identifier == identifier,
                    OTPCode.code == code,
                    OTPCode.verified == False
                ).order_by(OTPCode.created_at.desc())
            )
            otp_record = result.scalars().first()
            
            if otp_record:
                otp_record.verified = True
                await db.commit()
            
            return True
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
    
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.identifier == identifier,
            OTPCode.code == code,
            OTPCode.verified == False,
            OTPCode.expires_at > datetime.now(timezone.utc)
        ).order_by(OTPCode.created_at.desc())
    )
    otp_record = result.scalars().first()
    
    if not otp_record:
        return False
    
    otp_record.attempts += 1
    
    if otp_record.attempts > OTP_MAX_ATTEMPTS:
        await db.commit()
        return False
    
    if otp_record.code == code:
        otp_record.verified = True
        await db.commit()
        return True
    
    await db.commit()
    return False

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