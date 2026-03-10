"""enforce_foreign_key_on_delete_rules

Revision ID: 89c3b9a136f4
Revises: f24e58db7a3e
Create Date: 2026-02-20

This migration enforces explicit ON DELETE rules for all foreign keys.

Problem:
- 5 FKs had ON DELETE = NO ACTION (PostgreSQL default)
- This prevents deleting teacher accounts if they have created content
- For production, we need explicit rules for data integrity

Solution:
- Teacher-created content (homework, tests, PYQs, quizzes, study_materials)
  uses ON DELETE SET NULL to preserve content if teacher is deleted
- This allows teacher account deactivation without losing educational content

Foreign Keys Modified (5):
---------------------------
| Table               | Column     | Parent | New Rule  | Reason                    |
|---------------------|------------|--------|-----------|---------------------------|
| homework            | created_by | users  | SET NULL  | Preserve homework content |
| tests               | created_by | users  | SET NULL  | Preserve test content     |
| previous_year_papers| created_by | users  | SET NULL  | Preserve PYQ content      |
| quizzes             | created_by | users  | SET NULL  | Preserve quiz content     |
| study_materials     | uploaded_by| users  | SET NULL  | Preserve study materials  |

Existing FKs (23) - Already Correct:
------------------------------------
- CASCADE: Child records deleted with parent (submissions, questions, etc.)
- All student data cascades from student_profiles.roll_no
- All content cascades from subjects -> chapters
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89c3b9a136f4'
down_revision: Union[str, Sequence[str], None] = 'f24e58db7a3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Modify ON DELETE rules for teacher-created content.
    
    Strategy: SET NULL allows teacher deletion while preserving content.
    The created_by/uploaded_by columns must be nullable for SET NULL to work.
    """
    
    # ==========================================================================
    # Make columns nullable FIRST (required for SET NULL)
    # ==========================================================================
    op.alter_column('homework', 'created_by', nullable=True)
    op.alter_column('tests', 'created_by', nullable=True)
    op.alter_column('quizzes', 'created_by', nullable=True)
    op.alter_column('study_materials', 'uploaded_by', nullable=True)
    
    # ==========================================================================
    # homework.created_by -> users.id : NO ACTION -> SET NULL
    # ==========================================================================
    op.drop_constraint('homework_created_by_fkey', 'homework', type_='foreignkey')
    op.create_foreign_key(
        'homework_created_by_fkey',
        'homework',
        'users',
        ['created_by'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # ==========================================================================
    # tests.created_by -> users.id : NO ACTION -> SET NULL
    # ==========================================================================
    op.drop_constraint('tests_created_by_fkey', 'tests', type_='foreignkey')
    op.create_foreign_key(
        'tests_created_by_fkey',
        'tests',
        'users',
        ['created_by'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # ==========================================================================
    # previous_year_papers.created_by -> users.id : NO ACTION -> SET NULL
    # ==========================================================================
    op.drop_constraint('previous_year_papers_created_by_fkey', 'previous_year_papers', type_='foreignkey')
    op.create_foreign_key(
        'previous_year_papers_created_by_fkey',
        'previous_year_papers',
        'users',
        ['created_by'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # ==========================================================================
    # quizzes.created_by -> users.id : NO ACTION -> SET NULL
    # ==========================================================================
    op.drop_constraint('quizzes_created_by_fkey', 'quizzes', type_='foreignkey')
    op.create_foreign_key(
        'quizzes_created_by_fkey',
        'quizzes',
        'users',
        ['created_by'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # ==========================================================================
    # study_materials.uploaded_by -> users.id : NO ACTION -> SET NULL
    # ==========================================================================
    op.drop_constraint('study_materials_uploaded_by_fkey', 'study_materials', type_='foreignkey')
    op.create_foreign_key(
        'study_materials_uploaded_by_fkey',
        'study_materials',
        'users',
        ['uploaded_by'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """
    Revert ON DELETE rules back to NO ACTION (PostgreSQL default).
    """
    
    # homework.created_by
    op.drop_constraint('homework_created_by_fkey', 'homework', type_='foreignkey')
    op.create_foreign_key(
        'homework_created_by_fkey',
        'homework',
        'users',
        ['created_by'],
        ['id'],
        ondelete='NO ACTION'
    )
    
    # tests.created_by
    op.drop_constraint('tests_created_by_fkey', 'tests', type_='foreignkey')
    op.create_foreign_key(
        'tests_created_by_fkey',
        'tests',
        'users',
        ['created_by'],
        ['id'],
        ondelete='NO ACTION'
    )
    
    # previous_year_papers.created_by
    op.drop_constraint('previous_year_papers_created_by_fkey', 'previous_year_papers', type_='foreignkey')
    op.create_foreign_key(
        'previous_year_papers_created_by_fkey',
        'previous_year_papers',
        'users',
        ['created_by'],
        ['id'],
        ondelete='NO ACTION'
    )
    
    # quizzes.created_by
    op.drop_constraint('quizzes_created_by_fkey', 'quizzes', type_='foreignkey')
    op.create_foreign_key(
        'quizzes_created_by_fkey',
        'quizzes',
        'users',
        ['created_by'],
        ['id'],
        ondelete='NO ACTION'
    )
    
    # study_materials.uploaded_by
    op.drop_constraint('study_materials_uploaded_by_fkey', 'study_materials', type_='foreignkey')
    op.create_foreign_key(
        'study_materials_uploaded_by_fkey',
        'study_materials',
        'users',
        ['uploaded_by'],
        ['id'],
        ondelete='NO ACTION'
    )
    
    # Revert columns to NOT NULL
    op.alter_column('homework', 'created_by', nullable=False)
    op.alter_column('tests', 'created_by', nullable=False)
    op.alter_column('quizzes', 'created_by', nullable=False)
    op.alter_column('study_materials', 'uploaded_by', nullable=False)
