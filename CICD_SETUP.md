# 🚀 CI/CD Pipeline Setup Guide - GitHub to EC2

## Overview
This guide will help you set up automatic deployment from GitHub to your EC2 instance. Every time you push code to GitHub (from Emergent or any other source), your EC2 instance will automatically update.

---

## 📋 Prerequisites

- ✅ EC2 instance running Ubuntu (IP: 13.201.25.124)
- ✅ GitHub repository connected to this project
- ✅ SSH access to EC2 instance
- ✅ EC2 SSH key file (DhruvStar_key.pem)

---

## 🔧 Part 1: EC2 Instance Setup (One-Time)

### Step 1: Connect to EC2
```bash
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
```

### Step 2: Run Setup Script
The setup script will:
- Install dependencies (Python, Node.js, Yarn, Nginx)
- Create systemd service for backend
- Configure Nginx reverse proxy
- Set up web root directory

```bash
# Create app directory
mkdir -p /home/ubuntu/studybuddy

# Copy the setup script to EC2 (from your local machine)
scp -i DhruvStar_key.pem scripts/ec2-setup.sh ubuntu@13.201.25.124:/home/ubuntu/

# Run the setup script on EC2
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
chmod +x /home/ubuntu/ec2-setup.sh
./ec2-setup.sh
```

### Step 3: Configure Environment Files on EC2

#### Backend Environment (.env)
```bash
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
cd /home/ubuntu/studybuddy/backend

# Create .env file
nano .env
```

Add your configuration:
```env
# PostgreSQL Database
DATABASE_URL=postgresql+asyncpg://postgres:abv84012@database-1.c7iya4u0apvr.ap-south-1.rds.amazonaws.com:5432/postgres

# Authentication
MOCK_OTP_MODE=true
MOCK_OTP_VALUE=123456
JWT_SECRET=7c96ec43e36b1ba78f0e6d129e09591d68f80c039efb3b5ac3fe639086407082
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# OpenRouter API Key
OPENROUTER_API_KEY=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

# AWS S3 Storage
AWS_ACCESS_KEY_ID=AKIAWC2NIBD4VYOCCBXO
AWS_SECRET_ACCESS_KEY=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
S3_BUCKET_NAME=anshavprojects
AWS_REGION=ap-south-1

# Admin Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=Admin@123
ENV=production
```

#### Frontend Environment (.env)
```bash
cd /home/ubuntu/studybuddy/frontend

# Create .env file
nano .env
```

Add your configuration:
```env
REACT_APP_BACKEND_URL=https://your-domain.com
```
*Replace with your actual domain or EC2 public URL*

---

## 🔐 Part 2: GitHub Repository Setup

### Step 1: Get EC2 SSH Private Key Content
```bash
# On your local machine where you have DhruvStar_key.pem
cat DhruvStar_key.pem
```
Copy the entire content including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`

### Step 2: Add GitHub Secrets
Go to your GitHub repository:

1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**

Add these 3 secrets:

#### Secret 1: EC2_HOST
- **Name**: `EC2_HOST`
- **Value**: `13.201.25.124`

#### Secret 2: EC2_USERNAME
- **Name**: `EC2_USERNAME`
- **Value**: `ubuntu`

#### Secret 3: EC2_SSH_KEY
- **Name**: `EC2_SSH_KEY`
- **Value**: Paste the entire content of `DhruvStar_key.pem` file
  ```
  -----BEGIN RSA PRIVATE KEY-----
  MIIEpAIBAAKCAQEA...
  (entire key content)
  ...
  -----END RSA PRIVATE KEY-----
  ```

### Step 3: Verify GitHub Workflow File
The workflow file is already created at `.github/workflows/deploy-to-ec2.yml`

To verify:
```bash
cat .github/workflows/deploy-to-ec2.yml
```

---

## 🎯 Part 3: Testing the Pipeline

### Automatic Deployment (Push to GitHub)
```bash
# Make any change to your code
echo "# Test update" >> README.md

# Commit and push
git add .
git commit -m "Test CI/CD pipeline"
git push origin main
```

### Monitor Deployment
1. Go to your GitHub repository
2. Click **Actions** tab
3. You'll see your workflow running
4. Click on the workflow to see live logs

### Manual Trigger (Optional)
You can also trigger deployment manually:
1. Go to **Actions** tab
2. Select **Deploy StudyBuddy to EC2** workflow
3. Click **Run workflow** button
4. Select branch and click **Run workflow**

---

## 📊 Deployment Process

When you push to GitHub, the workflow will:

1. ✅ **Checkout code** from your repository
2. ✅ **Connect to EC2** via SSH
3. ✅ **Pull latest code** from GitHub
4. ✅ **Backend Deployment**:
   - Install Python dependencies
   - Restart backend service
   - Verify service is running
5. ✅ **Frontend Deployment**:
   - Install Node dependencies
   - Build React app
   - Copy to web root
   - Reload Nginx
6. ✅ **Verify** all services are running

**Total Time**: ~3-5 minutes

---

## 🔍 Monitoring & Troubleshooting

### Check Deployment Status
```bash
# Connect to EC2
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124

