# StudyBuddy Project Handover Document
## Complete Context for New Session Setup

**Document Version:** 3.0  
**Last Updated:** March 15, 2026  
**Project:** StudyBuddy K-12 Learning Management System  
**GitHub Repository:** https://github.com/anshavvayeda/DS-latest  
**Current Status:** Development Active | CI/CD Working | AI Evaluation System Phase 3 Complete

---

# TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Current Project State](#2-current-project-state)
3. [AI Evaluation System](#3-ai-evaluation-system)
4. [Complete Setup Instructions](#4-complete-setup-instructions)
5. [Environment Configuration](#5-environment-configuration)
6. [Key Files & Their Purpose](#6-key-files--their-purpose)
7. [Important Commands](#7-important-commands)
8. [What's Working](#8-whats-working)
9. [Known Issues](#9-known-issues)
10. [Pending Tasks](#10-pending-tasks)
11. [Technical Architecture](#11-technical-architecture)
12. [Troubleshooting Guide](#12-troubleshooting-guide)
13. [Important Context](#13-important-context)
14. [Change Log](#14-change-log)

---

# 1. PROJECT OVERVIEW

## What is StudyBuddy?

StudyBuddy is a comprehensive K-12 Learning Management System (LMS) designed for Indian schools with AI-powered features.

### Core Functionality:
- **Multi-role system**: Admin, Teacher, Student, Parent, Maintenance
- **AI Content Generation**: Automatic creation of revision notes, flashcards, and practice quizzes from textbook PDFs
- **AI Paper Evaluation**: Multi-LLM evaluation system for structured tests with per-question feedback
- **Assessment System**: Homework management, timed tests, previous year papers
- **Performance Tracking**: Student performance dashboard with score trends across AI-evaluated tests
- **Multi-tenancy**: School-based data isolation

### Technology Stack:

**Backend:**
- Framework: FastAPI (Python)
- Database: PostgreSQL (AWS RDS)
- Storage: AWS S3
- AI: OpenRouter API (GPT-4o for subjective evaluation, Gemini Flash Lite for semantic tasks)
- Authentication: JWT-based (Dual: Cookie + Bearer Token)

**Frontend:**
- Framework: React 19
- Styling: TailwindCSS + Custom CSS
- State Management: React Hooks
- HTTP Client: Axios (with Bearer token interceptor)

**Infrastructure:**
- Development: Emergent Agent Environment (Kubernetes)
- Production: AWS EC2 (Ubuntu 24.04)
- Web Server: Nginx (configured for 30MB uploads)
- Process Manager: Systemd (EC2) / Supervisor (Emergent)
- CI/CD: GitHub Actions (deploy-to-ec2.yml)

---

# 2. CURRENT PROJECT STATE

## Completed Work (as of March 15, 2026):

### AI Evaluation System (Phases 1-3 COMPLETE):

**Phase 1 - Backend (COMPLETE):**
- Database models: StructuredTest, StructuredQuestion, StructuredTestSubmission, EvaluationResult
- AI evaluation service (`evaluation_agent.py`) with multi-LLM orchestration
- 7 question types: MCQ, True/False, Fill-blank, One-word, Match-following, Short/Long answer, Numerical
- Full CRUD API endpoints in `structured_tests.py`

**Phase 2 - Teacher UI (COMPLETE):**
- `StructuredTestCreator.jsx` with multi-step form for creating tests
- Subject auto-populated from parent view (read-only field)
- Detailed marking schemes and rubrics per question

**Phase 3 - Student Results UI (COMPLETE):**
- `StudentAITest.jsx` component for test-taking and results viewing
- Test-taking: Timer, question navigation dots, all input types (MCQ radio, TF, text, textarea, match pairs)
- Results: Grade card (A+/A/B/C/D/F), score/percentage, improvement notes
- Per-question expandable breakdown with rubric points (covered/missed), feedback, correct answers
- Parallel data fetching via Promise.allSettled for faster subject loading

**Phase 4 - Student Performance Dashboard (COMPLETE):**
- Backend API: `/api/structured-tests/student/performance` with score trends, subject breakdown, question type analysis
- Frontend: `StudentPerformanceDashboard.jsx` with score trend chart, subject-wise stats, question type strengths/weaknesses
- Integrated into student subject view

### Core LMS Features (COMPLETE):
- 7,245+ lines of FastAPI code (server.py)
- Complete API endpoints for all user roles
- AI content generation system (background processing)
- Homework and test management with PDF extraction
- Analytics and reporting
- 4,500+ lines of React code (App.js)
- 15+ component files
- Complete UI for all user roles

### CI/CD Pipeline (COMPLETE):
- GitHub Actions workflow fully operational
- Automatic deployment to EC2 on push to main

### Branding & UI (COMPLETE):
- Custom StudyBuddy logos and branding
- Calligraphic tagline with Dancing Script font
- Dark theme with galaxy background

### Bug Fixes:
- MCQ dict-format options rendering
- White text on white backgrounds
- Teacher profile dropdown
- Parallelized subject data loading (was sequential, causing UI hang)
- Fixed double `/api` prefix in AI test API URLs

---

# 3. AI EVALUATION SYSTEM

## Architecture:
```
Teacher → Create Test (StructuredTestCreator) → Publish
Student → View Tests → Attempt Test (StudentAITest) → Submit
AI Agent → Evaluate (GPT-4o / Gemini Flash Lite / Deterministic)
Student → View Results (score card, per-question feedback)
Student → Performance Dashboard (trends, strengths/weaknesses)
Teacher → Review & Override (Phase 5 - upcoming)
```

## Question Types & Evaluation Strategy:
| Type | Evaluator | Method |
|------|-----------|--------|
| MCQ | Deterministic | Exact match |
| True/False | Deterministic | Exact match |
| Fill-blank | Deterministic | Exact match |
| One-word | Gemini Flash Lite | Semantic match |
| Match-following | Deterministic | Pair comparison |
| Short/Long Answer | GPT-4o | Rubric-based evaluation |
| Numerical | GPT-4o | Step-by-step verification |

## Key API Endpoints:
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/structured-tests` | Create draft test |
| POST | `/api/structured-tests/{id}/questions` | Add questions |
| POST | `/api/structured-tests/{id}/publish` | Publish test |
| GET | `/api/structured-tests/list/{subject_id}/{standard}` | List tests for students |
| GET | `/api/structured-tests/{id}` | Get test with questions |
| POST | `/api/structured-tests/{id}/start` | Start test attempt |
| POST | `/api/structured-tests/{id}/submit` | Submit & evaluate |
| GET | `/api/structured-tests/{id}/results/{student_id}` | Detailed results |
| GET | `/api/structured-tests/student/performance` | Performance dashboard data |
| POST | `/api/structured-tests/teacher/review/{submission_id}` | Teacher review |

## Database Models:
- `structured_tests` - Test metadata (title, marks, duration, deadline)
- `structured_questions` - Questions with evaluation criteria (rubric points, solution steps)
- `structured_test_submissions` - Student submissions with scores (permanent)
- `evaluation_results` - Detailed per-question feedback (TTL: 1 month)

---

# 4. COMPLETE SETUP INSTRUCTIONS

## Prerequisites:
- Access to GitHub repository: https://github.com/anshavvayeda/DS-latest
- Emergent Agent environment (Kubernetes) or local machine with Python 3.8+ and Node.js 20+

## Step-by-Step Setup:

### Step 1: Clone Repository
```bash
cd /app
rm -rf backend frontend .github scripts *.md
git clone https://github.com/anshavvayeda/DS-latest.git temp_clone
mv temp_clone/* temp_clone/.* /app/ 2>/dev/null || true
rm -rf temp_clone
```

### Step 2: Create Backend .env
```bash
cat > /app/backend/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@HOST:5432/postgres
MOCK_OTP_MODE=true
MOCK_OTP_VALUE=123456
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
OPENROUTER_API_KEY=your-openrouter-key-here
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=ap-south-1
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@123
ENV=production
EOF
```

### Step 3: Create Frontend .env
```bash
cat > /app/frontend/.env << 'EOF'
REACT_APP_BACKEND_URL=https://your-preview-url.emergentagent.com
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
EOF
```

### Step 4: Install Dependencies
```bash
cd /app/backend && pip install -q -r requirements.txt
cd /app/frontend && yarn install
```

### Step 5: Start & Verify
```bash
sudo supervisorctl restart all
sleep 5
sudo supervisorctl status
curl $(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)/api/
```

### Step 6: Create Test Data
```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
TOKEN=$(curl -s -X POST "$API_URL/api/admin/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"Admin@123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Register teacher
curl -s -X POST "$API_URL/api/admin/register-student" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"name":"Test Teacher","phone":"8888888888","password":"123456","role":"teacher","school_name":"Test School","roll_no":"T001"}'

# Register student
curl -s -X POST "$API_URL/api/admin/register-student" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"name":"Test Student","phone":"9999999999","password":"123456","role":"student","standard":5,"school_name":"Test School","roll_no":"S001"}'
```

---

# 5. KEY FILES & THEIR PURPOSE

## Repository Structure:
```
/app/
├── backend/
│   ├── server.py                         # Main FastAPI app (7,245+ lines)
│   ├── requirements.txt
│   ├── .env
│   ├── init_ec2_admin.py
│   └── app/
│       ├── models/
│       │   └── database.py               # SQLAlchemy models (incl. StructuredTest models)
│       ├── routes/
│       │   └── structured_tests.py       # AI evaluation API endpoints
│       └── services/
│           ├── evaluation_agent.py       # AI evaluation orchestrator
│           ├── ai_service.py             # AI content generation
│           ├── ai_orchestrator_v2.py     # Background AI tasks
│           ├── gpt4o_extraction.py       # PDF extraction
│           ├── storage_service.py        # S3 operations
│           └── auth_service.py           # JWT & authentication
├── frontend/
│   ├── src/
│   │   ├── App.js                        # Main React app (4,700+ lines)
│   │   ├── App.css                       # Global styles
│   │   └── components/
│   │       ├── StudentAITest.jsx         # Student test-taking & results
│   │       ├── StudentAITest.css
│   │       ├── StudentPerformanceDashboard.jsx  # Performance trends
│   │       ├── StudentPerformanceDashboard.css
│   │       ├── StructuredTestCreator.jsx # Teacher test creation
│   │       ├── StructuredTestCreator.css
│   │       ├── TeacherUpload.jsx
│   │       ├── TeacherAnalytics.jsx
│   │       ├── StudentContentViewer.jsx
│   │       ├── HomeworkAnswering.jsx
│   │       ├── TestManagement.jsx
│   │       ├── QuestionRenderer.jsx
│   │       ├── AdminDashboard.jsx
│   │       └── ...
│   └── public/
│       ├── studybuddy-icon.png
│       └── studybuddy-banner.png
├── memory/
│   └── PRD.md
└── STUDYBUDDY_HANDOVER.md
```

---

# 6. IMPORTANT COMMANDS

## Service Management:
```bash
sudo supervisorctl restart all
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
sudo supervisorctl status
```

## Logs:
```bash
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/frontend.out.log
```

## API Testing:
```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Admin login
curl -s -X POST "$API_URL/api/admin/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"Admin@123"}'

# Student login
curl -s -X POST "$API_URL/api/auth/login" -H "Content-Type: application/json" -d '{"roll_no":"S001","password":"123456"}'
```

## Dependencies:
```bash
# Backend
pip install package-name && pip freeze > /app/backend/requirements.txt

# Frontend (ALWAYS yarn, NEVER npm)
cd /app/frontend && yarn add package-name
```

---

# 7. WHAT'S WORKING

- Admin login, user management, analytics
- Teacher PDF upload, AI content generation, homework/test management
- Teacher AI-evaluated test creation (structured questions with rubrics)
- Student content viewing, homework, timed tests
- Student AI test-taking with timer and all question types
- Student AI test results with grade, per-question feedback, rubric breakdown
- Student performance dashboard with score trends
- Parent dashboard
- S3 storage, PostgreSQL, multi-tenancy
- CI/CD: GitHub Actions → EC2
- Custom branding

---

# 8. KNOWN ISSUES

## CRITICAL (P0):
### 1. Login/Logout State Management Bug
After admin logs out, subsequent logins for other roles fail, get stuck, or log into wrong user. The API works correctly (confirmed via curl), but the frontend auth state lifecycle fails. **Status: NOT FIXED** (recurring 2x).

## HIGH (P1):
### 2. EC2 Admin Dashboard Empty
Separate database on EC2. Use `init_ec2_admin.py` to seed. **Status: USER VERIFICATION PENDING.**

## MEDIUM (P2):
### 3. Code Refactoring - `server.py` and `App.js` are monolithic
### 4. PDF Extraction Flaws - fill_blanks/match_following format issues

## LOW (P3):
### 5. Redis Not Connected
### 6. Automated Testing Suite not started

---

# 9. PENDING TASKS

## Immediate:
1. **Fix Login/Logout Bug (P0)** - Deep debug auth state lifecycle
2. **Phase 5: Teacher Review Mode (P0)** - Teachers view AI grading, override marks

## Medium Priority:
3. **Phase 6: Data Retention Policy (P1)** - Auto-delete detailed reports after 1 month
4. **Code Refactoring (P1)** - Split monolithic files

## Backlog:
5. PDF Extraction Fixes (P2)
6. Redis Caching (P3)
7. Automated Testing (P3)

---

# 10. TECHNICAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                       USERS                              │
│  Admin | Teachers | Students | Parents                   │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────┐
│              FRONTEND (React 19)                         │
│  App.js + 15+ components | CSS | Axios + Bearer Token    │
└────────────────────┬────────────────────────────────────┘
                     │ REST API (/api/*)
                     ▼
┌─────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI)                            │
│  server.py + structured_tests.py | JWT Auth              │
└──┬────────────┬─────────────┬────────────┬──────────────┘
   │            │             │            │
   ▼            ▼             ▼            ▼
┌────────┐ ┌────────┐ ┌──────────────┐ ┌──────────┐
│Postgres│ │ AWS S3 │ │  OpenRouter   │ │Background│
│ (RDS)  │ │ (PDFs) │ │GPT-4o/Gemini │ │ Workers  │
└────────┘ └────────┘ └──────────────┘ └──────────┘
```

## Authentication Flow:
1. User submits login → POST /api/auth/login {roll_no, password}
2. Backend validates → returns {token, user}
3. Frontend stores token in localStorage
4. Axios interceptor attaches Bearer token to every request
5. Backend checks Bearer header first, then Cookie

---

# 11. CREDENTIALS

| System | Username/Key | Password/Value |
|--------|-------------|----------------|
| Admin | `admin` | `Admin@123` |
| Test Teacher | roll_no: `T001` | `123456` |
| Test Student | roll_no: `S001` | `123456` |

---

# 12. CHANGE LOG

## Version 3.0 (March 15, 2026)

### AI Evaluation System:
- Phase 1: Backend models + evaluation agent + API endpoints
- Phase 2: Teacher test creation UI (StructuredTestCreator)
- Phase 3: Student test-taking + results UI (StudentAITest)
- Phase 4: Student performance dashboard with score trends
- Parallel data fetching (Promise.allSettled) for subject loading
- Fixed double `/api` prefix bug in frontend API calls

### Bug Fixes:
- Parallelized selectSubject() — was hanging due to sequential API calls
- Fixed CSS nesting bug in StructuredTestCreator.css
- Fixed AI test list not showing for students

## Version 2.0 (March 15, 2026)
- CI/CD pipeline fixed
- Dual auth (Cookie + Bearer Token)
- Custom branding overhaul
- MCQ rendering fixes
- White text bug fixes
- OpenRouter API key refresh

## Version 1.0 (March 7, 2026)
- Initial handover document
- All core features built

---

**Document End**
**Version:** 3.0 | **Updated:** March 15, 2026
