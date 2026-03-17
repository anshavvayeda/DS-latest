# StudyBuddy Project Handover Document
## Complete Context for New Session Setup

**Document Version:** 4.0  
**Last Updated:** March 17, 2026  
**Project:** StudyBuddy K-12 Learning Management System  
**GitHub Repository:** https://github.com/anshavvayeda/DS-latest  
**Current Status:** Development Active | CI/CD Working | AI Evaluation + AI Homework Complete | Mobile Responsive

---

# TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Current Project State](#2-current-project-state)
3. [AI Evaluation System](#3-ai-evaluation-system)
4. [AI Homework System](#4-ai-homework-system)
5. [Complete Setup Instructions](#5-complete-setup-instructions)
6. [Key Files & Their Purpose](#6-key-files--their-purpose)
7. [Important Commands](#7-important-commands)
8. [What's Working](#8-whats-working)
9. [Known Issues](#9-known-issues)
10. [Pending Tasks](#10-pending-tasks)
11. [Technical Architecture](#11-technical-architecture)
12. [Credentials](#12-credentials)
13. [Change Log](#13-change-log)

---

# 1. PROJECT OVERVIEW

## What is StudyBuddy?

StudyBuddy is a comprehensive K-12 Learning Management System (LMS) designed for Indian schools with AI-powered features.

### Core Functionality:
- **Multi-role system**: Admin, Teacher, Student, Parent
- **AI Content Generation**: Automatic creation of revision notes, flashcards (1-2 word answers), and practice quizzes from textbook PDFs
- **AI Paper Evaluation**: Multi-LLM evaluation system for structured tests with per-question feedback
- **AI Homework**: Structured homework with pre-generated hints, "Check Answer" feature, and dropdown-based Match-the-Following
- **Assessment System**: AI-evaluated tests with timed test-taking, previous year papers
- **Performance Tracking**: Student performance dashboard with score trends across AI-evaluated tests
- **Parent Dashboard**: View child's AI homework and test stats, performance charts
- **Admin-Centric Auth**: All user management handled by admin (no self-registration, no OTP)

### Technology Stack:

**Backend:**
- Framework: FastAPI (Python)
- Database: PostgreSQL (AWS RDS)
- Storage: AWS S3
- AI: OpenRouter API (GPT-4o for subjective evaluation, Gemini Flash for semantic tasks)
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

## Completed Work (as of March 17, 2026):

### AI Evaluation System (Phases 1-4 COMPLETE):

**Phase 1 - Backend (COMPLETE):**
- Database models: StructuredTest, StructuredQuestion, StructuredTestSubmission, EvaluationResult
- AI evaluation service (`evaluation_agent.py`) with multi-LLM orchestration
- 7 question types: MCQ, True/False, Fill-blank, One-word, Match-following, Short/Long answer, Numerical
- Full CRUD API endpoints in `structured_tests.py`

**Phase 2 - Teacher UI (COMPLETE):**
- `StructuredTestCreator.jsx` with multi-step form for creating tests
- Subject auto-populated from parent view (read-only field)
- Detailed marking schemes and rubrics per question
- Published AI test list on teacher dashboard (`TeacherAITestsList` component)

**Phase 3 - Student Results UI (COMPLETE):**
- `StudentAITest.jsx` for test-taking and results viewing
- Test-taking: Timer, question navigation dots, all input types (MCQ radio, TF, text, textarea, match dropdowns)
- Results: Grade card (A+/A/B/C/D/F), score/percentage, improvement notes
- Per-question expandable breakdown with rubric points, feedback, correct answers
- Match-the-Following uses dropdown selectors for better UX

**Phase 4 - Student Performance Dashboard (COMPLETE):**
- Backend API: `/api/structured-tests/student/performance` with score trends, subject breakdown, question type analysis
- Frontend: `StudentPerformanceDashboard.jsx` with score trend chart, subject-wise stats, question type strengths/weaknesses

### AI Homework System (COMPLETE):

- `StructuredHomeworkCreator.jsx` - Teacher creates AI homework (same UI pattern as test creator)
- `StudentAIHomework.jsx` - Student solves homework with pre-generated hints and "Check Answer" feature
- **Pre-generated hints**: Hints are generated via LLM when teacher publishes homework, stored in `hint_text` column (no real-time LLM calls for students)
- **Check Answer**: Replaces old "Reveal Answer" — gives correctness feedback without revealing the answer
- **Match-the-Following**: Uses dropdown selectors instead of text input for better student UX
- Published AI homework visible on teacher dashboard (`TeacherAIHomeworkList` component)
- Parent dashboard shows AI homework stats

### Authentication (SIMPLIFIED):
- **Admin-centric model**: All user registration and password resets handled by admin
- **Removed**: Teacher self-registration form, OTP-based password reset system
- **Removed**: All OTP code — schemas, models, service functions, env vars
- Login: Roll number + password for teachers/students

### Legacy Feature Removal (COMPLETE):
- **Deleted**: Entire PDF-based homework system (`homework.py` routes, frontend components)
- All homework is now AI-structured only

### Mobile Responsiveness (VERIFIED):
- CSS media queries at 768px and 480px breakpoints
- Teacher tabs stack vertically on mobile
- Subject cards use single column layout on mobile
- No horizontal overflow at 375px viewport
- Gujarati language button hidden on mobile
- AI test/homework teacher cards stack vertically on mobile
- Flashcard height auto-sizes on mobile (no overlap with hints/buttons)
- Tested: 8/8 mobile responsiveness tests passed

### UI/UX Improvements (COMPLETE):
- Subject chips with ✕ delete buttons in teacher class management view
- Custom StudyBuddy logos and branding with galaxy background
- Flashcard generation produces 1-2 word answers with playing cards icon
- AI homework/test card contrast fixed for student view
- Calligraphic tagline with Dancing Script font

### Core LMS Features (COMPLETE):
- Complete API endpoints for all user roles
- AI content generation system (background processing)
- Timed test management with previous year papers
- Analytics and reporting
- 20+ component files across the frontend
- CI/CD Pipeline via GitHub Actions

### Bug Fixes (All Fixed):
- **CRITICAL Login Bug (P0)**: Fixed triple root cause — cookie deletion mismatch, stale cookie priority, frontend cookie cleanup
- Parent Dashboard graphs rendering (replaced SVG with HTML/CSS bar chart)
- Parent Dashboard AI test scores display
- Save Draft not saving before Publish
- Parallel data fetching (Promise.allSettled) preventing UI hang
- MCQ dict-format options rendering
- Double `/api` prefix in AI test API URLs
- White text on white backgrounds

---

# 3. AI EVALUATION SYSTEM

## Architecture:
```
Teacher -> Create Test (StructuredTestCreator) -> Publish
Student -> View Tests -> Attempt Test (StudentAITest) -> Submit
AI Agent -> Evaluate (GPT-4o / Gemini Flash / Deterministic)
Student -> View Results (score card, per-question feedback)
Student -> Performance Dashboard (trends, strengths/weaknesses)
Teacher -> Review Submissions (TeacherAITestsList)
```

## Question Types & Evaluation Strategy:
| Type | Evaluator | Method |
|------|-----------|--------|
| MCQ | Deterministic | Exact match |
| True/False | Deterministic | Exact match |
| Fill-blank | Deterministic | Exact match |
| One-word | Gemini Flash | Semantic match |
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

---

# 4. AI HOMEWORK SYSTEM

## Architecture:
```
Teacher -> Create Homework (StructuredHomeworkCreator) -> Publish
  -> Background: AI generates hints for each question -> Stored in DB
Student -> View Homework -> Start Attempt -> Get Hint (from DB) -> Check Answer -> Submit
Teacher -> View Submissions (TeacherAIHomeworkList)
Parent -> View AI Homework Stats (ParentDashboard)
```

## Key API Endpoints:
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/structured-homework` | Create draft homework |
| PUT | `/api/structured-homework/publish/{id}` | Publish (triggers hint generation) |
| GET | `/api/structured-homework/hint/{submission_id}/{question_id}` | Get pre-generated hint |
| POST | `/api/structured-homework/check-answer/{submission_id}/{question_id}` | Check answer correctness |
| GET | `/api/structured-homework/student/list/{subject_id}/{standard}` | List homework for students |

## Database:
- `structured_homework_questions` table has `hint_text` column for pre-generated hints

---

# 5. COMPLETE SETUP INSTRUCTIONS

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
curl -s -X POST "$API_URL/api/admin/register-student" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"name":"Test Teacher","phone":"8888888888","password":"Test@123","role":"teacher","school_name":"Test School","roll_no":"teacher4"}'

# Register student
curl -s -X POST "$API_URL/api/admin/register-student" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"name":"Test Student","phone":"9999999999","password":"123456","role":"student","standard":5,"school_name":"Test School","roll_no":"S001"}'
```

---

# 6. KEY FILES & THEIR PURPOSE

## Repository Structure:
```
/app/
├── backend/
│   ├── server.py                          # Main FastAPI app
│   ├── requirements.txt
│   ├── .env
│   ├── init_ec2_admin.py
│   ├── alembic/                           # Database migrations
│   │   └── versions/                      # Migration files (incl. hint_text column)
│   └── app/
│       ├── models/
│       │   └── database.py                # SQLAlchemy models (Users, Tests, Homework, etc.)
│       ├── schemas/
│       │   └── __init__.py                # Pydantic request/response models
│       ├── routes/
│       │   ├── auth.py                    # Authentication (login, admin auth)
│       │   ├── content.py                 # Content management
│       │   ├── parent_teacher.py          # Parent/teacher dashboard APIs
│       │   ├── structured_tests.py        # AI evaluation test endpoints
│       │   └── structured_homework.py     # AI homework endpoints (hints, check-answer)
│       └── services/
│           ├── evaluation_agent.py        # AI evaluation orchestrator
│           ├── ai_service.py              # AI content generation
│           ├── ai_orchestrator_v2.py      # Background AI tasks
│           ├── gpt4o_extraction.py        # PDF extraction
│           ├── storage_service.py         # S3 operations
│           └── auth_service.py            # JWT token creation & verification
├── frontend/
│   ├── src/
│   │   ├── App.js                         # Main React app
│   │   ├── App.css                        # Global styles (incl. responsive CSS)
│   │   └── components/
│   │       ├── AuthScreen.jsx             # Login screen (simplified, no OTP/register)
│   │       ├── Header.jsx                 # App header with role toggle, language btn
│   │       ├── GalaxyBackground.jsx       # Animated background
│   │       ├── ProfileDropdown.jsx        # User profile dropdown
│   │       ├── TeacherView.jsx            # Teacher dashboard (subject chips with ✕ delete)
│   │       ├── StudentView.jsx            # Student dashboard
│   │       ├── ParentDashboard.jsx        # Parent dashboard (AI homework/test stats)
│   │       ├── AdminDashboard.jsx         # Admin user management
│   │       ├── StructuredTestCreator.jsx  # Teacher AI test creation
│   │       ├── StructuredHomeworkCreator.jsx # Teacher AI homework creation
│   │       ├── StudentAITest.jsx          # Student test-taking & results
│   │       ├── StudentAIHomework.jsx      # Student homework (hints, check answer)
│   │       ├── StudentPerformanceDashboard.jsx # Performance trends
│   │       ├── StudentContentViewer.jsx   # Content viewer
│   │       ├── ToolContentDisplay.jsx     # Flashcards, notes, quiz display
│   │       ├── TeacherUpload.jsx          # PDF upload for content generation
│   │       ├── TeacherAnalytics.jsx       # Analytics dashboard
│   │       ├── TeacherReviewMode.jsx      # Teacher review of AI grading
│   │       ├── HomeworkAnswering.jsx       # Homework answering UI
│   │       ├── TestManagement.jsx         # Test management UI
│   │       ├── QuestionRenderer.jsx       # Shared question rendering
│   │       └── StudentProfileView.jsx     # Student profile
│   └── public/
│       ├── studybuddy-icon.png
│       └── studybuddy-banner.png
├── memory/
│   └── PRD.md
└── STUDYBUDDY_HANDOVER.md
```

### DELETED Files (no longer exist):
- `/app/backend/app/routes/homework.py` — Old PDF homework system (removed)
- OTP-related code in schemas, models, auth_service — All removed

---

# 7. IMPORTANT COMMANDS

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

# Teacher login
curl -s -X POST "$API_URL/api/auth/login" -H "Content-Type: application/json" -d '{"roll_no":"teacher4","password":"Test@123"}'

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

# 8. WHAT'S WORKING

- Admin login, user management, analytics
- Teacher PDF upload, AI content generation (notes, flashcards, quizzes)
- Teacher AI test creation with structured questions and rubrics
- Teacher AI homework creation with auto-hint generation on publish
- Teacher dashboard shows published AI tests and homework with review/delete options
- Teacher subject management with ✕ delete buttons on subject chips
- Student content viewing with flashcards, revision notes, practice quizzes
- Student AI test-taking with timer, all question types, dropdown Match-the-Following
- Student AI test results with grade card, per-question feedback, rubric breakdown
- Student AI homework with pre-generated hints, "Check Answer" feature
- Student performance dashboard with score trends
- Parent dashboard with AI homework and test statistics, performance charts
- Mobile responsive design for all views (Teacher, Student, Parent)
- S3 storage, PostgreSQL, multi-tenancy
- CI/CD: GitHub Actions -> EC2
- Custom branding with galaxy background

---

# 9. KNOWN ISSUES

## MEDIUM (P2):
### 1. EC2 Admin Dashboard Empty
Separate database on EC2. Use `init_ec2_admin.py` to seed.

### 2. PDF Extraction Flaws
Minor formatting issues in fill_blanks/match_following extraction for PYQ papers.

### 3. "Login As User" Search Bug
AdminDashboard search display has a pre-existing bug.

## LOW (P3):
### 4. Redis Not Connected
Benign connection errors in backend logs. Not blocking any feature.

### 5. Automated Testing Suite
Not started yet.

---

# 10. PENDING TASKS

## Medium Priority (P1):
1. **Fix PDF Extraction Flaws** - PYQ paper formatting issues
2. **Fix AdminDashboard "Login As User" Search Bug**

## Backlog (P2-P3):
3. **Implement Redis Caching** - Performance optimization
4. **Automated Testing Suite** - Regression testing
5. **Teacher Review Mode Enhancements** - Override AI marks with detailed feedback

---

# 11. TECHNICAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                       USERS                              │
│  Admin | Teachers | Students | Parents                   │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────┐
│              FRONTEND (React 19)                         │
│  App.js + 20+ components | CSS | Axios + Bearer Token    │
│  Mobile Responsive (768px / 480px breakpoints)           │
└────────────────────┬────────────────────────────────────┘
                     │ REST API (/api/*)
                     ▼
┌─────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI)                            │
│  server.py + routes/ (auth, tests, homework, content)    │
│  JWT Auth | Background Tasks (hint generation)           │
└──┬────────────┬─────────────┬────────────┬──────────────┘
   │            │             │            │
   ▼            ▼             ▼            ▼
┌────────┐ ┌────────┐ ┌──────────────┐ ┌──────────┐
│Postgres│ │ AWS S3 │ │  OpenRouter   │ │Background│
│ (RDS)  │ │ (PDFs) │ │GPT-4o/Gemini │ │ Workers  │
└────────┘ └────────┘ └──────────────┘ └──────────┘
```

## Authentication Flow:
1. User submits login -> POST /api/auth/login {roll_no, password}
2. Backend validates -> returns {token, user}
3. Frontend stores token in localStorage
4. Axios interceptor attaches Bearer token to every request
5. Backend checks Bearer header first, then Cookie
6. No OTP, no self-registration (admin manages all users)

## Key Design Decisions:
- **Pre-generated hints**: AI hints generated at publish time, stored in DB, served instantly to students (no real-time LLM calls)
- **Background Tasks**: FastAPI `BackgroundTasks` for expensive operations (hint generation, AI content creation)
- **Database-Centric**: Shifting from dynamic API calls to pre-computed, stored content for performance
- **Responsive CSS**: Media queries at 768px and 480px; mobile-first adjustments for all views

---

# 12. CREDENTIALS

| System | Username/Key | Password/Value |
|--------|-------------|----------------|
| Admin | `admin` | `Admin@123` |
| Test Teacher | roll_no: `teacher4` | `Test@123` |
| Test Student | roll_no: `S001` | `123456` |

---

# 13. CHANGE LOG

## Version 4.0 (March 17, 2026)

### New Features:
- **AI Homework System**: Complete structured homework with pre-generated hints, Check Answer, dropdown Match-the-Following
- **Subject Delete**: Teacher can remove subjects via ✕ buttons on subject chips
- **Parent AI Stats**: Parent dashboard displays AI homework statistics

### Auth Simplification:
- Removed teacher self-registration and OTP-based password reset
- Removed all OTP code: schemas, models, service functions, env vars (MOCK_OTP_MODE, MOCK_OTP_VALUE)
- Auth is now fully admin-managed

### Legacy Removal:
- Deleted entire PDF-based homework system (routes, components, DB queries)

### Mobile Responsiveness:
- Added responsive CSS for Teacher, Student, and Parent views (768px / 480px breakpoints)
- Teacher tabs stack vertically, subject cards single-column
- Gujarati language button hidden on mobile
- AI test/homework teacher cards stack vertically
- Flashcard auto-height with no content/button overlap
- 8/8 mobile tests passed

### Bug Fixes:
- Fixed CRITICAL login bug (triple root cause: cookie deletion, stale cookie priority, frontend cleanup)
- Fixed Parent Dashboard graphs and AI test scores
- Fixed Save Draft not saving before Publish
- Fixed AI homework not visible on teacher dashboard
- Fixed student view AI homework card contrast

### UI/UX:
- Polished AI Homework and Test creator UIs for consistency
- Updated flashcard generation: 1-2 word answers, playing cards icon
- Flashcard icon alignment with other AI tools tabs

## Version 3.0 (March 15, 2026)

### AI Evaluation System:
- Phase 1: Backend models + evaluation agent + API endpoints
- Phase 2: Teacher test creation UI (StructuredTestCreator)
- Phase 3: Student test-taking + results UI (StudentAITest)
- Phase 4: Student performance dashboard with score trends
- Parallel data fetching (Promise.allSettled) for subject loading
- Fixed double `/api` prefix bug in frontend API calls

## Version 2.0 (March 15, 2026)
- CI/CD pipeline fixed
- Dual auth (Cookie + Bearer Token)
- Custom branding overhaul
- MCQ rendering fixes
- White text bug fixes

## Version 1.0 (March 7, 2026)
- Initial handover document
- All core features built

---

**Document End**
**Version:** 4.0 | **Updated:** March 17, 2026
