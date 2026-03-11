#!/usr/bin/env python3
"""
Initialize EC2 Database with Admin User
Run this on EC2 to create the default admin account
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, '/home/ubuntu/studybuddy/backend')

from app.models.database import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def init_admin():
    """Create admin user if doesn't exist"""
    load_dotenv()
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in .env")
        return
    
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if admin exists
        result = await session.execute(
            select(User).where(User.role == 'admin')
        )
        existing_admin = result.scalars().first()
        
        if existing_admin:
            print(f"✅ Admin user already exists: {existing_admin.phone}")
            print(f"   Username: admin")
            print(f"   You can reset password if needed")
            return
        
        # Create admin user
        import uuid
        admin_id = str(uuid.uuid4())
        
        admin_user = User(
            id=admin_id,
            phone="admin",  # Username for admin
            email="admin@studybuddy.com",
            password_hash=pwd_context.hash("Admin@123"),
            role="admin",
            is_active=True,
            profile_completed=True
        )
        
        session.add(admin_user)
        await session.commit()
        
        print("✅ Admin user created successfully!")
        print("")
        print("Login credentials:")
        print("  Username: admin")
        print("  Password: Admin@123")
        print("")
        print("Please change the password after first login!")

if __name__ == "__main__":
    asyncio.run(init_admin())
