# =============================================================================
# PRODUCTION MIGRATION GUIDE
# FastAPI Backend → AWS EC2 + RDS
# =============================================================================
# Version: 1.0
# Date: February 2026
# Architecture: FastAPI + asyncpg + Alembic + Gunicorn + Nginx + RDS PostgreSQL
# =============================================================================

# TABLE OF CONTENTS
# -----------------
# Phase 1 – Local Preparation
# Phase 2 – RDS Schema Validation
# Phase 3 – EC2 Deployment
# Phase 4 – Production Hardening
# Phase 5 – Monitoring & Backup
# Appendix A – Failure Scenarios & Fixes
# Appendix B – Rollback Procedures
# Appendix C – Optional Components

# =============================================================================
# PHASE 1 – LOCAL PREPARATION
# =============================================================================

## 1.1 Verify Local Environment

```bash
# Check Python version (must be 3.12)
python3 --version

# Check installed packages
pip list | grep -E "fastapi|sqlalchemy|asyncpg|alembic|gunicorn|uvicorn"

# Expected output:
# alembic              1.18.x
# asyncpg              0.30.x
# fastapi              0.115.x
# gunicorn             25.x.x
# sqlalchemy           2.0.x
# uvicorn              0.25.x
```

## 1.2 Verify Alembic Configuration

```bash
# Check current migration state
cd /path/to/backend
alembic current

# View migration history
alembic history --verbose

# Verify no pending migrations
alembic check
# Expected: "No new upgrade operations detected."
```

## 1.3 Validate Schema Locally

```bash
# Generate SQL without executing (offline mode)
alembic upgrade head --sql > schema_review.sql

# Review the SQL file
cat schema_review.sql
```

## 1.4 Prepare Production Files

Create the following directory structure:
```
backend/
├── server.py                 # FastAPI app
├── requirements.txt          # Dependencies
├── .env.example             # Template (commit this)
├── .env                     # Secrets (DO NOT commit)
├── alembic.ini              # Alembic config
├── alembic/                 # Migrations
├── gunicorn.conf.py         # Gunicorn config
├── app/
│   ├── models/
│   ├── services/
│   └── ...
├── deploy/
│   ├── studybuddy.service   # systemd
│   ├── nginx.conf           # Nginx
│   └── s3-lifecycle.json    # S3 lifecycle policy
├── logs/                    # Application logs
└── tmp/                     # Temp files (NOT /app)
```

## 1.5 Update requirements.txt

```bash
# Freeze current dependencies
pip freeze > requirements.txt

# Verify critical packages are present
grep -E "asyncpg|sqlalchemy|alembic|fastapi|gunicorn|uvicorn|python-dotenv" requirements.txt
```

# =============================================================================
# PHASE 2 – RDS SCHEMA VALIDATION
# =============================================================================

## 2.1 Production .env Template

Create `/path/to/backend/.env.example`:
```
# =============================================================================
# PRODUCTION ENVIRONMENT VARIABLES
# =============================================================================
# Copy to .env and fill in values. NEVER commit .env to version control.
# =============================================================================

# -----------------------------------------------------------------------------
# DATABASE (Required)
# -----------------------------------------------------------------------------
# IMPORTANT: Use ssl=true for asyncpg (NOT sslmode=require)
DATABASE_URL=postgresql+asyncpg://USERNAME:PASSWORD@RDS_ENDPOINT:5432/DBNAME?ssl=true

# -----------------------------------------------------------------------------
# AUTHENTICATION (Required)
# -----------------------------------------------------------------------------
JWT_SECRET=generate-with-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# -----------------------------------------------------------------------------
# ADMIN (Required)
# -----------------------------------------------------------------------------
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-admin-password

# -----------------------------------------------------------------------------
# AWS S3 (Required)
# -----------------------------------------------------------------------------
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=ap-south-1

# -----------------------------------------------------------------------------
# AI SERVICE (Required for AI features)
# -----------------------------------------------------------------------------
OPENROUTER_API_KEY=your-openrouter-key

# -----------------------------------------------------------------------------
# TEMP DIRECTORY (Required)
# -----------------------------------------------------------------------------
# Must be writable by application user. DO NOT use /app
TEMP_DIR=/home/ubuntu/studybuddy/backend/tmp

# -----------------------------------------------------------------------------
# REDIS (Optional)
# -----------------------------------------------------------------------------
# Leave empty if Redis not installed - app will function without caching
REDIS_URL=

# -----------------------------------------------------------------------------
# ENVIRONMENT (Required)
# -----------------------------------------------------------------------------
ENV=production
MOCK_OTP_MODE=false
LOG_LEVEL=INFO
```

