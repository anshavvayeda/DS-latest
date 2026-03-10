# 🔧 Fix Deployment Issue - Repository Access

## Problem Identified

✅ **SSH Connection**: Working!  
❌ **Deployment**: Failing because EC2 can't access your private GitHub repository

---

## 🎯 Solution: Fix Repository Access

### Option 1: Make Repository Public (RECOMMENDED - Easiest)

**Time:** 2 minutes

1. Go to: https://github.com/anshavvayeda/DS-latest/settings

2. Scroll to bottom → "Danger Zone"

3. Click "Change visibility" → "Make public"

4. Type repository name to confirm: `DS-latest`

5. Click "I understand, change repository visibility"

6. **Test deployment:**
   - Go to: https://github.com/anshavvayeda/DS-latest/actions
   - Click "Deploy StudyBuddy to EC2"
   - Click "Run workflow" → main → Run workflow

✅ This will fix the issue immediately!

---

### Option 2: Use GitHub Personal Access Token (Keep Private)

**Time:** 5 minutes

If you want to keep the repository private, add a GitHub token:

1. **Create a Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Note: "EC2 Deployment"
   - Check: `repo` (full control)
   - Click "Generate token"
   - **Copy the token** (starts with `ghp_...`)

2. **Add token to GitHub Secrets:**
   - Go to: https://github.com/anshavvayeda/DS-latest/settings/secrets/actions
   - Click "New repository secret"
   - Name: `GH_PAT`
   - Value: Paste your token
   - Click "Add secret"

3. **Update workflow file:**

I'll update the workflow file for you. Run this command:

```bash
# This updates the workflow to use the token
cat > /app/.github/workflows/deploy-to-ec2.yml << 'EOF'
name: Deploy StudyBuddy to EC2

on:
  push:
    branches:
      - main
      - master
  workflow_dispatch:

jobs:
  deploy:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USERNAME }}
          key: ${{ secrets.EC2_SSH_KEY }}
          port: 22
          command_timeout: 30m
          script: |
            #!/bin/bash
            set -e
            
            echo "========================================="
            echo "🚀 Starting StudyBuddy Deployment"
            echo "========================================="
            
            APP_DIR="/home/ubuntu/studybuddy"
            REPO_URL="https://${{ secrets.GH_PAT }}@github.com/${{ github.repository }}.git"
            BRANCH="${{ github.ref_name }}"
            
            echo "📦 Deployment Configuration:"
            echo "  - App Directory: $APP_DIR"
            echo "  - Branch: $BRANCH"
            
            # Create app directory
            mkdir -p "$APP_DIR"
            cd "$APP_DIR"
            
            # Clone or pull with authentication
            if [ ! -d ".git" ]; then
              echo "📥 Cloning repository..."
              git clone "$REPO_URL" .
              git checkout "$BRANCH"
            else
              echo "🔄 Pulling latest changes..."
              git remote set-url origin "$REPO_URL"
              git fetch origin
              git reset --hard "origin/$BRANCH"
              git clean -fd
            fi
            
            echo "🔧 Backend Deployment"
            cd "$APP_DIR/backend"
            
            # Install dependencies
            echo "📦 Installing Python dependencies..."
            pip3 install -q -r requirements.txt
            
            # Restart backend service
            echo "🔄 Restarting backend service..."
            sudo systemctl restart studybuddy-backend || echo "Service not configured yet"
            
            echo "🎨 Frontend Deployment"
            cd "$APP_DIR/frontend"
            
            # Install and build
            echo "📦 Installing Node dependencies..."
            yarn install --frozen-lockfile
            
            echo "🔨 Building frontend..."
            yarn build
            
            # Deploy to web root
            echo "📋 Deploying to web root..."
            sudo mkdir -p /var/www/studybuddy
            sudo cp -r build/* /var/www/studybuddy/
            
            # Reload Nginx
            echo "🔄 Reloading Nginx..."
            sudo systemctl reload nginx || echo "Nginx not configured yet"
            
            echo "========================================="
            echo "✅ Deployment Completed Successfully!"
            echo "========================================="

      - name: Deployment Status
        if: success()
        run: |
          echo "✅ Deployment to EC2 completed successfully!"
          
      - name: Deployment Failed
        if: failure()
        run: |
          echo "❌ Deployment failed!"
          exit 1
EOF
```

4. **Commit and push:**
   - Use "Save to Github" button again
   - Or run: `cd /app && git add .github/workflows/deploy-to-ec2.yml && git commit -m "Update workflow with token" && git push`

---

### Option 3: Use SSH Deploy Key (Most Secure)

This is more complex. Tell me if you want to go this route and I'll guide you.

---

## 🎯 Which Option Should You Choose?

**For testing and MVP:**
- ✅ **Option 1** (Make public) - Fastest, works immediately

**For production:**
- ✅ **Option 2** (PAT token) - Keeps repo private, relatively easy

---

## 📋 Quick Action Plan

1. **Choose Option 1 or 2** above

2. **If Option 1:**
   - Make repo public (5 clicks)
   - Run deployment workflow
   - ✅ Done!

3. **If Option 2:**
   - Create GitHub token
   - Add to secrets
   - Update workflow (I'll help)
   - Run deployment
   - ✅ Done!

---

## ❓ What Do You Want to Do?

Tell me:
- **"Make it public"** - I'll guide you through Option 1
- **"Keep it private"** - I'll guide you through Option 2
- **"Need help deciding"** - I'll explain pros/cons

Which option do you prefer? 😊
EOF
