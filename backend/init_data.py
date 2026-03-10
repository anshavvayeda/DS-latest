"""
Initialize test data for development and testing.
Creates:
- 1 Teacher account
- 3 Student accounts with profiles
- Mock OTPs for all accounts
"""

import asyncio
from sqlalchemy import select, delete
from app.models.database import AsyncSessionLocal, Subject, User, StudentProfile, OTPCode, init_db
from datetime import datetime, timezone, timedelta
import uuid

# Default subjects for ALL standards (Class 1-10)
DEFAULT_SUBJECT_NAMES = [
    {"name": "English", "description_template": "NCERT Class {standard} English"},
    {"name": "Hindi", "description_template": "NCERT Class {standard} Hindi"},
    {"name": "Mathematics", "description_template": "NCERT Class {standard} Mathematics"},
    {"name": "Science", "description_template": "NCERT Class {standard} Science"},
    {"name": "Environmental Studies (EVS)", "description_template": "NCERT Class {standard} EVS"},
    {"name": "Computer Science", "description_template": "NCERT Class {standard} Computer Science"},
]

# Test accounts for development
# NOTE: These are TEST ONLY accounts created via seeding, NOT hardcoded in auth logic
TEST_ACCOUNTS = [
    # Teacher
    {
        "user": {
            "email": "teacher@studybuddy.com",
            "phone": "9999900001",
            "role": "teacher",
            "profile_completed": True
        },
        "otp": "222222",
        "profile": None  # Teachers don't have student profiles
    },
    # Student A - Class 5
    {
        "user": {
            "email": "rahul@studybuddy.com",
            "phone": "9999900002",
            "role": "student",
            "profile_completed": True
        },
        "otp": "111111",
        "profile": {
            "name": "Rahul Sharma",
            "roll_no": "STU2024001",
            "school_name": "Delhi Public School, Dwarka",
            "standard": 5,
            "gender": "male",
            "email": "rahul@studybuddy.com",
            "login_phone": "9999900002",
            "parent_phone": "9999900012"
        }
    },
    # Student B - Class 5
    {
        "user": {
            "email": "priya@studybuddy.com",
            "phone": "9999900003",
            "role": "student",
            "profile_completed": True
        },
        "otp": "111112",
        "profile": {
            "name": "Priya Patel",
            "roll_no": "STU2024002",
            "school_name": "Kendriya Vidyalaya, Sector 22",
            "standard": 5,
            "gender": "female",
            "email": "priya@studybuddy.com",
            "login_phone": "9999900003",
            "parent_phone": "9999900013"
        }
    },
    # Student C - Class 10
    {
        "user": {
            "email": "ananya@studybuddy.com",
            "phone": "9999900004",
            "role": "student",
            "profile_completed": True
        },
        "otp": "111113",
        "profile": {
            "name": "Ananya Singh",
            "roll_no": "STU2024003",
            "school_name": "Ryan International School",
            "standard": 10,
            "gender": "female",
            "email": "ananya@studybuddy.com",
            "login_phone": "9999900004",
            "parent_phone": "9999900014"
        }
    }
]

def generate_subjects_for_all_standards():
    """Generate subject entries for all standards (1-10)"""
    subjects = []
    for standard in range(1, 11):
        for order, subject_info in enumerate(DEFAULT_SUBJECT_NAMES, 1):
            subjects.append({
                "name": subject_info["name"],
                "standard": standard,
                "description": subject_info["description_template"].format(standard=standard),
                "order": order,
                "is_default": True
            })
    return subjects


async def init_test_data():
    """Initialize all test data"""
    await init_db()
    
    async with AsyncSessionLocal() as session:
        print("=" * 60)
        print("🚀 INITIALIZING TEST DATA")
        print("=" * 60)
        
        # Clear existing test data
        print("\n1️⃣ Clearing existing test data...")
        await session.execute(delete(OTPCode))
        await session.execute(delete(StudentProfile))
        await session.execute(delete(User))
        await session.commit()
        print("   ✅ Cleared users, profiles, and OTP codes")
        
        # Create test accounts
        print("\n2️⃣ Creating test accounts...")
        
        for account in TEST_ACCOUNTS:
            # Create user
            user = User(
                id=str(uuid.uuid4()),
                **account["user"]
            )
            session.add(user)
            await session.flush()  # Get the user ID
            
            # Create student profile if applicable
            if account["profile"]:
                profile = StudentProfile(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    **account["profile"]
                )
                session.add(profile)
                print(f"   👤 Student: {account['profile']['name']} ({account['user']['email']}) - OTP: {account['otp']}")
            else:
                print(f"   👨‍🏫 Teacher: {account['user']['email']} - OTP: {account['otp']}")
            
            # Create mock OTP for email
            otp_email = OTPCode(
                id=str(uuid.uuid4()),
                identifier=account["user"]["email"],
                code=account["otp"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),  # Valid for 1 year
                verified=False
            )
            session.add(otp_email)
            
            # Create mock OTP for phone
            otp_phone = OTPCode(
                id=str(uuid.uuid4()),
                identifier=account["user"]["phone"],
                code=account["otp"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
                verified=False
            )
            session.add(otp_phone)
        
        await session.commit()
        
        # Check if subjects exist, if not create them
        print("\n3️⃣ Checking subjects...")
        result = await session.execute(select(Subject).where(Subject.is_default == True))
        existing_subjects = result.scalars().all()
        
        if len(existing_subjects) < 50:
            print("   Creating default subjects...")
            # Clear and recreate
            await session.execute(delete(Subject))
            all_subjects = generate_subjects_for_all_standards()
            for subject_data in all_subjects:
                subject = Subject(**subject_data)
                session.add(subject)
            await session.commit()
            print(f"   ✅ Created {len(all_subjects)} subjects (5 × 10 standards)")
        else:
            print(f"   ✅ {len(existing_subjects)} subjects already exist")
        
        print("\n" + "=" * 60)
        print("✅ TEST DATA INITIALIZATION COMPLETE")
        print("=" * 60)
        
        print("\n📋 TEST CREDENTIALS:")
        print("-" * 60)
        print("👨‍🏫 TEACHER:")
        print("   Email: teacher@studybuddy.com")
        print("   Phone: 9999900001")
        print("   OTP: 222222")
        print("")
        print("👤 STUDENTS:")
        print("   1. Rahul Sharma (Class 5) - Student A")
        print("      Email: rahul@studybuddy.com | Phone: 9999900002 | OTP: 111111")
        print("   2. Priya Patel (Class 5) - Student B")
        print("      Email: priya@studybuddy.com | Phone: 9999900003 | OTP: 111112")
        print("   3. Ananya Singh (Class 10) - Student C")
        print("      Email: ananya@studybuddy.com | Phone: 9999900004 | OTP: 111113")
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(init_test_data())