## 2.2 Test RDS Connectivity

```bash
# Create test script
cat > test_rds_connection.py << 'EOF'
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)
    
    # Mask password in output
    masked_url = db_url.split('@')[0].split(':')[0] + ':***@' + db_url.split('@')[1]
    print(f"Connecting to: {masked_url}")
    
    # Verify ssl=true is in URL
    if 'ssl=true' not in db_url:
        print("⚠️  WARNING: ssl=true not found in DATABASE_URL")
        print("   asyncpg requires ssl=true, not sslmode=require")
    
    try:
        engine = create_async_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
        
        async with engine.connect() as conn:
            # Test basic connectivity
            result = await conn.execute(text('SELECT 1'))
            print(f"✅ Basic connectivity: OK")
            
            # Check PostgreSQL version
            result = await conn.execute(text('SELECT version()'))
            version = result.scalar()
            print(f"✅ PostgreSQL version: {version[:50]}...")
            
            # Check SSL status
            result = await conn.execute(text('SHOW ssl'))
            ssl_status = result.scalar()
            print(f"✅ SSL enabled: {ssl_status}")
            
        await engine.dispose()
        print("\n✅ RDS connection test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Connection FAILED: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
EOF

# Run test
python3 test_rds_connection.py
```

## 2.3 Deploy Schema to RDS

```bash
# Step 1: Backup current state (if any)
alembic current

# Step 2: Run migrations
alembic upgrade head

# Step 3: Verify migration applied
alembic current
# Expected: Shows latest revision ID with "(head)"

# Step 4: Verify tables created
cat > verify_schema.py << 'EOF'
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def verify_schema():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    
    async with engine.connect() as conn:
        # List all tables
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]
        
        print(f"Tables found: {len(tables)}")
        for table in tables:
            print(f"  - {table}")
        
        # Verify minimum expected tables
        expected_min = 22
        if len(tables) >= expected_min:
            print(f"\n✅ Schema verification PASSED ({len(tables)} tables)")
        else:
            print(f"\n⚠️  WARNING: Only {len(tables)} tables found (expected {expected_min}+)")
    
    await engine.dispose()

asyncio.run(verify_schema())
EOF

python3 verify_schema.py
```

## 2.4 Verify Foreign Key Constraints

```bash
cat > verify_fk.py << 'EOF'
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def verify_fk():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rc 
                ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """))
        
        fks = result.fetchall()
        print(f"Foreign keys found: {len(fks)}")
        
        cascade_count = sum(1 for fk in fks if fk[2] == 'CASCADE')
        set_null_count = sum(1 for fk in fks if fk[2] == 'SET NULL')
        no_action_count = sum(1 for fk in fks if fk[2] == 'NO ACTION')
        
        print(f"  CASCADE: {cascade_count}")
        print(f"  SET NULL: {set_null_count}")
        print(f"  NO ACTION: {no_action_count}")
        
        if no_action_count == 0:
            print("\n✅ All FKs have explicit ON DELETE rules")
        else:
            print(f"\n⚠️  WARNING: {no_action_count} FKs have NO ACTION")
    
    await engine.dispose()

asyncio.run(verify_fk())
EOF

python3 verify_fk.py
```

## 2.5 Verify Indexes

```bash
cat > verify_indexes.py << 'EOF'
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def verify_indexes():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT 
                tablename,
                indexname
            FROM pg_indexes 
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """))
        
        indexes = result.fetchall()
        print(f"Indexes found: {len(indexes)}")
        
        # Check for critical indexes
        critical = ['idx_chapters_ai_status', 'idx_users_created_at', 
                   'idx_test_submissions_created_at', 'idx_homework_submissions_created_at']
        
        index_names = [idx[1] for idx in indexes]
        
        for idx in critical:
            if idx in index_names:
                print(f"  ✅ {idx}")
            else:
                print(f"  ❌ MISSING: {idx}")
    
    await engine.dispose()

asyncio.run(verify_indexes())
EOF

python3 verify_indexes.py
```

