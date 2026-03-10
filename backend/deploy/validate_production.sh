#!/bin/bash
# =============================================================================
# Production Validation Script
# =============================================================================
# Run this after deployment to verify everything is working
# Usage: ./validate_production.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_DIR="/home/ubuntu/studybuddy/backend"

echo "=============================================="
echo "  PRODUCTION VALIDATION"
echo "  $(date)"
echo "=============================================="

# 1. Service Status
echo ""
echo "1. Service Status:"
if sudo systemctl is-active --quiet studybuddy; then
    echo -e "   ${GREEN}✅ studybuddy service running${NC}"
else
    echo -e "   ${RED}❌ studybuddy service NOT running${NC}"
    exit 1
fi

# 2. Nginx Status
echo ""
echo "2. Nginx Status:"
if sudo systemctl is-active --quiet nginx; then
    echo -e "   ${GREEN}✅ nginx running${NC}"
else
    echo -e "   ${RED}❌ nginx NOT running${NC}"
fi

# 3. Health Endpoint
echo ""
echo "3. Health Endpoint:"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health 2>/dev/null)
if [ "$HEALTH" = "200" ]; then
    echo -e "   ${GREEN}✅ Health check passed (HTTP 200)${NC}"
else
    echo -e "   ${RED}❌ Health check failed (HTTP $HEALTH)${NC}"
fi

# 4. Port 8000 Security
echo ""
echo "4. Port 8000 Security:"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "unknown")
if [ "$PUBLIC_IP" != "unknown" ]; then
    PORT_CHECK=$(curl -s --connect-timeout 3 -o /dev/null -w "%{http_code}" http://$PUBLIC_IP:8000/health 2>/dev/null || echo "000")
    if [ "$PORT_CHECK" = "000" ]; then
        echo -e "   ${GREEN}✅ Port 8000 not publicly accessible${NC}"
    else
        echo -e "   ${RED}❌ WARNING: Port 8000 IS accessible (HTTP $PORT_CHECK)${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Could not determine public IP${NC}"
fi

# 5. Database SSL
echo ""
echo "5. Database Connection:"
cd "$APP_DIR"
source venv/bin/activate
python3 -c "
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

url = os.getenv('DATABASE_URL', '')
if 'ssl=true' in url:
    print('   ✅ SSL enabled in DATABASE_URL')
else:
    print('   ❌ SSL not configured (must use ssl=true)')

# Test connection
async def test():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    try:
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        await engine.dispose()
        print('   ✅ Database connection successful')
    except Exception as e:
        print(f'   ❌ Database connection failed: {e}')

asyncio.run(test())
" 2>/dev/null

# 6. .env Security
echo ""
echo "6. Environment File:"
if [ -f "$APP_DIR/.env" ]; then
    PERM=$(stat -c "%a" "$APP_DIR/.env")
    if [ "$PERM" = "600" ]; then
        echo -e "   ${GREEN}✅ .env permissions correct (600)${NC}"
    else
        echo -e "   ${YELLOW}⚠️  .env permissions: $PERM (should be 600)${NC}"
    fi
else
    echo -e "   ${RED}❌ .env file not found${NC}"
fi

# 7. Temp Directory
echo ""
echo "7. Temp Directory:"
if [ -d "$APP_DIR/tmp" ] && [ -w "$APP_DIR/tmp" ]; then
    echo -e "   ${GREEN}✅ Temp directory exists and writable${NC}"
else
    echo -e "   ${RED}❌ Temp directory issue${NC}"
fi

# 8. Logs Directory
echo ""
echo "8. Logs Directory:"
if [ -d "$APP_DIR/logs" ]; then
    echo -e "   ${GREEN}✅ Logs directory exists${NC}"
else
    echo -e "   ${YELLOW}⚠️  Logs directory missing${NC}"
fi

# 9. Database Tables
echo ""
echo "9. Database Schema:"
python3 -c "
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
load_dotenv()

async def check():
    engine = create_async_engine(os.getenv('DATABASE_URL'))
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'\"))
        count = result.scalar()
        if count >= 22:
            print(f'   ✅ {count} tables found (schema complete)')
        else:
            print(f'   ⚠️  {count} tables found (expected 22+)')
    await engine.dispose()

asyncio.run(check())
" 2>/dev/null

# 10. Memory Usage
echo ""
echo "10. Resource Usage:"
MEM_USED=$(free -m | awk 'NR==2{printf "%.0f", $3/$2*100}')
echo "    Memory: ${MEM_USED}% used"
DISK_USED=$(df -h / | awk 'NR==2{print $5}')
echo "    Disk: ${DISK_USED} used"

echo ""
echo "=============================================="
echo "  VALIDATION COMPLETE"
echo "=============================================="
