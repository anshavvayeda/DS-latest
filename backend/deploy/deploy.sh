#!/bin/bash
# =============================================================================
# StudyBuddy Backend Deployment Script
# =============================================================================
# Usage: ./deploy.sh [--skip-deps] [--restart-only]
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/home/ubuntu/studybuddy/backend"
VENV_DIR="$APP_DIR/venv"
SERVICE_NAME="studybuddy"
BRANCH="${DEPLOY_BRANCH:-main}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
SKIP_DEPS=false
RESTART_ONLY=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --skip-deps) SKIP_DEPS=true ;;
        --restart-only) RESTART_ONLY=true ;;
        *) log_error "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Header
echo "=============================================="
echo "  StudyBuddy Backend Deployment"
echo "  $(date)"
echo "=============================================="

# Check if running as correct user
if [ "$USER" != "ubuntu" ]; then
    log_warn "Not running as ubuntu user. Some operations may fail."
fi

# Navigate to app directory
cd "$APP_DIR"
log_info "Working directory: $(pwd)"

if [ "$RESTART_ONLY" = true ]; then
    log_info "Restart-only mode - skipping git pull and dependencies"
else
    # Step 1: Git pull
    log_info "Step 1: Pulling latest code from $BRANCH..."
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
    log_info "Git pull complete"

    # Step 2: Activate virtual environment
    log_info "Step 2: Activating virtual environment..."
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    log_info "Virtual environment activated"

    # Step 3: Install dependencies
    if [ "$SKIP_DEPS" = false ]; then
        log_info "Step 3: Installing dependencies..."
        pip install --upgrade pip
        pip install -r requirements.txt
        log_info "Dependencies installed"
    else
        log_info "Step 3: Skipping dependency installation (--skip-deps)"
    fi

    # Step 4: Run database migrations
    log_info "Step 4: Running database migrations..."
    alembic upgrade head
    log_info "Migrations complete"
fi

# Step 5: Restart service
log_info "Step 5: Restarting $SERVICE_NAME service..."
sudo systemctl daemon-reload
sudo systemctl restart $SERVICE_NAME

# Wait for service to start
sleep 3

# Step 6: Check service status
log_info "Step 6: Checking service status..."
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    log_info "Service is running!"
else
    log_error "Service failed to start!"
    sudo journalctl -u $SERVICE_NAME -n 50 --no-pager
    exit 1
fi

# Step 7: Health check
log_info "Step 7: Running health check..."
sleep 2
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")

if [ "$HEALTH_RESPONSE" = "200" ]; then
    log_info "Health check passed!"
else
    log_error "Health check failed! (HTTP $HEALTH_RESPONSE)"
    log_info "Checking logs..."
    sudo journalctl -u $SERVICE_NAME -n 20 --no-pager
    exit 1
fi

# Step 8: Show recent logs
log_info "Step 8: Recent logs:"
echo "----------------------------------------------"
sudo journalctl -u $SERVICE_NAME -n 10 --no-pager
echo "----------------------------------------------"

# Summary
echo ""
echo "=============================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "=============================================="
echo "  Service: $SERVICE_NAME"
echo "  Status: $(sudo systemctl is-active $SERVICE_NAME)"
echo "  Health: http://localhost:8000/health"
echo "=============================================="