# =============================================================================
# PHASE 3 – EC2 DEPLOYMENT
# =============================================================================

## 3.1 Gunicorn Configuration

Create `gunicorn.conf.py`:
```python
# =============================================================================
# Gunicorn Production Configuration
# =============================================================================
# Optimized for AWS EC2 t3.small / t3.medium
# =============================================================================

import os

# -----------------------------------------------------------------------------
# Server Socket
# -----------------------------------------------------------------------------
# IMPORTANT: Bind to 127.0.0.1 only - Nginx handles public traffic
bind = "127.0.0.1:8000"
backlog = 2048

# -----------------------------------------------------------------------------
# Worker Configuration
# -----------------------------------------------------------------------------
workers = int(os.getenv("GUNICORN_WORKERS", 4))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
threads = 1

# -----------------------------------------------------------------------------
# Timeouts
# -----------------------------------------------------------------------------
timeout = 120
graceful_timeout = 30
keepalive = 5

# -----------------------------------------------------------------------------
# Process
# -----------------------------------------------------------------------------
proc_name = "studybuddy"
pidfile = "/tmp/gunicorn-studybuddy.pid"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
errorlog = "-"
accesslog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# -----------------------------------------------------------------------------
# Temp Directory
# -----------------------------------------------------------------------------
# Use application-specific temp directory, NOT /app
worker_tmp_dir = os.getenv("TEMP_DIR", "/home/ubuntu/studybuddy/backend/tmp")
```

## 3.2 Systemd Service File

Create `deploy/studybuddy.service`:
```ini
[Unit]
Description=StudyBuddy FastAPI Backend
Documentation=https://github.com/yourusername/studybuddy
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/studybuddy/backend

# Environment
Environment="PATH=/home/ubuntu/studybuddy/backend/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/home/ubuntu/studybuddy/backend/.env

# Temp directory (required for asyncpg and file operations)
Environment="TEMP_DIR=/home/ubuntu/studybuddy/backend/tmp"
Environment="TMPDIR=/home/ubuntu/studybuddy/backend/tmp"

# Start command
ExecStart=/home/ubuntu/studybuddy/backend/venv/bin/gunicorn \
    --config /home/ubuntu/studybuddy/backend/gunicorn.conf.py \
    server:app

# Lifecycle
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10
StartLimitInterval=0

# Resource Limits
LimitNOFILE=65536
LimitNPROC=4096

# Security
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=strict
ReadWritePaths=/home/ubuntu/studybuddy/backend/tmp
ReadWritePaths=/home/ubuntu/studybuddy/backend/logs
ReadWritePaths=/home/ubuntu/studybuddy/backend/uploads

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=studybuddy

# Timeouts
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

## 3.3 Nginx Configuration

Create `deploy/nginx.conf`:
```nginx
# =============================================================================
# Nginx Configuration for StudyBuddy
# =============================================================================
# File: /etc/nginx/sites-available/studybuddy
# =============================================================================

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

