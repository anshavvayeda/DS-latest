# StudyBuddy - K-12 Learning Management System

## Original Problem Statement
Full-stack LMS with AI-powered features for students, teachers, and admins. Includes homework management, test creation, AI evaluation, and multi-language support.

## Core Requirements
- Multi-role auth (admin, teacher, student)
- Subject/chapter management with syllabus tracking
- Homework and test management
- AI-powered paper evaluation system (multi-LLM strategy)
- Multi-language support (English/Gujarati)

## AI Evaluation System - Product Requirements
1. **Teacher UI**: Structured test creation with MCQ, True/False, Fill-blank, One-word, Match-following, Short/Long answer, Numerical question types
2. **Backend**: Store tests and questions as structured JSON, route evaluation to appropriate AI models
3. **AI Evaluation Agent**: GPT-4o for subjective, Gemini Flash Lite for simple semantic, deterministic for objective
4. **Student Results UI**: Per-question feedback with rubric breakdown, grades, scores
5. **Student Performance Dashboard**: Score trends, subject-wise breakdown, question type strengths/weaknesses
6. **Teacher Review Mode**: Override AI grades (upcoming)
7. **Data Retention**: Detailed reports for 1 month, scores for academic year (upcoming)

## Architecture
- **Backend**: FastAPI + PostgreSQL + SQLAlchemy
- **Frontend**: React
- **AI**: OpenRouter (GPT-4o, Gemini Flash Lite)
- **Storage**: AWS S3
- **CI/CD**: GitHub Actions → EC2

## What's Been Implemented

### Phase 1 - Backend (Complete)
- Database models: StructuredTest, StructuredQuestion, StructuredTestSubmission, EvaluationResult
- AI evaluation service with multi-LLM orchestration
- Full CRUD API endpoints for structured tests

### Phase 2 - Teacher UI (Complete)
- StructuredTestCreator component with multi-step form
- 7 question types with marking schemes/rubrics
- Subject shown as read-only field (auto-populated from parent view)

### Phase 3 - Student Results UI (Complete - Mar 15, 2026)
- StudentAITest component for test-taking and results viewing
- Test-taking: Timer, question navigation, all input types
- Results: Grade card (A+/A/B/C/D/F), score/percentage, improvement notes
- Per-question expandable breakdown with rubric feedback
- Parallel data fetching via Promise.allSettled

### Phase 4 - Student Performance Dashboard (Complete - Mar 15, 2026)
- Backend API: GET /api/structured-tests/student/performance
- Summary cards: total tests, average %, best %, recent trend
- Subject-wise performance with progress bars
- Question type strengths/weaknesses analysis (green/yellow/red indicators)
- Recent tests timeline with grade badges
- Score trend chart (bar + line overlay, appears with 2+ tests)

### Old Test System Removed (Complete - Mar 16, 2026)
- Removed ~1800 lines of old test code (PDF upload, S3 JSON, single-prompt LLM evaluation)
- Deleted: old test routes (POST /tests, GET /tests/subject/*, etc.), TestTaking.jsx/css, cleanup_expired_tests_task
- Kept: PYQ (study resources), Homework (TestManagement with contentType=homework), all Structured* (new AI system)
- Parent dashboard updated to only query StructuredTestSubmission
- Verified: 13/13 backend tests + full frontend UI verification passed

### Data Retention Policy (Complete - Mar 16, 2026)
- EvaluationResult TTL: 2 months (changed from 1 month)
- Background cron job runs every 6 hours to clean up expired detailed evaluation records
- Before deletion: condenses per-question improvement suggestions into brief 1-2 sentence summary
- Retained permanently: total_score, max_score, percentage, class_rank, improvement_summary
- Deleted after 2 months: detailed EvaluationResult rows, raw answers_json
- Manual admin cleanup: DELETE /api/structured-tests/cleanup/expired
- Frontend gracefully shows "archived per 2-month retention policy" when details expire

### Student Greeting (Complete - Mar 16, 2026)
- Added cursive greeting "Hi <name>, Which subject do you want to study today?" using Dancing Script font with gradient colors
- Appears above the subjects grid only for students (not in teacher preview mode)

### Teacher Review Mode (Complete - Mar 16, 2026)
- Teachers can click "Review Submissions" on any AI-evaluated test to see all student submissions
- Detailed view shows each question with student answer, AI feedback, and marks
- Teachers can override AI marks per question and add comments
- Save Review persists changes and recalculates final score
- Backend endpoint POST /api/structured-tests/{test_id}/review/{student_id} handles overrides

### Parent Dashboard AI Sync (Complete - Mar 16, 2026)
- Backend endpoint `/api/student/parent-dashboard` updated to query StructuredTestSubmission + StructuredTest
- AI-evaluated test scores now appear in subject-wise performance cards with graphs
- Overall stats (tests taken, avg score) include combined data from old and AI test systems
- Subject classification (strong/average/weak) based on all test data
- Replaced SVG-based chart with pure HTML/CSS bar chart for reliable rendering

### Backend Refactoring (Complete - Mar 16, 2026)
- Monolithic `server.py` (~5950 lines) split into modular architecture:
  - `server.py` (165 lines): App setup, CORS, lifecycle, router registration
  - `app/deps.py` (87 lines): Shared auth dependencies (get_current_user, password hashing, config)
  - `app/schemas/__init__.py` (137 lines): All Pydantic request/response models
  - `app/routes/auth.py` (1090 lines): Auth, login, admin CRUD
  - `app/routes/content.py` (2108 lines): Subjects, chapters, PYQs, student content
  - `app/routes/homework.py` (1036 lines): Homework CRUD, evaluation
  - `app/routes/parent_teacher.py` (1274 lines): Parent dashboard, teacher analytics, study materials
  - `app/routes/structured_tests.py` (904 lines): AI test creation, submission, evaluation
- All 21 backend + frontend tests passed (100% success rate)

### Other Completed Work
- Branding/UI overhaul, bug fixes, CI/CD pipeline, documentation

## Known Issues
- **P1**: Admin dashboard empty on EC2 (user verification pending)

## Recently Fixed Bugs (Mar 16, 2026)
- **CRITICAL Login Bug (P0, Recurring) — FIXED**: After admin logout, student/teacher login was broken. Three root causes: 1) `delete_cookie` didn't match `set_cookie` attributes (samesite/secure/httponly) so cookie was never deleted, 2) Server prioritized stale cookie over fresh Authorization header, 3) Frontend didn't clear stale cookies before new login. All three fixed and verified with 11/11 backend + frontend tests passing.
- **Parent Dashboard graphs not rendering**: Replaced SVG chart with pure HTML/CSS bar chart
- **Parent Dashboard not showing AI test scores**: Updated backend to query StructuredTestSubmission
- **Save Draft was not saving questions before Publish**: `handlePublish` now always calls `handleSave()` first
- **Parallel data fetching**: Replaced sequential awaits with `Promise.allSettled` to prevent UI hang

## Prioritized Backlog

### P0
- Frontend refactoring: Split monolithic App.js (~4600 lines) into modular components

### P1
- Fix minor PDF extraction flaws in PYQ feature

### P2
- Implement Redis caching
- Add automated testing

## Test Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Student**: roll_no `S001`, password `123456`
