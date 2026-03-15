# StudyBuddy - K-12 Learning Management System

## Original Problem Statement
Set up the StudyBuddy project from GitHub repo, debug CI/CD pipeline, fix known issues, and build AI-based paper evaluation system.

## Tech Stack
- **Backend**: FastAPI + PostgreSQL (AWS RDS)
- **Frontend**: React
- **AI**: OpenRouter API (Claude Sonnet 4.5, Gemini 2.5 Flash, Gemini 2.5 Flash Lite, GPT-4o)
- **Storage**: AWS S3
- **Deployment**: GitHub Actions → EC2 (Nginx + systemd)
- **Auth**: JWT (Cookie + Bearer Token dual system)

## Completed Tasks
- [x] Project setup from GitHub repo
- [x] CI/CD pipeline fix (GitHub Actions → EC2)
- [x] File upload fix (30MB limit via Nginx)
- [x] Authentication flow overhaul (dual Cookie + Bearer)
- [x] Brand logo replacement (atom/math icon, banner, calligraphic tagline)
- [x] Header brand consolidation (single icon)
- [x] Progress bar UI cleanup
- [x] MCQ dict-options rendering fix
- [x] White text on white background fix
- [x] Teacher dropdown name fix
- [x] OpenRouter API key update
- [x] **AI Paper Evaluation System - Phase 1: Backend** (2026-03-15)
  - New DB tables: StructuredTest, StructuredQuestion, StructuredTestSubmission, EvaluationResult
  - Evaluation agent with modular evaluators (deterministic + AI)
  - API endpoints for full CRUD + evaluation + review
  - Verification agent for marks validation
- [x] **AI Paper Evaluation System - Phase 2: Teacher UI** (2026-03-15)
  - StructuredTestCreator component with multi-step form
  - All 8 question types supported
  - Evaluation points and solution steps builders
  - Marks allocation tracker
  - Save draft and publish flow

## In Progress / Pending
- **P0**: Critical login/logout bug (auth state lifecycle)
- **P1**: AI Evaluation Phase 3 — Student results UI with detailed feedback
- **P1**: AI Evaluation Phase 4 — Teacher review mode UI

## Upcoming Tasks
- **P1**: Code refactoring (monolithic server.py and App.js)
- **P2**: Fix PDF extraction flaws
- **P3**: Redis caching, automated testing

## Key Files - Evaluation System
- `/app/backend/app/routes/structured_tests.py` — API routes
- `/app/backend/app/services/evaluation_agent.py` — AI evaluation logic
- `/app/backend/app/models/database.py` — DB models (lines 680-830)
- `/app/frontend/src/components/StructuredTestCreator.jsx` — Teacher UI
- `/app/frontend/src/components/StructuredTestCreator.css` — Styles

## AI Model Routing
- **No AI**: MCQ, True/False, Fill-in-blank, Match-following, totaling
- **Gemini 2.5 Flash Lite** (OpenRouter): One-word semantic comparison
- **GPT-4o** (OpenRouter): Subjective rubric evaluation, numerical steps, feedback generation

## Test Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Teacher**: roll_no `T001`, password `123456`
- **Student**: roll_no `S001`/`S002`, password `123456`