# Upstream (internal only - not publicly accessible)
upstream studybuddy {
    server 127.0.0.1:8000 fail_timeout=0;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1000;
    gzip_types application/json application/javascript text/css text/plain text/xml;

    # Client limits
    client_max_body_size 50M;
    client_body_buffer_size 128k;

    # Health check (no rate limiting)
    location = /health {
        proxy_pass http://studybuddy;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        access_log off;
    }

    # Auth endpoints (strict rate limiting)
    location ~ ^/api/(auth|admin/login) {
        limit_req zone=auth burst=5 nodelay;
        
        proxy_pass http://studybuddy;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # API endpoints
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://studybuddy;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Root path
    location / {
        proxy_pass http://studybuddy;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Logging
    access_log /var/log/nginx/studybuddy_access.log;
    error_log /var/log/nginx/studybuddy_error.log;
}
```

## 3.4 EC2 Deployment Commands

```bash
# =============================================================================
# EXECUTE ON EC2 INSTANCE
# =============================================================================

# Step 1: SSH into EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Step 2: Update system
sudo apt update && sudo apt upgrade -y

# Step 3: Install system dependencies
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    git \
    nginx \
    curl \
    htop \
    build-essential \
    libpq-dev \
    postgresql-client

# Step 4: Create application directory
sudo mkdir -p /home/ubuntu/studybuddy
sudo chown -R ubuntu:ubuntu /home/ubuntu/studybuddy

# Step 5: Upload/clone code
cd /home/ubuntu/studybuddy
git clone YOUR_REPO_URL .
# OR: scp -r ./backend ubuntu@EC2_IP:/home/ubuntu/studybuddy/

# Step 6: Create required directories
cd /home/ubuntu/studybuddy/backend
mkdir -p tmp logs uploads

# Step 7: Set directory permissions
chmod 755 tmp logs uploads

# Step 8: Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Step 9: Upgrade pip
pip install --upgrade pip wheel setuptools

# Step 10: Install dependencies
pip install -r requirements.txt

# Step 11: Create .env file
cp .env.example .env
nano .env  # Fill in production values

# Step 12: Secure .env
chmod 600 .env

# Step 13: Test database connection
python3 test_rds_connection.py

# Step 14: Run migrations (if not already done)
alembic upgrade head
alembic current

# Step 15: Install systemd service
sudo cp deploy/studybuddy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable studybuddy

# Step 16: Start service
sudo systemctl start studybuddy
sudo systemctl status studybuddy

# Step 17: Install Nginx config
sudo cp deploy/nginx.conf /etc/nginx/sites-available/studybuddy
sudo ln -sf /etc/nginx/sites-available/studybuddy /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Step 18: Test and reload Nginx
sudo nginx -t
sudo systemctl reload nginx

# Step 19: Verify deployment
curl http://localhost/health
curl http://YOUR_EC2_PUBLIC_IP/health
```

# =============================================================================
# PHASE 4 – PRODUCTION HARDENING
# =============================================================================

## 4.1 EC2 Security Group Configuration

```
INBOUND RULES:
┌──────────┬──────────┬─────────────────────┬──────────────────────────────┐
│ Type     │ Port     │ Source              │ Description                  │
├──────────┼──────────┼─────────────────────┼──────────────────────────────┤
│ SSH      │ 22       │ YOUR_IP/32          │ Admin SSH access only        │
│ HTTP     │ 80       │ 0.0.0.0/0           │ Public web traffic           │
│ HTTPS    │ 443      │ 0.0.0.0/0           │ Public web traffic (SSL)     │
└──────────┴──────────┴─────────────────────┴──────────────────────────────┘

OUTBOUND RULES:
┌──────────┬──────────┬─────────────────────┬──────────────────────────────┐
│ Type     │ Port     │ Destination         │ Description                  │
├──────────┼──────────┼─────────────────────┼──────────────────────────────┤
│ All      │ All      │ 0.0.0.0/0           │ Allow all outbound           │
└──────────┴──────────┴─────────────────────┴──────────────────────────────┘

⚠️  IMPORTANT: Port 8000 must NOT be in inbound rules!
    Gunicorn binds to 127.0.0.1:8000 (localhost only)
    All public traffic goes through Nginx on port 80/443
```

## 4.2 RDS Security Group Configuration

```
INBOUND RULES:
┌──────────────┬──────────┬─────────────────────┬────────────────────────────┐
│ Type         │ Port     │ Source              │ Description                │
├──────────────┼──────────┼─────────────────────┼────────────────────────────┤
│ PostgreSQL   │ 5432     │ sg-xxxxx (EC2 SG)   │ EC2 to RDS only            │
└──────────────┴──────────┴─────────────────────┴────────────────────────────┘

⚠️  IMPORTANT: 
    - Source must be EC2 Security Group ID, NOT 0.0.0.0/0
    - RDS should NOT be publicly accessible unless absolutely required
```

## 4.3 Temp Directory Fix

The application must NOT use `/app` as temp directory (permission issues in production).

```bash
# Create temp directory
mkdir -p /home/ubuntu/studybuddy/backend/tmp
chmod 755 /home/ubuntu/studybuddy/backend/tmp

# Verify in .env
grep TEMP_DIR /home/ubuntu/studybuddy/backend/.env
# Expected: TEMP_DIR=/home/ubuntu/studybuddy/backend/tmp

# Verify systemd has TMPDIR set
grep TMPDIR /etc/systemd/system/studybuddy.service
# Expected: Environment="TMPDIR=/home/ubuntu/studybuddy/backend/tmp"
```

Update application code if needed:
```python
# In your storage_service.py or similar
import os
import tempfile

# Get temp directory from environment
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp')

# Ensure it exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Use it for temp files
def get_temp_file():
    return tempfile.NamedTemporaryFile(dir=TEMP_DIR, delete=False)
```

## 4.4 S3 Lifecycle Policy (Corrected)

Create `deploy/s3-lifecycle.json`:
```json
{
    "Rules": [
        {
            "ID": "DeleteOldTempFiles",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "temp/"
            },
            "Expiration": {
                "Days": 7
            }
        },
        {
            "ID": "TransitionOldUploadsToIA",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "uploads/"
            },
            "Transitions": [
                {
                    "Days": 90,
                    "StorageClass": "STANDARD_IA"
                }
            ]
        },
        {
            "ID": "DeleteOldAICache",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "ai_cache/"
            },
            "Expiration": {
                "Days": 30
            }
        }
    ]
}
```

Apply lifecycle policy:
```bash
aws s3api put-bucket-lifecycle-configuration \
    --bucket YOUR_BUCKET_NAME \
    --lifecycle-configuration file://deploy/s3-lifecycle.json
