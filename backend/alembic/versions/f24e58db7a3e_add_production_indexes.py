"""add_production_indexes

Revision ID: f24e58db7a3e
Revises: 2c7657550053
Create Date: 2026-02-20

This migration:
1. Adds critical performance indexes for high-frequency query columns
2. Removes duplicate indexes to reduce disk usage and write overhead

Performance Indexes Added:
- idx_chapters_ai_status: Filter chapters by AI generation status
- idx_homework_status_status: Filter homework by completion status
- idx_users_created_at: Time-based user queries
- idx_test_submissions_created_at: Time-based test result queries
- idx_homework_submissions_created_at: Time-based homework queries

Duplicate Indexes Removed (6):
- ix_chapters_school_name (duplicate of idx_chapters_school)
- ix_homework_school_name (duplicate of idx_homework_school)
- ix_subjects_standard (duplicate of idx_subject_standard)
- ix_subjects_school_name (duplicate of idx_subjects_school)
- ix_tests_school_name (duplicate of idx_tests_school)
- ix_previous_year_papers_school_name (duplicate of idx_pyq_school)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f24e58db7a3e'
down_revision: Union[str, Sequence[str], None] = '2c7657550053'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add production indexes and remove duplicates."""
    
    # ==========================================================================
    # 1️⃣ ADD CRITICAL PERFORMANCE INDEXES
    # ==========================================================================
    
    # AI status filtering (high-frequency queries for content generation status)
    op.create_index(
        'idx_chapters_ai_status',
        'chapters',
        ['ai_status'],
        unique=False
    )
    
    # Homework status filtering
    op.create_index(
        'idx_homework_status_status',
        'student_homework_status',
        ['status'],
        unique=False
    )
    
    # Time-based queries on high-traffic tables
    op.create_index(
        'idx_users_created_at',
        'users',
        ['created_at'],
        unique=False
    )
    
    op.create_index(
        'idx_test_submissions_created_at',
        'test_submissions',
        ['created_at'],
        unique=False
    )
    
    op.create_index(
        'idx_homework_submissions_created_at',
        'homework_submissions',
        ['created_at'],
        unique=False
    )
    
    # ==========================================================================
    # 2️⃣ REMOVE DUPLICATE INDEXES
    # ==========================================================================
    
    # These indexes duplicate existing idx_* indexes on the same columns
    op.drop_index('ix_chapters_school_name', table_name='chapters', if_exists=True)
    op.drop_index('ix_homework_school_name', table_name='homework', if_exists=True)
    op.drop_index('ix_subjects_standard', table_name='subjects', if_exists=True)
    op.drop_index('ix_subjects_school_name', table_name='subjects', if_exists=True)
    op.drop_index('ix_tests_school_name', table_name='tests', if_exists=True)
    op.drop_index('ix_previous_year_papers_school_name', table_name='previous_year_papers', if_exists=True)


def downgrade() -> None:
    """Reverse: Remove new indexes and restore duplicates."""
    
    # Remove performance indexes
    op.drop_index('idx_chapters_ai_status', table_name='chapters', if_exists=True)
    op.drop_index('idx_homework_status_status', table_name='student_homework_status', if_exists=True)
    op.drop_index('idx_users_created_at', table_name='users', if_exists=True)
    op.drop_index('idx_test_submissions_created_at', table_name='test_submissions', if_exists=True)
    op.drop_index('idx_homework_submissions_created_at', table_name='homework_submissions', if_exists=True)
    
    # Restore duplicate indexes (if needed for rollback)
    op.create_index('ix_chapters_school_name', 'chapters', ['school_name'], unique=False)
    op.create_index('ix_homework_school_name', 'homework', ['school_name'], unique=False)
    op.create_index('ix_subjects_standard', 'subjects', ['standard'], unique=False)
    op.create_index('ix_subjects_school_name', 'subjects', ['school_name'], unique=False)
    op.create_index('ix_tests_school_name', 'tests', ['school_name'], unique=False)
    op.create_index('ix_previous_year_papers_school_name', 'previous_year_papers', ['school_name'], unique=False)
