#!/bin/bash
# =============================================================================
# EC2 Initial Server Setup Script
# =============================================================================
# Run this ONCE on a fresh Ubuntu 24.04 EC2 instance
# Usage: curl -sSL https://your-url/setup.sh | bash
# =============================================================================

set -e

echo "=============================================="
echo "  StudyBuddy EC2 Server Setup"
echo "  $(date)"
echo "=============================================="

# Update system
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
echo "[2/8] Installing required packages..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    nginx \
    curl \
    htop \
    supervisor \
    build-essential \
    libpq-dev \
    postgresql-client

# Create application directory
echo "[3/8] Creating application directory..."
sudo mkdir -p /home/ubuntu/studybuddy
sudo chown -R ubuntu:ubuntu /home/ubuntu/studybuddy

# Clone repository (replace with your repo URL)
echo "[4/8] Cloning repository..."
cd /home/ubuntu/studybuddy
# git clone https://github.com/yourusername/studybuddy.git .
echo "NOTE: Clone your repository manually or update this script with your repo URL"

# Create virtual environment
echo "[5/8] Setting up Python virtual environment..."
cd /home/ubuntu/studybuddy/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create logs directory
echo "[6/8] Creating logs directory..."
mkdir -p /home/ubuntu/studybuddy/backend/logs
mkdir -p /home/ubuntu/studybuddy/backend/uploads

# Setup systemd service
echo "[7/8] Setting up systemd service..."
sudo cp /home/ubuntu/studybuddy/backend/deploy/studybuddy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable studybuddy

# Setup Nginx
echo "[8/8] Setting up Nginx..."
sudo cp /home/ubuntu/studybuddy/backend/deploy/nginx.conf /etc/nginx/sites-available/studybuddy
sudo ln -sf /etc/nginx/sites-available/studybuddy /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and fill in your values:"
echo "   cp /home/ubuntu/studybuddy/backend/.env.example /home/ubuntu/studybuddy/backend/.env"
echo "   nano /home/ubuntu/studybuddy/backend/.env"
echo ""
echo "2. Run database migrations:"
echo "   cd /home/ubuntu/studybuddy/backend"
echo "   source venv/bin/activate"
echo "   alembic upgrade head"
echo ""
echo "3. Start the service:"
echo "   sudo systemctl start studybuddy"
echo ""
echo "4. Check status:"
echo "   sudo systemctl status studybuddy"
echo "   curl http://localhost:8000/health"
echo ""
echo "=============================================="
