"""
Seed test submissions for Parent Dashboard testing.
Creates test submission records to display in performance charts.
"""

import asyncio
from sqlalchemy import select
from app.models.database import (
    AsyncSessionLocal, init_db, 
    Subject, User, StudentProfile, Test, TestSubmission, StudentPerformance
)
from datetime import datetime, timezone, timedelta
import uuid
import random

async def seed_test_submissions():
    """Create test submissions with varying performance for dashboard testing"""
    await init_db()
    
    async with AsyncSessionLocal() as session:
        print("=" * 60)
        print("🧪 SEEDING TEST SUBMISSIONS FOR DASHBOARD")
        print("=" * 60)
        
        # Get all students
        result = await session.execute(select(StudentProfile))
        students = result.scalars().all()
        
        if not students:
            print("❌ No students found. Run init_data.py first.")
            return
        
        # Get subjects for standard 5 (for Class 5 students)
        result = await session.execute(
            select(Subject).where(Subject.standard == 5)
        )
        subjects_5 = result.scalars().all()
        
        # Get subjects for standard 10 (for Class 10 students)
        result = await session.execute(
            select(Subject).where(Subject.standard == 10)
        )
        subjects_10 = result.scalars().all()
        
        print(f"\n📚 Found {len(subjects_5)} subjects for Class 5")
        print(f"📚 Found {len(subjects_10)} subjects for Class 10")
        
        # Performance profiles for different students
        # Strong student (80-95%), Average student (60-79%), Weak student (40-59%)
        performance_profiles = {
            "9999900002": {"min": 75, "max": 95, "label": "Strong"},      # Rahul - Strong
            "9999900003": {"min": 55, "max": 75, "label": "Average"},     # Priya - Average
            "9999900004": {"min": 40, "max": 65, "label": "Needs Improvement"}  # Ananya - Weak
        }
        
        for student in students:
            profile = performance_profiles.get(student.login_phone, {"min": 50, "max": 80, "label": "Average"})
            subjects = subjects_5 if student.standard == 5 else subjects_10
            
            # Get the user record
            user_result = await session.execute(
                select(User).where(User.id == student.user_id)
            )
            user = user_result.scalars().first()
            
            print(f"\n👤 Creating test data for {student.name} ({profile['label']} performer)")
            
            for subject in subjects[:5]:  # Only first 5 subjects
                # Create 5-8 test submissions over the past 2 months
                num_tests = random.randint(5, 8)
                total_marks = 0
                total_max = 0
                
                for i in range(num_tests):
                    # Create a test record first
                    test_id = str(uuid.uuid4())
                    test_date = datetime.now(timezone.utc) - timedelta(days=random.randint(5, 60))
                    
                    test = Test(
                        id=test_id,
                        subject_id=subject.id,
                        standard=student.standard,
                        title=f"{subject.name} Unit Test {i+1}",
                        file_name=f"test_{i+1}.pdf",
                        file_path=f"tests/{test_id}/test.pdf",
                        submission_deadline=test_date + timedelta(hours=2),
                        expires_at=test_date + timedelta(hours=2, minutes=5),
                        duration_minutes=90,
                        created_by=str(user.id),
                        status='expired',
                        created_at=test_date
                    )
                    session.add(test)
                    
                    # Create submission with performance based on profile
                    max_score = random.choice([50, 75, 100])
                    percentage = random.randint(profile['min'], profile['max'])
                    score = round((percentage / 100) * max_score, 1)
                    
                    total_marks += score
                    total_max += max_score
                    
                    submission = TestSubmission(
                        id=str(uuid.uuid4()),
                        test_id=test_id,
                        test_title=test.title,
                        subject_name=subject.name,
                        standard=student.standard,
                        student_id=student.user_id,
                        roll_no=student.roll_no,
                        started_at=test_date,
                        submitted_at=test_date + timedelta(minutes=random.randint(30, 80)),
                        time_taken_seconds=random.randint(1800, 4800),
                        auto_submitted=False,
                        submitted=True,
                        evaluated=True,
                        total_score=score,
                        max_score=max_score,
                        percentage=percentage,
                        total_questions=random.randint(15, 30),
                        evaluated_at=test_date + timedelta(hours=1),
                        test_upload_date=test_date,
                        created_at=test_date
                    )
                    session.add(submission)
                
                # Create/update student performance record
                avg_percentage = (total_marks / total_max * 100) if total_max > 0 else 0
                
                if avg_percentage >= 80:
                    classification = 'strong'
                elif avg_percentage >= 60:
                    classification = 'average'
                else:
                    classification = 'weak'
                
                # Check if performance record exists
                perf_result = await session.execute(
                    select(StudentPerformance).where(
                        StudentPerformance.student_id == student.user_id,
                        StudentPerformance.subject_id == subject.id
                    )
                )
                existing_perf = perf_result.scalars().first()
                
                if existing_perf:
                    existing_perf.total_tests_taken = num_tests
                    existing_perf.average_percentage = round(avg_percentage, 1)
                    existing_perf.total_marks_scored = total_marks
                    existing_perf.total_max_marks = total_max
                    existing_perf.classification = classification
                    existing_perf.last_test_date = datetime.now(timezone.utc)
                    existing_perf.updated_at = datetime.now(timezone.utc)
                else:
                    performance = StudentPerformance(
                        id=str(uuid.uuid4()),
                        student_id=student.user_id,
                        roll_no=student.roll_no,
                        subject_id=subject.id,
                        subject_name=subject.name,
                        standard=student.standard,
                        total_tests_taken=num_tests,
                        average_percentage=round(avg_percentage, 1),
                        total_marks_scored=total_marks,
                        total_max_marks=total_max,
                        classification=classification,
                        last_test_date=datetime.now(timezone.utc)
                    )
                    session.add(performance)
                
                print(f"   📊 {subject.name}: {num_tests} tests, Avg: {avg_percentage:.1f}% ({classification})")
        
        await session.commit()
        
        print("\n" + "=" * 60)
        print("✅ TEST SUBMISSION DATA SEEDED SUCCESSFULLY")
        print("=" * 60)
        print("\n🎯 Performance Profiles:")
        print("   Rahul (9999900002): Strong performer (75-95%)")
        print("   Priya (9999900003): Average performer (55-75%)")
        print("   Ananya (9999900004): Needs Improvement (40-65%)")

if __name__ == "__main__":
    asyncio.run(seed_test_submissions())