```

⚠️  **IMPORTANT**: The parameter name is `"ID"` (uppercase), not `"Id"`.

## 4.5 Production Validation Checklist

```bash
#!/bin/bash
# Save as: validate_production.sh

echo "=== PRODUCTION VALIDATION CHECKLIST ==="
echo ""

# 1. Check service status
echo "1. Service Status:"
sudo systemctl is-active studybuddy && echo "   ✅ Service running" || echo "   ❌ Service not running"

# 2. Check Nginx status
echo ""
echo "2. Nginx Status:"
sudo systemctl is-active nginx && echo "   ✅ Nginx running" || echo "   ❌ Nginx not running"

# 3. Check health endpoint
echo ""
echo "3. Health Endpoint:"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)
[ "$HEALTH" = "200" ] && echo "   ✅ Health check passed" || echo "   ❌ Health check failed (HTTP $HEALTH)"

# 4. Check port 8000 is NOT publicly accessible
echo ""
echo "4. Port 8000 Security:"
PUBLIC_IP=$(curl -s ifconfig.me)
PORT_8000=$(curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" http://$PUBLIC_IP:8000/health 2>/dev/null)
[ "$PORT_8000" = "000" ] && echo "   ✅ Port 8000 not publicly accessible" || echo "   ❌ WARNING: Port 8000 is accessible!"

# 5. Check SSL to database
echo ""
echo "5. Database SSL:"
source /home/ubuntu/studybuddy/backend/venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/studybuddy/backend/.env')
url = os.getenv('DATABASE_URL', '')
if 'ssl=true' in url:
    print('   ✅ SSL enabled in DATABASE_URL')
else:
    print('   ❌ SSL not configured!')
"

# 6. Check .env permissions
echo ""
echo "6. Environment File Security:"
PERM=$(stat -c "%a" /home/ubuntu/studybuddy/backend/.env)
[ "$PERM" = "600" ] && echo "   ✅ .env has correct permissions (600)" || echo "   ⚠️  .env permissions: $PERM (should be 600)"

# 7. Check temp directory
echo ""
echo "7. Temp Directory:"
[ -d "/home/ubuntu/studybuddy/backend/tmp" ] && echo "   ✅ Temp directory exists" || echo "   ❌ Temp directory missing"
[ -w "/home/ubuntu/studybuddy/backend/tmp" ] && echo "   ✅ Temp directory writable" || echo "   ❌ Temp directory not writable"

# 8. Check logs directory
echo ""
echo "8. Logs Directory:"
[ -d "/home/ubuntu/studybuddy/backend/logs" ] && echo "   ✅ Logs directory exists" || echo "   ❌ Logs directory missing"

# 9. Check database tables
echo ""
echo "9. Database Schema:"
python3 -c "
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv('/home/ubuntu/studybuddy/backend/.env')

async def check():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'\"))
        count = result.scalar()
        print(f'   Tables found: {count}')
        if count >= 22:
            print('   ✅ Schema complete')
        else:
            print('   ⚠️  Schema may be incomplete')
    await engine.dispose()

asyncio.run(check())
"

echo ""
echo "=== VALIDATION COMPLETE ==="
```

# =============================================================================
# PHASE 5 – MONITORING & BACKUP
# =============================================================================

## 5.1 RDS Snapshot Backup Strategy

### Manual Snapshot
```bash
aws rds create-db-snapshot \
    --db-instance-identifier database-1 \
    --db-snapshot-identifier studybuddy-manual-$(date +%Y%m%d-%H%M)
```

### List Snapshots
```bash
aws rds describe-db-snapshots \
    --db-instance-identifier database-1 \
    --query 'DBSnapshots[*].[DBSnapshotIdentifier,SnapshotCreateTime,Status]' \
    --output table
```

### Automated Backup Configuration
- Enable automated backups in RDS console
- Set retention period: 7 days minimum
- Set backup window: During low-traffic hours

## 5.2 Logging Best Practices

### Application Logs
```bash
# View live logs
sudo journalctl -u studybuddy -f

# View last 100 lines
sudo journalctl -u studybuddy -n 100

# View logs since today
sudo journalctl -u studybuddy --since today

# View error logs only
sudo journalctl -u studybuddy -p err

# Export logs to file
sudo journalctl -u studybuddy --since "2026-02-01" > backend_logs.txt
```

### Log Rotation
Systemd journal auto-rotates. For application logs:
```bash
# Create logrotate config
sudo tee /etc/logrotate.d/studybuddy << EOF
/home/ubuntu/studybuddy/backend/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 640 ubuntu ubuntu
    sharedscripts
    postrotate
        systemctl reload studybuddy > /dev/null 2>&1 || true
    endscript
}
EOF
```

## 5.3 Monitoring Best Practices

### Basic Monitoring Script
```bash
#!/bin/bash
# Save as: monitor.sh

