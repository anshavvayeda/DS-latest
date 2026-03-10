"""initial_schema

Revision ID: 2c7657550053
Revises: 
Create Date: 2026-02-20 20:59:49.984033

This is the baseline migration representing the existing schema.
All 22 tables were created via SQLAlchemy's create_all() before
Alembic was initialized. This migration documents the schema but
performs no operations since the tables already exist.

Tables:
-------
CORE AUTH:
- users: Base authentication (email/phone, role)
- student_profiles: Extended student data (roll_no as primary identifier)
- otp_codes: OTP verification

CONTENT MANAGEMENT:
- subjects: 5 default subjects per standard (Class 1-10)
- chapters: Chapters within subjects
- contents: Uploaded textbooks (S3 URLs only)
- previous_year_papers: PYQ metadata and S3 URLs
- study_materials: Additional study materials per chapter

HOMEWORK:
- homework: Homework assignments
- homework_questions: Extracted questions from homework
- homework_solutions: AI-generated solutions
- homework_submissions: Student homework submissions

TESTS:
- tests: Test assignments with time constraints
- test_questions: Extracted questions metadata
- test_submissions: Student test submissions

STUDENT DATA:
- student_exam_scores: School exam scores
- student_practice_progress: Chapter-wise practice progress
- student_homework_status: Homework completion tracking
- student_performance: Performance tracking per subject

CACHE:
- quizzes: Teacher-created quizzes
- ai_cache: Generic AI content cache
- ai_content_cache: Cached AI-generated content
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c7657550053'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration - schema already exists.
    
    This migration was created after tables were already in the database.
    No operations are performed. Future migrations will make incremental changes.
    
    Tables documented (22 total):
    - ai_cache
    - ai_content_cache
    - chapters
    - contents
    - homework
    - homework_questions
    - homework_solutions
    - homework_submissions
    - otp_codes
    - previous_year_papers
    - quizzes
    - student_exam_scores
    - student_homework_status
    - student_performance
    - student_practice_progress
    - student_profiles
    - study_materials
    - subjects
    - test_questions
    - test_submissions
    - tests
    - users
    """
    pass


def downgrade() -> None:
    """
    Downgrade not supported for baseline migration.
    
    To completely reset the database, drop all tables manually
    and re-run init_postgres.py.
    """
    pass
