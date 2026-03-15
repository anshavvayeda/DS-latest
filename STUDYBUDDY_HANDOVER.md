# StudyBuddy Project Handover Document
## Complete Context for New Session Setup

**Document Version:** 2.0  
**Last Updated:** March 15, 2026  
**Project:** StudyBuddy K-12 Learning Management System  
**GitHub Repository:** https://github.com/anshavvayeda/DS-latest  
**Current Status:** Development Active | CI/CD Working | UI Polish & Bug Fixes In Progress

---

# TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Current Project State](#2-current-project-state)
3. [Complete Setup Instructions](#3-complete-setup-instructions)
4. [Environment Configuration](#4-environment-configuration)
5. [Key Files & Their Purpose](#5-key-files--their-purpose)
6. [Important Commands](#6-important-commands)
7. [What's Working](#7-whats-working)
8. [Known Issues](#8-known-issues)
9. [Pending Tasks](#9-pending-tasks)
10. [Technical Architecture](#10-technical-architecture)
11. [Troubleshooting Guide](#11-troubleshooting-guide)
12. [Important Context](#12-important-context)
13. [Change Log](#13-change-log)

---

# 1. PROJECT OVERVIEW

## What is StudyBuddy?

StudyBuddy is a comprehensive K-12 Learning Management System (LMS) designed for Indian schools with AI-powered features.

### Core Functionality:
- **Multi-role system**: Admin, Teacher, Student, Parent, Maintenance
- **AI Content Generation**: Automatic creation of revision notes, flashcards, and practice quizzes from textbook PDFs
- **Assessment System**: Homework management, timed tests, previous year papers
- **Performance Tracking**: Analytics for students, teachers, and schools
- **Multi-tenancy**: School-based data isolation

### Technology Stack:

**Backend:**
- Framework: FastAPI (Python)
- Database: PostgreSQL (AWS RDS)
- Storage: AWS S3
- AI: OpenRouter API (Claude Sonnet 4.5 + Gemini 2.5 Flash)
- Authentication: JWT-based (Dual: Cookie + Bearer Token)

**Frontend:**
- Framework: React 19
- Styling: TailwindCSS + Radix UI
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

### Backend Development:
- 7,245+ lines of FastAPI code (server.py)
- Complete API endpoints for all user roles
- AI content generation system (background processing)
- Homework and test management with PDF extraction
- Analytics and reporting
- Teacher analytics dashboard
- Background AI orchestrator with retry logic
- S3 storage integration
- PostgreSQL database models (724 lines)
- Dual authentication (Cookie + Bearer Token headers)
- Public teacher registration endpoint (`/api/auth/register-teacher`)
- EC2 admin seeding script (`init_ec2_admin.py`)

### Frontend Development:
- 4,500+ lines of React code (App.js)
- 13+ component files
- Complete UI for all user roles
- AI content generation popup (background process message)
- Admin, Teacher, Student, Parent dashboards
- Responsive design with TailwindCSS
- Test taking interface with timer
- Homework submission with AI help
- Axios interceptor for Bearer token authentication
- localStorage-based token management

### CI/CD Pipeline (COMPLETED):
- GitHub Actions workflow fully operational
- Automatic deployment to EC2 on push to main
- Node.js v20 on EC2 (upgraded from v18)
- Python virtual environment on EC2 (`/home/ubuntu/studybuddy/venv`)
- Nginx configured for 30MB file uploads
- EC2 admin seeding script integrated

### Branding & UI (COMPLETED - March 11-15, 2026):
- Custom StudyBuddy atom/math logo on all pages
- Login page: atom icon (transparent background)
- Header: Single atom icon (56px, proportional)
- Teacher banner: "STUDYBUDDY" circular logo (220px)
- Tagline: "Your Personal AI Teaching Assistant 24*7" (Dancing Script calligraphic font, white)
- "Made with Emergent" badge hidden
- Progress bar UI simplified (removed Current Stage/Elapsed box)
- Progress text: "AI is doing the magic, sit back and relax..."

### Bug Fixes (March 11-15, 2026):
- MCQ options rendering: dict-format options (`{a: '7', b: '70'}`) now converted to array with radio buttons
- Auto-detect MCQ type when `question_type` is null but options exist
- White text on white backgrounds: Fixed body `color: #F8FAFC` inheritance in homework/student content areas
- Teacher dropdown: Shows "Teacher" instead of "Student" for teacher logins
- OpenRouter API key updated (old key was expired/invalid)

### Documentation:
- Project handoff documentation
- CI/CD setup guide
- Marketing campaign document
- Multiple debugging guides

---

## Current Issues (Priority Order):

### CRITICAL (P0):
1. **Login/Logout Bug** - After admin logs out, subsequent login attempts for other roles (teacher/student) are buggy. Login fails, gets stuck on "logging in", or incorrectly logs into previous admin account. The API works fine (tested via curl), but the frontend `checkAuth()` flow fails. Root cause: stale tokens in localStorage and/or Axios interceptor not picking up new tokens correctly.
   - **Workaround**: Inject token via browser console or clear localStorage manually
   - **Status**: IN PROGRESS - needs deep debugging of auth state lifecycle

### HIGH (P1):
2. **EC2 Admin Dashboard Empty** - After deployment, EC2 instance has separate empty database. Use `init_ec2_admin.py` to seed admin user. Status: USER VERIFICATION PENDING.

### MEDIUM (P2):
3. **Code Refactoring** - `server.py` (7,245 lines) and `App.js` (4,500+ lines) are monolithic and need splitting into modules.
4. **PDF Extraction Flaws** - `fill_blanks` uses wrong format, `match_following` sometimes missing `correct_matches`.

### LOW (P3):
5. **Redis Not Connected** - Caching disabled, app works fine without it.

---

# 3. COMPLETE SETUP INSTRUCTIONS

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
ls -la
```

### Step 2: Create Backend .env
```bash
cat > /app/backend/.env << 'EOF'
# PostgreSQL Database (AWS RDS)
DATABASE_URL=postgresql+asyncpg://postgres:PASSWORD@HOST:5432/postgres

# Authentication
MOCK_OTP_MODE=true
MOCK_OTP_VALUE=123456
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# OpenRouter API Key (for AI features)
OPENROUTER_API_KEY=your-openrouter-key-here

# AWS S3 Storage
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=ap-south-1

# Admin Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@123
ENV=production
EOF
```
**IMPORTANT**: Replace all placeholder values with actual credentials.

### Step 3: Create Frontend .env
```bash
cat > /app/frontend/.env << 'EOF'
REACT_APP_BACKEND_URL=https://auto-grading-1.preview.emergentagent.com
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
EOF
```

### Step 4: Install Dependencies
```bash
# Backend
cd /app/backend
pip install -q -r requirements.txt

# Frontend (ALWAYS use yarn, NEVER npm)
cd /app/frontend
yarn install
```

### Step 5: Start Services
```bash
sudo supervisorctl restart all
sleep 5
sudo supervisorctl status
```

### Step 6: Verify
```bash
# Backend
curl $REACT_APP_BACKEND_URL/api/

# Admin login test
curl -X POST "$REACT_APP_BACKEND_URL/api/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123"}'

# Frontend logs
tail -n 30 /var/log/supervisor/frontend.out.log
# Should see: "webpack compiled successfully"
```

### Step 7: Create Test Data (if fresh database)
```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
TOKEN=$(curl -s -X POST "$API_URL/api/admin/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"Admin@123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Register teacher first (creates school namespace)
curl -s -X POST "$API_URL/api/admin/register-student" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Test Teacher","phone":"8888888888","password":"123456","role":"teacher","school_name":"Test School","roll_no":"T001"}'

# Register student (school must exist via teacher)
curl -s -X POST "$API_URL/api/admin/register-student" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Test Student","phone":"9999999999","password":"123456","role":"student","standard":5,"school_name":"Test School","roll_no":"S001"}'
```

---

# 4. ENVIRONMENT CONFIGURATION

## Backend .env Variables:

| Variable | Purpose | Required |
|----------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection (format: `postgresql+asyncpg://user:pass@host:5432/db`) | YES |
| `MOCK_OTP_MODE` | If `true`, OTP is always `MOCK_OTP_VALUE` | YES |
| `MOCK_OTP_VALUE` | Default: `123456` | YES |
| `JWT_SECRET` | Token signing key (generate: `openssl rand -hex 32`) | YES |
| `JWT_ALGORITHM` | `HS256` | YES |
| `JWT_EXPIRATION_HOURS` | Token validity (default: `24`) | YES |
| `OPENROUTER_API_KEY` | AI features key from https://openrouter.ai/keys | YES |
| `AWS_ACCESS_KEY_ID` | S3 access | YES |
| `AWS_SECRET_ACCESS_KEY` | S3 secret | YES |
| `S3_BUCKET_NAME` | S3 bucket (default: `anshavprojects`) | YES |
| `AWS_REGION` | AWS region (default: `ap-south-1`) | YES |
| `ADMIN_USERNAME` | Default admin (default: `admin`) | YES |
| `ADMIN_PASSWORD` | Default admin password (default: `Admin@123`) | YES |

## Frontend .env Variables:

| Variable | Purpose | Required |
|----------|---------|----------|
| `REACT_APP_BACKEND_URL` | Backend API base URL | YES |
| `WDS_SOCKET_PORT` | `443` (for Emergent environment) | YES |
| `ENABLE_HEALTH_CHECK` | `false` | YES |

---

# 5. KEY FILES & THEIR PURPOSE

## Repository Structure:
```
/app/
├── .github/
│   └── workflows/
│       ├── deploy-to-ec2.yml           # Main deployment workflow (WORKING)
│       └── test-ssh-connection.yml     # SSH test workflow
├── backend/
│   ├── server.py                       # Main FastAPI app (7,245+ lines, MODIFIED)
│   ├── requirements.txt
│   ├── .env                            # Backend credentials (MUST CREATE)
│   ├── init_ec2_admin.py               # EC2 admin seeder script
│   ├── alembic/                        # DB migrations
│   └── app/
│       ├── models/
│       │   └── database.py             # SQLAlchemy models (724 lines)
│       └── services/
│           ├── ai_service.py           # AI content generation (3,000+ lines)
│           ├── ai_orchestrator_v2.py   # Background AI tasks
│           ├── gpt4o_extraction.py     # PDF extraction
│           ├── storage_service.py      # S3 operations
│           ├── auth_service.py         # JWT & authentication
│           └── background_extraction.py
├── frontend/
│   ├── src/
│   │   ├── App.js                      # Main React app (4,500+ lines, MODIFIED)
│   │   ├── App.css                     # Global styles (MODIFIED)
│   │   ├── index.js
│   │   └── components/
│   │       ├── TeacherUpload.jsx
│   │       ├── TeacherAnalytics.jsx
│   │       ├── StudentContentViewer.jsx  # (MODIFIED - dict options fix)
│   │       ├── StudentContentViewer.css  # (MODIFIED - dark text fix)
│   │       ├── HomeworkAnswering.jsx
│   │       ├── HomeworkAnswering.css     # (MODIFIED - dark text fix)
│   │       ├── TestManagement.jsx        # (MODIFIED - progress UI)
│   │       ├── QuestionRenderer.jsx      # (MODIFIED - MCQ dict→array fix)
│   │       ├── ProfileDropdown.jsx       # (MODIFIED - Teacher name fix)
│   │       ├── AdminDashboard.jsx
│   │       ├── ParentDashboard.jsx
│   │       └── TestTaking.jsx
│   ├── public/
│   │   ├── studybuddy-icon.png         # Atom/math icon (login + header)
│   │   ├── studybuddy-banner.png       # STUDYBUDDY circular logo (teacher banner)
│   │   ├── studybuddy-brand.png        # Combined brand image (unused now)
│   │   └── studybuddy-logo.png         # Lightbulb mascot (unused now)
│   ├── .env                            # Frontend env (MUST CREATE)
│   └── package.json
├── scripts/
│   ├── configure-nginx.sh              # Nginx 30MB upload config
│   └── ec2-setup.sh                    # EC2 initial setup
└── memory/
    └── PRD.md                          # Product requirements
```

## Critical File Modifications Summary:

### Backend (`server.py`):
- Dual auth: `get_current_user()` checks Bearer header first, then Cookie
- Login responses include `token` in body
- Public endpoint: `POST /api/auth/register-teacher`
- `app.include_router(api_router)` moved to end of file (fixed 404 for analytics)

### Frontend (`App.js`):
- `handleLogin()`: Clears old token, stores new token in localStorage
- `checkAuth()`: Calls `GET /api/auth/me` with Bearer token
- Axios interceptor: Reads token from localStorage at request time
- `handleLogout()`: Clears localStorage token
- All logo `src` attributes point to `/studybuddy-icon.png`
- Header uses single `app-header-logo` class (56px)

### Frontend (`App.css`):
- `body { color: #F8FAFC }` - global near-white text (for dark theme)
- `#emergent-badge { display: none !important }` - hides badge
- `.app-header-logo { height: 56px }` - header icon
- `.banner-logo { width: 220px; height: 220px }` - teacher banner
- `.banner-tagline` - Dancing Script calligraphic font, white
- `.teacher-view { padding: 10px 40px }` - reduced top padding

### Components:
- `QuestionRenderer.jsx`: MCQ handles dict options via helper function; auto-detects MCQ when type is null
- `StudentContentViewer.jsx/css`: Dict→array options conversion; dark text override
- `HomeworkAnswering.css`: Dark text override (preserving white on colored headers/buttons)
- `TestManagement.jsx`: Removed stage/elapsed info box; changed text to "AI is doing the magic..."
- `ProfileDropdown.jsx`: Shows `user?.name` with role-based fallback

---

# 6. IMPORTANT COMMANDS

## Service Management:
```bash
sudo supervisorctl restart all          # Restart everything
sudo supervisorctl restart backend      # Backend only
sudo supervisorctl restart frontend     # Frontend only
sudo supervisorctl status               # Check status
```

## Logs:
```bash
tail -f /var/log/supervisor/backend.err.log    # Backend errors
tail -f /var/log/supervisor/backend.out.log    # Backend output
tail -f /var/log/supervisor/frontend.out.log   # Frontend build
```

## API Testing:
```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Admin login
curl -s -X POST "$API_URL/api/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123"}'

# Student/Teacher login
curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"roll_no":"S001","password":"123456"}'

# Authenticated request
TOKEN="your-jwt-token-here"
curl -s "$API_URL/api/auth/me" -H "Authorization: Bearer $TOKEN"

# Check OpenRouter API key
curl -s "https://openrouter.ai/api/v1/auth/key" \
  -H "Authorization: Bearer $(grep OPENROUTER_API_KEY /app/backend/.env | cut -d= -f2)"
```

## Dependencies:
```bash
# Backend (always pip install then freeze)
pip install package-name && pip freeze > /app/backend/requirements.txt

# Frontend (ALWAYS yarn, NEVER npm)
cd /app/frontend && yarn add package-name
```

---

# 7. WHAT'S WORKING

## Fully Functional:
- Admin login, user management, bulk upload, analytics
- Teacher PDF upload, AI content generation (background), homework/test management
- Student content viewing (notes, flashcards, quizzes), homework with AI help, timed tests
- Parent dashboard with child performance
- AI: revision notes, flashcards, 75 quiz questions, answer checking, hints
- S3 storage, PostgreSQL database, multi-tenancy
- CI/CD: GitHub Actions → EC2 deployment
- Nginx: 30MB file upload limit
- Custom branding: atom/math logo, calligraphic tagline
- MCQ rendering with dict-format options
- Dark text on white card backgrounds

## Authentication System:
- Backend accepts both Cookie and Bearer Token (`get_current_user()`)
- Frontend stores JWT in localStorage
- Axios interceptor attaches Bearer token to all requests
- Login API returns token in response body
- **KNOWN BUG**: Frontend auth state lifecycle has issues (see Known Issues #1)

---

# 8. KNOWN ISSUES

## CRITICAL (P0):

### 1. Login/Logout State Management Bug
**Description:** After admin logs out, subsequent logins for other roles fail, get stuck, or log into wrong user.

**Root Cause Analysis:**
- The API works correctly (confirmed via curl)
- The frontend `handleLogin()` stores token in localStorage
- `onSuccess()` calls `checkAuth()` which calls `GET /api/auth/me`
- `checkAuth()` returns 401 — meaning the token isn't being sent correctly
- The Axios interceptor reads from localStorage, but timing/state issues prevent it from using the new token

**Attempted Fixes (Insufficient):**
- Clear localStorage on logout
- Clear old token before storing new one in handleLogin
- Get token from localStorage at request time (not mount time)

**Next Debug Steps:**
1. Add `console.log` in Axios interceptor to verify token is being read
2. Check if `checkAuth()` runs before token is written to localStorage
3. Verify the interceptor ID isn't duplicated (cleanup in useEffect return)
4. Consider using React state for token instead of localStorage
5. Test: does the interceptor from the FIRST `useEffect` call get cleaned up properly?

**Files to Examine:**
- `/app/frontend/src/App.js` lines 750-800 (checkAuth + interceptor)
- `/app/frontend/src/App.js` lines 1008-1034 (handleLogin)
- `/app/frontend/src/App.js` lines 814-825 (handleLogout)

**Workaround:** Inject token via browser console: `localStorage.setItem('auth_token', 'TOKEN_VALUE')` then reload.

---

## HIGH (P1):

### 2. EC2 Admin Dashboard Empty
- Separate database on EC2 — expected behavior
- Use `init_ec2_admin.py` to seed admin
- Status: USER VERIFICATION PENDING

---

## MEDIUM (P2):

### 3. Code Refactoring Needed
- `server.py` (7,245 lines) → split into route modules
- `App.js` (4,500+ lines) → split into page components

### 4. PDF Extraction Flaws
- `fill_blanks`: wrong format
- `match_following`: missing `correct_matches` sometimes
- File: `/app/backend/app/services/gpt4o_extraction.py`

---

## LOW (P3):

### 5. Redis Not Connected (optional enhancement)
### 6. Automated Testing Suite (not started)

---

# 9. PENDING TASKS

## Immediate Priority:

### 1. Fix Login/Logout Bug (P0)
- Deep debug auth state lifecycle in App.js
- Trace token through localStorage → interceptor → API call
- Ensure cleanup of Axios interceptors
- Test login/logout/re-login cycle for all roles
- **Estimated Time:** 2-4 hours

### 2. EC2 Dashboard Verification (P1)
- Confirm with user that `init_ec2_admin.py` resolved the issue
- **Estimated Time:** 15 minutes

## Medium Priority:

### 3. Code Refactoring (P1)
- Backend: Split server.py into `routes/student.py`, `routes/teacher.py`, `routes/admin.py`
- Frontend: Split App.js into page components
- **Estimated Time:** 4-6 hours

### 4. Fix PDF Extraction Flaws (P2)
- Update prompts in `gpt4o_extraction.py`
- **Estimated Time:** 1-2 hours

## Future/Backlog:

### 5. Redis Caching (P3) - 2-3 hours
### 6. Automated Testing Suite (P3) - 8-10 hours
### 7. Mobile App (Future) - 100+ hours

---

# 10. TECHNICAL ARCHITECTURE

## System Architecture:
```
┌──────────────────────────────────────────────────────────────┐
│                        USERS                                  │
│  Admin | Teachers | Students | Parents                       │
└──────────────────┬───────────────────────────────────────────┘
                   │ HTTPS
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                 FRONTEND (React 19)                           │
│  App.js + 13 components | TailwindCSS | Axios + Bearer Token │
└──────────────────┬───────────────────────────────────────────┘
                   │ REST API (/api/*)
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                 BACKEND (FastAPI)                             │
│  server.py | JWT (Cookie + Bearer) | BackgroundTasks         │
└───┬──────────────┬──────────────┬──────────────┬────────────┘
    │              │              │              │
    ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌───────────┐  ┌────────────┐
│PostgreSQL│  │ AWS S3   │  │ OpenRouter│  │ Background │
│  (RDS)   │  │ (PDFs)   │  │    AI     │  │  Workers   │
└─────────┘  └──────────┘  └───────────┘  └────────────┘
```

## Authentication Flow:
```
1. User submits login form → POST /api/auth/login {roll_no, password}
2. Backend validates → returns {token, user} in response body
3. Frontend stores token in localStorage
4. Axios interceptor reads localStorage on EVERY request
5. Adds header: Authorization: Bearer <token>
6. Backend get_current_user() checks Bearer header first, then Cookie
7. On logout: localStorage.removeItem('auth_token') + POST /api/auth/logout
```

## Key API Endpoints:

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| POST | `/api/admin/login` | Admin login | None |
| POST | `/api/auth/login` | Student/Teacher login | None |
| POST | `/api/auth/register-teacher` | Public teacher registration | None |
| GET | `/api/auth/me` | Get current user | Bearer/Cookie |
| POST | `/api/admin/register-student` | Register any user role | Admin |
| GET | `/api/homework?standard=X` | List homework | Bearer |
| GET | `/api/homework/{id}/questions` | Get homework questions | Bearer |
| POST | `/api/homework/{id}/evaluate-answer` | AI check answer | Bearer |
| POST | `/api/homework/{id}/help` | AI hint | Bearer |
| POST | `/api/homework` | Upload homework PDF | Teacher |
| GET | `/api/homework/{id}/extraction-status` | Poll extraction progress | Bearer |

## Database Schema (Key Tables):

| Table | Key Columns |
|-------|-------------|
| `users` | id (UUID), email, phone, password_hash, role, is_active |
| `student_profiles` | user_id, roll_no, standard, school_name, gender |
| `chapters` | id, subject_id, name, standard, school_name, ai_status, ai_generated |
| `homework` | id, subject_id, standard, title, file_path, extraction_status |
| `homework_questions` | id, homework_id, question_number, question_type, question_text, options, correct_answer |
| `tests` | id, subject_id, standard, title, duration_minutes |

**Note on options format:** The `options` field for MCQ questions is stored as a JSON dict (`{a: "val1", b: "val2"}`), not an array. Frontend components must convert this to an array for rendering.

---

# 11. TROUBLESHOOTING GUIDE

## Backend Not Starting:
```bash
tail -n 100 /var/log/supervisor/backend.err.log
# Common: missing .env, invalid DATABASE_URL, missing packages
```

## Frontend Build Errors:
```bash
tail -n 50 /var/log/supervisor/frontend.out.log
# If babel plugin crash: restart frontend (sudo supervisorctl restart frontend)
# Missing module: cd /app/frontend && yarn install
```

## Login Fails in Browser (But Works via curl):
- This is the Known Issue #1 (auth state bug)
- **Workaround**: Open browser console, run:
  ```js
  // Get token
  fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({roll_no:'S001',password:'123456'})}).then(r=>r.json()).then(d=>{localStorage.setItem('auth_token',d.token);location.reload()})
  ```

## AI Content Generation Fails:
```bash
# Check OpenRouter API key
curl -s "https://openrouter.ai/api/v1/auth/key" \
  -H "Authorization: Bearer $(grep OPENROUTER_API_KEY /app/backend/.env | cut -d= -f2)"
# Look for: "limit_remaining" > 0
# If "User not found" → key is expired, get new one from openrouter.ai/keys
```

## MCQ Options Not Showing:
- Check if `question.options` is a dict (e.g., `{a: "7", b: "70"}`)
- `QuestionRenderer.jsx` and `StudentContentViewer.jsx` now handle this
- If still broken, check the component is using the latest code

## White/Invisible Text:
- Body has `color: #F8FAFC` (near-white) for dark theme
- Any white-background card needs explicit `color: #1e293b` override
- Already fixed in `HomeworkAnswering.css` and `StudentContentViewer.css`
- If found elsewhere, add similar dark text override

## GitHub Actions CI/CD:
- Workflow: `.github/workflows/deploy-to-ec2.yml`
- Requires GitHub Secrets: `EC2_HOST`, `EC2_USERNAME`, `EC2_SSH_KEY`
- EC2 uses Python venv at `/home/ubuntu/studybuddy/venv`
- Node.js v20 required on EC2

---

# 12. IMPORTANT CONTEXT

## Credentials:

| System | Username/Key | Password/Value |
|--------|-------------|----------------|
| Admin | `admin` | `Admin@123` |
| Test Teacher | roll_no: `T001` | `123456` |
| Test Student | roll_no: `S001` | `123456` |
| EC2 SSH | `ubuntu@13.201.25.124` | DhruvStar_key.pem |

## Separate Databases:
- **Emergent Preview** and **EC2 Production** have completely separate PostgreSQL databases
- Data created in one does NOT appear in the other
- Use `init_ec2_admin.py` for fresh EC2 database

## Custom Branding Assets:
- `/frontend/public/studybuddy-icon.png` - Atom/math icon (used in header + login)
- `/frontend/public/studybuddy-banner.png` - STUDYBUDDY circular logo (teacher banner)
- Google Font: Dancing Script (calligraphic tagline)

## Multi-Tenancy:
- All data isolated by `school_name`
- Teachers create school namespace
- Students must be registered under an existing teacher's school
- Registration flow: Admin creates teacher → Teacher's school exists → Admin creates students under that school

## Business Context:
- Target: Private K-12 schools in India
- Pricing: Rs 200-300/student/year (SaaS)
- Key value: Save teachers 400+ hours/year, improve results 12-15%
- Schools are interested — CI/CD and polish are critical for demos

---

# 13. CHANGE LOG

## Version 2.0 (March 15, 2026)

### CI/CD & Infrastructure:
- Fixed GitHub Actions deployment pipeline (SSH, venv, Node.js v20)
- Created Nginx upload limit script (`configure-nginx.sh` → 30MB)
- Created EC2 admin seeder (`init_ec2_admin.py`)

### Authentication:
- Implemented dual auth (Cookie + Bearer Token)
- Added Bearer token in login response body
- Added Axios interceptor for localStorage token
- Created public teacher registration endpoint
- **Bug**: Login state lifecycle still broken (P0)

### Branding & UI:
- Replaced all "Dhruv Star" logos with custom StudyBuddy assets
- Header: single atom/math icon (56px)
- Login page: atom icon on all 4 auth screens
- Teacher banner: circular STUDYBUDDY logo (220px) + calligraphic tagline
- Hidden "Made with Emergent" badge
- Progress bar UI: removed stage/elapsed box, friendlier text

### Bug Fixes:
- MCQ dict-format options → array conversion (QuestionRenderer + StudentContentViewer)
- Auto-detect MCQ type when question_type is null
- White text on white backgrounds fixed (HomeworkAnswering.css, StudentContentViewer.css)
- Teacher dropdown shows "Teacher" not "Student" (ProfileDropdown.jsx)
- Updated OpenRouter API key (old was expired)

## Version 1.0 (March 7, 2026)
- Initial handover document
- All core features built
- CI/CD setup in progress

---

# QUICK START CHECKLIST

For a new agent picking up this project:

- [ ] Clone repository from GitHub
- [ ] Create backend/.env and frontend/.env with actual credentials
- [ ] `pip install -r backend/requirements.txt`
- [ ] `cd frontend && yarn install`
- [ ] `sudo supervisorctl restart all`
- [ ] Verify: `curl $API_URL/api/` returns API status
- [ ] Verify: frontend compiles (`tail /var/log/supervisor/frontend.out.log`)
- [ ] Test admin login via curl
- [ ] Read Known Issues section (especially Login Bug #1)
- [ ] Check with user for current priority

---

**Document End**
**Version:** 2.0 | **Updated:** March 15, 2026 | **Words:** ~5,000
