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
- Teacher UI with 7 question types
- Student test-taking and results UI with grade cards
- Student performance dashboard with trends

### AI Homework Agent (Complete)
- Pre-generated hints, check-answer without revealing answers

### WhatsApp Parent Chatbot (Complete)
- Sarvam AI agentic architecture with native Indic language support

### Content - Rational Numbers (Recreated - Mar 18, 2026)
- 2 tests (10 questions each) with proper evaluation_points format
- 2 homework assignments (5 questions each) with proper objective_data format
- Test IDs: 4f47c150-425b-4d66-90ee-a7c33bfb8e8e, 9668ca1c-d180-46fa-85e2-56fa60899157
- HW IDs: 62d4c6a9-2f7b-449f-bf36-8429da36b1dc, aed61f3b-d8a1-40c0-8278-434ed30aa44f

## Recently Fixed Bugs

### P0: Test Evaluation TypeError (Fixed - Mar 18, 2026)
- **Bug**: `TypeError: string indices must be integers, not 'str'`
- **Root Cause**: `evaluation_points` stored as plain string instead of list of dicts
- **Fix**: Updated `evaluate_subjective()` to handle string, list-of-dicts, and None formats
- **Data Fix**: Deleted wrongly populated tests/homework, recreated with correct format
- **Verified**: 9/9 backend tests passed

### Admin Login via Main Form (Fixed - Mar 18, 2026)
- Admin can now login via the regular roll_no login form (no need for separate Admin Login link)
- `/api/auth/login` checks admin credentials first, then student profiles

### Subject Progress Bar (Fixed - Mar 18, 2026)
- **Bug**: Student subject card showed 0% even after completing tests/homework
- **Root Cause**: Progress only counted practice quizzes, not structured tests or homework
- **Fix**: Updated to weighted average: quizzes 40%, tests 35%, homework 25%
- Dynamically weights based on what content exists for the subject

## Known Issues
- bcrypt/passlib version mismatch causes `AttributeError` warning (functional but needs password reset after library changes)
- EC2 cookie auth may have issues with `secure=True` on HTTP

## Prioritized Backlog

### P1
- EC2 deployment guidance (SARVAM_API_KEY + latest code pull)
- Fix minor PDF extraction flaws in PYQ feature
- Fix "Login As User" search display bug in AdminDashboard

### P2
- Verify parent phone bug fix on EC2
- Implement Redis caching
- Add automated testing

### P3
- Enhance Teacher Review Mode

## Test Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Student S1 (KV)**: roll_no `S1`, password `Test@123`
- **Teacher T1 (KV)**: roll_no `T1`, password `Test@123`
