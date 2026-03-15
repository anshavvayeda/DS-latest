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

### Other Completed Work
- Branding/UI overhaul, bug fixes, CI/CD pipeline, documentation

## Known Issues
- **P0**: Login bug - After admin logout, teacher/student login fails (recurring 2x)
- **P1**: Admin dashboard empty on EC2 (user verification pending)

## Prioritized Backlog

### P0
- Fix critical login bug (recurring)
- Phase 5: Teacher Review Mode (teachers view/override AI grades)

### P1
- Phase 6: Data retention policy (auto-delete detailed reports after 1 month)
- Code refactoring (split monolithic server.py and App.js)

### P2
- Fix minor PDF extraction flaws
- Implement Redis caching
- Add automated testing

## Test Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Student**: roll_no `S001`, password `123456`