echo "=== SYSTEM METRICS ==="
echo ""
echo "CPU & Memory:"
free -h
echo ""
echo "Disk Usage:"
df -h /
echo ""
echo "Top Processes:"
ps aux --sort=-%mem | head -6
echo ""
echo "=== APPLICATION METRICS ==="
echo ""
echo "Service Status:"
sudo systemctl status studybuddy --no-pager | head -10
echo ""
echo "Open Connections:"
ss -tuln | grep -E "8000|80|443"
echo ""
echo "Recent Errors:"
sudo journalctl -u studybuddy -p err --since "1 hour ago" --no-pager | tail -10
```

### CloudWatch Integration (Optional)
```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure (basic config)
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

## 5.4 Zero-Downtime Deployment Sequence

```bash
#!/bin/bash
# Save as: deploy_zero_downtime.sh

set -e

APP_DIR="/home/ubuntu/studybuddy/backend"
cd "$APP_DIR"

echo "=== ZERO-DOWNTIME DEPLOYMENT ==="

# 1. Pull latest code
echo "1. Pulling latest code..."
git fetch origin main
git checkout main
git pull origin main

# 2. Activate venv
source venv/bin/activate

# 3. Install dependencies (if any new)
echo "2. Installing dependencies..."
pip install -r requirements.txt --quiet

# 4. Run migrations (if any)
echo "3. Running migrations..."
alembic upgrade head

# 5. Graceful reload (zero-downtime)
echo "4. Graceful reload..."
sudo systemctl reload studybuddy

# 6. Health check
echo "5. Health check..."
sleep 3
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)
if [ "$HEALTH" = "200" ]; then
    echo "   ✅ Deployment successful!"
else
    echo "   ❌ Health check failed! Rolling back..."
    git checkout HEAD~1
    sudo systemctl restart studybuddy
    exit 1
fi

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
```

# =============================================================================
# APPENDIX A – FAILURE SCENARIOS & FIXES
# =============================================================================

## A.1 Service Won't Start

```bash
# Check detailed error
sudo journalctl -u studybuddy -n 50 --no-pager

# Common causes:
# 1. Missing .env file
ls -la /home/ubuntu/studybuddy/backend/.env

# 2. Wrong Python path
which python3
/home/ubuntu/studybuddy/backend/venv/bin/python3 --version

# 3. Missing dependencies
source venv/bin/activate
pip install -r requirements.txt

# 4. Port already in use
sudo lsof -i :8000
sudo kill -9 <PID>

# 5. Permission issues
ls -la /home/ubuntu/studybuddy/backend/
sudo chown -R ubuntu:ubuntu /home/ubuntu/studybuddy/backend/
```