# Check backend service
sudo systemctl status studybuddy-backend

# Check backend logs
sudo journalctl -u studybuddy-backend -f

# Check Nginx
sudo systemctl status nginx
sudo nginx -t

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Common Issues

#### 1. Backend Service Not Starting
```bash
# Check logs
sudo journalctl -u studybuddy-backend -n 50 --no-pager

# Check .env file exists
ls -la /home/ubuntu/studybuddy/backend/.env

# Restart service
sudo systemctl restart studybuddy-backend
```

#### 2. Frontend Build Fails
```bash
# Check if Node.js is installed
node --version
yarn --version

# Manually build
cd /home/ubuntu/studybuddy/frontend
yarn install
yarn build
```

#### 3. Nginx Configuration Issues
```bash
# Test Nginx config
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

#### 4. GitHub Actions Failing
- Check **Actions** tab in GitHub for error logs
- Verify GitHub Secrets are set correctly
- Ensure EC2 security group allows SSH (port 22) from GitHub IPs

---

## 🔒 Security Best Practices

### 1. Protect Environment Files
- ✅ `.env` files are in `.gitignore` (never commit secrets to GitHub)
- ✅ `.env` files stay only on EC2 instance
- ✅ GitHub workflow preserves existing `.env` files

### 2. EC2 Security Group
Ensure your EC2 security group allows:
- **SSH (22)**: From GitHub Actions IPs or your IP
- **HTTP (80)**: From anywhere (0.0.0.0/0)
- **HTTPS (443)**: From anywhere (0.0.0.0/0) - if using SSL

### 3. Rotate SSH Keys
Periodically rotate your EC2 SSH keys and update GitHub secret

---

## 📝 Development Workflow

### From Emergent Agent
1. Make changes in Emergent
2. Agent commits changes
3. Push to GitHub repository
4. CI/CD pipeline automatically deploys to EC2

### From Local Development
1. Clone repository: `git clone <your-repo-url>`
2. Make changes locally
3. Commit: `git commit -m "Your message"`
4. Push: `git push origin main`
5. CI/CD pipeline automatically deploys to EC2

### From Another Emergent Account
1. Connect to same GitHub repository
2. Make changes
3. Push changes
4. CI/CD pipeline automatically deploys to EC2

**Key Point**: Any push to the `main` branch from ANY source triggers automatic deployment!

---

## 🎉 Success Checklist

After setup is complete, verify:

- [ ] EC2 setup script ran successfully
- [ ] Backend `.env` file configured on EC2
- [ ] Frontend `.env` file configured on EC2
- [ ] GitHub Secrets added (EC2_HOST, EC2_USERNAME, EC2_SSH_KEY)
- [ ] GitHub workflow file exists (`.github/workflows/deploy-to-ec2.yml`)
- [ ] First deployment successful (check Actions tab)
- [ ] Backend service running: `sudo systemctl status studybuddy-backend`
- [ ] Nginx running: `sudo systemctl status nginx`
- [ ] Application accessible at your domain/IP

---

## 📞 Quick Commands Reference

### EC2 Commands
```bash
# Connect to EC2
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124

# Check services
sudo systemctl status studybuddy-backend
sudo systemctl status nginx

# Restart services
sudo systemctl restart studybuddy-backend
sudo systemctl reload nginx

# View logs
sudo journalctl -u studybuddy-backend -f
sudo tail -f /var/log/nginx/error.log

# Manual deployment (if needed)
cd /home/ubuntu/studybuddy
git pull origin main
cd backend && pip3 install -r requirements.txt && sudo systemctl restart studybuddy-backend
cd ../frontend && yarn install && yarn build && sudo cp -r build/* /var/www/studybuddy/
```

### Git Commands
```bash
# Check status
git status

# Commit changes
git add .
git commit -m "Your message"

# Push to GitHub (triggers deployment)
git push origin main

# View remote
git remote -v
```

---

## 🔄 Continuous Deployment Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Developer (Emergent / Local / Any Source)                  │
│  Makes changes and pushes to GitHub                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Repository (main branch)                             │
│  Receives push event                                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions Workflow                                     │
│  - Triggered automatically                                   │
│  - Runs deployment script                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  EC2 Instance (13.201.25.124)                               │
│  - Pulls latest code                                         │
│  - Installs dependencies                                     │
│  - Builds frontend                                           │
│  - Restarts backend service                                  │
│  - Reloads Nginx                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  ✅ Application Updated & Running                           │
│  Students and teachers see latest changes                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [SSH Action Documentation](https://github.com/appleboy/ssh-action)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
- [Systemd Service Guide](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

---

**Setup Date**: $(date)
**Documentation Version**: 1.0
**Maintained by**: StudyBuddy Team
