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
- **Backend**: FastAPI + PostgreSQL + SQLAlchemy (modular routes)
- **Frontend**: React (modular components)
- **AI**: OpenRouter (GPT-4o, Gemini Flash Lite)
- **Storage**: AWS S3
- **CI/CD**: GitHub Actions -> EC2

### Backend Structure (Refactored Mar 16, 2026)
```
/app/backend/
├── server.py              (165 lines - App setup, CORS, lifecycle)
├── app/
│   ├── deps.py            (87 lines - Shared auth, config)
│   ├── schemas/__init__.py (137 lines - Pydantic models)
│   ├── routes/
│   │   ├── auth.py         (1090 lines - Auth, admin CRUD)
│   │   ├── content.py      (2108 lines - Subjects, chapters, PYQs)
│   │   ├── structured_homework.py (570 lines - AI homework CRUD)
│   │   ├── parent_teacher.py (1274 lines - Parent/teacher dashboards)
│   │   ├── structured_tests.py (912 lines - AI test lifecycle)
│   │   └── whatsapp.py     (WhatsApp webhook)
│   ├── models/database.py  (DB models, engine)
│   └── services/
│       ├── evaluation_agent.py (AI evaluation orchestrator)
│       └── whatsapp_agent.py   (Sarvam AI chatbot)
```

## What's Been Implemented

### Phase 1-4 - Core LMS (Complete)
- Database models, AI evaluation service, structured test CRUD
- Teacher UI with 7 question types
- Student test-taking and results UI with grade cards
- Student performance dashboard with trends

### AI Homework Agent (Complete - Mar 16, 2026)
- Pre-generated hints, check-answer without revealing answers
- No marks/grading, only completion tracking

### WhatsApp Parent Chatbot (Complete - Mar 18, 2026)
- Sarvam AI agentic architecture with native Indic language support
- Hindi (Devanagari), Gujarati (Gujarati script), English

### Content Creation - Rational Numbers (Recreated - Mar 18, 2026)
- Chapter "Rational Numbers" (Math, Std 8, KV) with AI-generated content
- 2 tests (10 questions each) with proper evaluation_points format
- 2 homework assignments (5 questions each) with proper objective_data format
- Test IDs: 4f47c150-425b-4d66-90ee-a7c33bfb8e8e, 9668ca1c-d180-46fa-85e2-56fa60899157
- Homework IDs: 62d4c6a9-2f7b-449f-bf36-8429da36b1dc, aed61f3b-d8a1-40c0-8278-434ed30aa44f

## Recently Fixed Bugs

### P0 Bug Fix: Test Evaluation TypeError (Fixed - Mar 18, 2026)
- **Bug**: `TypeError: string indices must be integers, not 'str'` when evaluating tests
- **Root Cause**: `evaluation_points` for short_answer questions was stored as a plain comma-separated string instead of a list of dicts with `{id, title, expected_concept, marks}` structure
- **Fix**: Updated `evaluation_agent.py evaluate_subjective()` to handle 3 formats:
  1. Proper list of dicts (correct format)
  2. Comma-separated string (auto-converts to list of dicts with equal marks)
  3. None (falls back to model_answer comparison)
- **Data Fix**: Deleted all wrongly populated tests/homework and recreated with correct format
- **Verified**: 9/9 backend tests passed, Test 1: 16.5/18 (91.67%), Test 2: 18/20 (90%)

## Known Issues
- **P2**: Admin dashboard empty on EC2 (uses separate unseeded database)
- **P2**: bcrypt/passlib version mismatch warning (functional but logs errors)

## Prioritized Backlog

### P1
- EC2 deployment guidance (SARVAM_API_KEY setup via demo_setup.sh)
- Fix minor PDF extraction flaws in PYQ feature
- Fix pre-existing "Login As User" search display bug in AdminDashboard

### P2
- Verify parent phone bug fix on EC2 (user verification pending)
- Implement Redis caching
- Add automated testing

### P3
- Enhance Teacher Review Mode

## Test Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Student S1 (KV)**: roll_no `S1`, password `Test@123`
- **Teacher T1 (KV)**: roll_no `T1`, password `Test@123`

## Key IDs
- Subject (Math, Std 8): 9e05f51f-7235-4cd1-8539-71aa7d962ea1
- Chapter (Rational Numbers): a391a21d-f7e4-4ddb-be1f-15b0de1bd1f5
