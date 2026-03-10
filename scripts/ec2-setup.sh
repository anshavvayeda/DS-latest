#!/bin/bash
# StudyBuddy EC2 Setup Script
# Run this ONCE on your EC2 instance to set up the systemd service

set -e

echo "========================================="
echo "🔧 StudyBuddy EC2 Setup"
echo "========================================="

APP_DIR="/home/ubuntu/studybuddy"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "❌ Please run as ubuntu user, not root"
   exit 1
fi

echo "1️⃣  Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv nginx git curl

# Install Node.js and Yarn
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

if ! command -v yarn &> /dev/null; then
    echo "📦 Installing Yarn..."
    curl -sL https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add -
    echo "deb https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list
    sudo apt-get update -qq && sudo apt-get install -y yarn
fi

echo ""
echo "2️⃣  Creating systemd service for backend..."

# Create systemd service file
sudo tee /etc/systemd/system/studybuddy-backend.service > /dev/null << 'EOF'
[Unit]
Description=StudyBuddy FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/studybuddy/backend
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "3️⃣  Configuring Nginx..."

# Create Nginx configuration
sudo tee /etc/nginx/sites-available/studybuddy > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    # Frontend (React build)
    location / {
        root /var/www/studybuddy;
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/studybuddy /etc/nginx/sites-enabled/studybuddy
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload Nginx
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "4️⃣  Creating web root directory..."
sudo mkdir -p /var/www/studybuddy
sudo chown -R ubuntu:ubuntu /var/www/studybuddy

echo ""
echo "5️⃣  Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable studybuddy-backend
sudo systemctl enable nginx

echo ""
echo "========================================="
echo "✅ EC2 Setup Complete!"
echo "========================================="
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Configure environment files:"
echo "   - Edit: $APP_DIR/backend/.env"
echo "   - Edit: $APP_DIR/frontend/.env"
echo ""
echo "2. Set up GitHub Secrets (see CICD_SETUP.md)"
echo ""
echo "3. Push code to GitHub to trigger deployment"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status studybuddy-backend"
echo "   sudo systemctl status nginx"
echo ""
echo "========================================="