## A.2 Database Connection Failed

```bash
# Check connection string
grep DATABASE_URL /home/ubuntu/studybuddy/backend/.env

# Test manually
source venv/bin/activate
python3 test_rds_connection.py

# Common causes:
# 1. Wrong ssl parameter (must be ssl=true, not sslmode=require)
# 2. Security group blocking access
# 3. RDS not publicly accessible
# 4. Wrong credentials
```

## A.3 502 Bad Gateway

```bash
# Check if Gunicorn is running
sudo systemctl status studybuddy

# Check Nginx error logs
sudo tail -f /var/log/nginx/studybuddy_error.log

# Check Nginx config
sudo nginx -t

# Restart services
sudo systemctl restart studybuddy
sudo systemctl reload nginx
```

## A.4 Slow Response Times

```bash
# Check database connections
psql -h YOUR_RDS_ENDPOINT -U postgres -d studybuddy -c "
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
"

# Check if pool is exhausted
# Increase pool_size in database.py if needed

# Check system resources
htop
free -m
df -h
```

## A.5 SSL/TLS Errors with RDS

```bash
# Verify DATABASE_URL has ssl=true (NOT sslmode=require)
grep DATABASE_URL .env

# WRONG:
# postgresql+asyncpg://user:pass@host:5432/db?sslmode=require

# CORRECT:
# postgresql+asyncpg://user:pass@host:5432/db?ssl=true

# asyncpg uses ssl=true parameter, not sslmode
```

# =============================================================================
# APPENDIX B – ROLLBACK PROCEDURES
# =============================================================================

## B.1 Schema-Only Rollback

```bash
# View current migration
alembic current

# View history
alembic history

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all (DANGEROUS - use only for complete reset)
alembic downgrade base
```

## B.2 Full Database Rollback from Snapshot

```bash
# 1. Stop application
sudo systemctl stop studybuddy

# 2. List available snapshots
aws rds describe-db-snapshots \
    --db-instance-identifier database-1 \
    --output table

# 3. Restore to new instance
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier database-1-restored \
    --db-snapshot-identifier YOUR_SNAPSHOT_ID

# 4. Wait for instance to be available
aws rds wait db-instance-available \
    --db-instance-identifier database-1-restored

# 5. Update .env with new endpoint
nano /home/ubuntu/studybuddy/backend/.env

# 6. Restart application
sudo systemctl start studybuddy
```

## B.3 Code Rollback

```bash
# View recent commits
git log --oneline -10

# Rollback to previous commit
git checkout HEAD~1

# Or rollback to specific commit
git checkout <commit_hash>

# Restart service
sudo systemctl restart studybuddy
```

# =============================================================================
# APPENDIX C – OPTIONAL COMPONENTS
# =============================================================================

## C.1 Redis Installation (Optional)

```bash
# Install Redis
sudo apt update
sudo apt install redis-server -y

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: supervised systemd
# Set: maxmemory 256mb
# Set: maxmemory-policy allkeys-lru

# Start Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Test Redis
redis-cli ping
# Expected: PONG

# Update .env
echo "REDIS_URL=redis://localhost:6379/0" >> /home/ubuntu/studybuddy/backend/.env

# Restart application
sudo systemctl restart studybuddy
```

⚠️  **Note**: Application should start without Redis. Verify graceful degradation:
```python
# In your code, handle Redis connection failure gracefully
try:
    redis_client = redis.Redis.from_url(REDIS_URL)
    redis_client.ping()
except:
    redis_client = None  # Caching disabled
```

## C.2 HTTPS Setup via Certbot

```bash
# Install Certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Test auto-renewal
sudo certbot renew --dry-run

# Certificate renewal is automatic via cron/systemd timer
```

## C.3 UFW Firewall Setup

```bash
# Enable UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status verbose

# ⚠️  Do NOT allow port 8000
```

# =============================================================================
# END OF MIGRATION GUIDE
# =============================================================================
