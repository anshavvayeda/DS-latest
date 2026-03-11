# StudyBuddy - K-12 Learning Management System

## Original Problem Statement
Set up the StudyBuddy project from GitHub repo `https://github.com/anshavvayeda/DS-latest`, debug CI/CD pipeline for EC2 deployment, and fix known application issues.

## Tech Stack
- **Backend**: FastAPI + PostgreSQL (AWS RDS)
- **Frontend**: React
- **AI**: OpenRouter API (Claude Sonnet 4.5, Gemini 2.5 Flash)
- **Storage**: AWS S3
- **Deployment**: GitHub Actions → EC2 (Nginx + systemd)
- **Auth**: JWT (Cookie + Bearer Token dual system)

## Completed Tasks
- [x] Project setup from GitHub repo
- [x] CI/CD pipeline fix (GitHub Actions → EC2)
- [x] Node.js upgrade on EC2 (v18 → v20)
- [x] File upload fix (30MB limit via Nginx)
- [x] Authentication flow overhaul (dual Cookie + Bearer)
- [x] Public teacher registration endpoint
- [x] EC2 admin seeding script (`init_ec2_admin.py`)
- [x] **Brand logo replacement** — Replaced all old "Dhruv Star" logos with new StudyBuddy lightbulb mascot (2026-03-11)
- [x] **Header brand consolidation** — Merged two header images into single combined brand image (`studybuddy-brand.png`) (2026-03-11)
- [x] **Banner resize + tagline** — Reduced center mascot to 75% and added "Smart Learning powered by AI" tagline (2026-03-11)

## In Progress / Pending Issues
- **P0**: Critical login/logout bug — login fails, gets stuck, or logs into wrong user after admin logout
- **P1**: EC2 admin dashboard appears empty (separate DB — user verification pending)

## Upcoming Tasks
- **P1**: Code refactoring — split monolithic `server.py` (7,245 lines) and `App.js` (4,256 lines)
- **P2**: Fix PDF extraction flaws (fill_blanks, match_following formatting)
- **P3**: Redis caching
- **P3**: Automated testing suite

## Key Files
- `/app/backend/server.py` — Main FastAPI app
- `/app/frontend/src/App.js` — Main React app
- `/app/.github/workflows/deploy-to-ec2.yml` — CI/CD workflow
- `/app/frontend/public/studybuddy-logo.png` — Brand logo

## Credentials
- **Admin**: username `admin`, password `Admin@123`
- **Teacher/Student**: Registered through the application
