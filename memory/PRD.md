# StudyBuddy - K-12 Learning Management System

## Original Problem Statement
Full-stack LMS with AI-powered features for students, teachers, and admins. Includes homework management, test creation, AI evaluation, and multi-language support.

## Core Requirements
- Multi-role auth (admin, teacher, student)
- Subject/chapter management with syllabus tracking
- Homework and test management
- AI-powered paper evaluation system (multi-LLM strategy)
- Multi-language support (English/Gujarati)

## Architecture
- **Backend**: FastAPI + PostgreSQL + SQLAlchemy (modular routes)
- **Frontend**: React (modular components)
- **AI**: OpenRouter (GPT-4o, Gemini Flash Lite), Sarvam AI (chatbot)
- **Storage**: AWS S3

## What's Been Implemented

### Phase 1-4 - Core LMS (Complete)
- Database models, AI evaluation service, structured test CRUD
- Teacher UI with 7 question types, Student test-taking and results UI
- Student performance dashboard with trends

### AI Homework Agent (Complete)
### WhatsApp Parent Chatbot (Complete) - Sarvam AI

### Content - Rational Numbers (Recreated - Mar 18, 2026)
- 2 tests (10 Qs each) + 2 homework (5 Qs each) with correct format
- Test IDs: 4f47c150, 9668ca1c | HW IDs: 62d4c6a9, aed61f3b

## Recently Fixed Bugs

### P0: Test Evaluation TypeError (Fixed - Mar 18)
- Fixed `evaluation_points` string format handling in `evaluate_subjective()`
- Deleted wrongly populated data, recreated correctly

### Admin Login via Main Form (Fixed - Mar 18)
- `/api/auth/login` now accepts admin credentials directly

### Subject Progress Bar (Fixed - Mar 18)
- Now includes practice quizzes (40%) + tests (35%) + homework (25%)

### Cookie Auth on HTTP (Fixed - Mar 18)
- **Root Cause**: Cookies set with `secure=True` were never sent over HTTP (EC2)
- **Fix**: Added `COOKIE_SECURE` env var. Set to `false` for HTTP deployments
- **Impact**: Fixed login, upload, and all auth issues on EC2
- All `set_cookie` calls now use adaptive `_set_auth_cookie()` helper

## EC2 Deployment Instructions
After `git pull`:
1. Add to `backend/.env`: `COOKIE_SECURE=false`
2. Add to `backend/.env`: `SARVAM_API_KEY=<your_key>`
3. Configure nginx: `client_max_body_size 50M;` in server block
4. Reset passwords: run the password reset script
5. Restart: `sudo systemctl restart studybuddy-backend`

## Prioritized Backlog
### P1
- Fix minor PDF extraction flaws in PYQ feature
- Fix "Login As User" search display bug in AdminDashboard
### P2
- Implement Redis caching
- Add automated testing
### P3
- Enhance Teacher Review Mode

## Test Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Student S1 (KV)**: roll_no `S1`, password `Test@123`
- **Teacher T1 (KV)**: roll_no `T1`, password `Test@123`
