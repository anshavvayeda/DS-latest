# =============================================================================
# StudyBuddy Backend - Production Deployment Guide
# =============================================================================

## Quick Start

### Prerequisites
- AWS EC2 instance (Ubuntu 24.04 LTS)
- AWS RDS PostgreSQL 17
- Python 3.11+
- Domain name (optional, for SSL)

---

## Step-by-Step Deployment

### Step 1: SSH into EC2

```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
```

### Step 2: Run Initial Setup

```bash
# Download and run setup script
cd /home/ubuntu
git clone https://github.com/yourusername/studybuddy.git
cd studybuddy/backend
chmod +x deploy/setup-ec2.sh
./deploy/setup-ec2.sh
```

### Step 3: Configure Environment Variables

```bash
# Copy example and edit
cp .env.example .env
nano .env
```

**Fill in these required values:**
```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@your-rds-endpoint:5432/studybuddy
JWT_SECRET=your-generated-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-admin-password
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
S3_BUCKET_NAME=your-bucket
OPENROUTER_API_KEY=your-api-key
ENV=production
```

### Step 4: Run Database Migrations

```bash
cd /home/ubuntu/studybuddy/backend
source venv/bin/activate
alembic upgrade head
```

### Step 5: Start the Service

```bash
sudo systemctl start studybuddy
sudo systemctl status studybuddy
```

### Step 6: Verify Deployment

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check Nginx
curl http://your-ec2-ip/health

# Check logs
sudo journalctl -u studybuddy -f
```

---

## File Locations

| File | Location |
|------|----------|
| Application | `/home/ubuntu/studybuddy/backend/` |
| Virtual Environment | `/home/ubuntu/studybuddy/backend/venv/` |
| Environment Variables | `/home/ubuntu/studybuddy/backend/.env` |
| Logs | `/home/ubuntu/studybuddy/backend/logs/` |
| Systemd Service | `/etc/systemd/system/studybuddy.service` |
| Nginx Config | `/etc/nginx/sites-available/studybuddy` |
| Gunicorn Config | `/home/ubuntu/studybuddy/backend/gunicorn.conf.py` |

---

## Common Commands

```bash
# Service management
sudo systemctl start studybuddy
sudo systemctl stop studybuddy
sudo systemctl restart studybuddy
sudo systemctl status studybuddy

# View logs
sudo journalctl -u studybuddy -f          # Follow logs
sudo journalctl -u studybuddy -n 100      # Last 100 lines
sudo journalctl -u studybuddy --since today

# Deploy updates
cd /home/ubuntu/studybuddy/backend
./deploy/deploy.sh

# Quick restart (skip git pull and deps)
./deploy/deploy.sh --restart-only

# Nginx
sudo nginx -t                              # Test config
sudo systemctl reload nginx                # Reload
sudo systemctl restart nginx               # Restart

# Database migrations
source venv/bin/activate
alembic upgrade head                       # Apply migrations
alembic current                            # Check current version
alembic history                            # View history
```

---

## SSL Setup (Optional)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
sudo certbot renew --dry-run
```

---

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u studybuddy -n 50

# Check .env file exists and is readable
cat /home/ubuntu/studybuddy/backend/.env

# Test manually
cd /home/ubuntu/studybuddy/backend
source venv/bin/activate
python -c "import server; print('OK')"
```

### Database connection failed
```bash
# Test connection
cd /home/ubuntu/studybuddy/backend
source venv/bin/activate
python -c "
from app.models.database import engine
import asyncio
async def test():
    async with engine.connect() as conn:
        print('Connected!')
asyncio.run(test())
"
```

### Nginx errors
```bash
sudo nginx -t
sudo tail -f /var/log/nginx/studybuddy_error.log
```

---

## Monitoring

### Health Check
```bash
# Basic health
curl http://localhost:8000/health

# From outside (via Nginx)
curl http://your-domain.com/health
```

### Resource Usage
```bash
htop
free -m
df -h
```

### Database Connections
```bash
# Check active connections
psql -h your-rds-endpoint -U postgres -d studybuddy -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Security Checklist

- [ ] `.env` file has restricted permissions (`chmod 600 .env`)
- [ ] RDS security group allows only EC2 security group
- [ ] EC2 security group allows only ports 22, 80, 443
- [ ] SSL certificate installed
- [ ] Strong JWT_SECRET (32+ characters)
- [ ] Strong ADMIN_PASSWORD
- [ ] MOCK_OTP_MODE=false in production
- [ ] Regular backups configured

---

## Backup & Recovery

### Manual RDS Snapshot
```bash
aws rds create-db-snapshot \
    --db-instance-identifier database-1 \
    --db-snapshot-identifier manual-backup-$(date +%Y%m%d)
```

### Export Environment
```bash
cp /home/ubuntu/studybuddy/backend/.env /home/ubuntu/backup/.env.backup
```
