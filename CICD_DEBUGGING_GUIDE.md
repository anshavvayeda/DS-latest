# 🔍 CI/CD Pipeline Debugging Guide

## Current Status

✅ **Application Setup**: Complete and running
- Backend: Running on port 8001 (database connected)
- Frontend: Running on port 3000 (webpack compiled)
- API responding: https://adaptive-classroom-5.preview.emergentagent.com/api/

⚠️ **CI/CD Pipeline**: Needs debugging
- Issue: GitHub Actions deployment to EC2 failing
- Root cause: SSH connection error (per handover document)

---

## 🎯 CI/CD Architecture

### Current Deployment Flow:
```
GitHub Push → GitHub Actions → SSH to EC2 → Deploy Code
     ↓              ↓              ↓              ↓
   main       workflow      appleboy/     systemd
   branch     triggered     ssh-action    services
```

### Required GitHub Secrets:
1. **EC2_HOST**: `13.201.25.124` (EC2 public IP)
2. **EC2_USERNAME**: `ubuntu` (default EC2 user)
3. **EC2_SSH_KEY**: Content of `DhruvStar_key.pem` file

---

## 🐛 Common CI/CD Issues & Solutions

### Issue 1: SSH Key Format Problem (Most Likely)

**Symptoms:**
- GitHub Actions fails at "Deploy to EC2" step
- Error: "Permission denied (publickey)" or silent failure
- SSH connection times out

**Root Cause:**
The `EC2_SSH_KEY` secret might have:
- Extra newlines at the beginning/end
- Missing header/footer (`-----BEGIN RSA PRIVATE KEY-----`)
- Corrupted during copy-paste
- Wrong line endings (Windows vs Unix)

**Solution:**

1. **Get the SSH key properly:**
   ```bash
   # On your local machine where DhruvStar_key.pem is stored
   cat DhruvStar_key.pem
   ```

2. **Copy EXACT content** (must include):
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA...
   (all lines of the key)
   ...
   -----END RSA PRIVATE KEY-----
   ```

3. **Update GitHub Secret:**
   - Go to: https://github.com/anshavvayeda/DS-latest/settings/secrets/actions
   - Delete existing `EC2_SSH_KEY` secret
   - Create new `EC2_SSH_KEY` secret
   - Paste the ENTIRE key content (no extra spaces/newlines)
   - Save

4. **Verify other secrets exist:**
   - `EC2_HOST` = `13.201.25.124`
   - `EC2_USERNAME` = `ubuntu`

---

### Issue 2: EC2 Security Group Blocks SSH

**Symptoms:**
- Connection timeout during deployment
- Works from local machine but not from GitHub Actions

**Solution:**

1. **Check EC2 Security Group:**
   - AWS Console → EC2 → Security Groups
   - Find security group for instance 13.201.25.124
   - Ensure port 22 (SSH) is open

2. **Allow GitHub Actions IPs:**
   
   **Option A (Recommended):** Allow all IPs temporarily for testing
   ```
   Type: SSH
   Port: 22
   Source: 0.0.0.0/0
   ```

   **Option B (More secure):** Allow GitHub Actions IP ranges
   - Get IPs from: https://api.github.com/meta
   - Add each IP range to security group

---

### Issue 3: Repository is Private

**Symptoms:**
- Git clone fails on EC2
- Error: "could not read Username for 'https://github.com'"

**Current Status:**
The workflow uses `${{ github.repository }}` which includes authentication from GitHub Actions automatically.

**If this fails:**

**Option A:** Make repository public temporarily

**Option B:** Use GitHub Personal Access Token (PAT)
1. Generate PAT: https://github.com/settings/tokens
2. Add as GitHub Secret: `GH_PAT`
3. Update workflow to use: 
   ```bash
   REPO_URL="https://${{ secrets.GH_PAT }}@github.com/${{ github.repository }}.git"
   ```

---

### Issue 4: EC2 Instance Not Set Up

**Symptoms:**
- SSH works but deployment fails
- Missing directories or services

**Solution:**

1. **Check if EC2 setup was completed:**
   ```bash
   ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
   
   # Check if service exists
   sudo systemctl status studybuddy-backend
   
   # Check if Nginx is configured
   ls -la /etc/nginx/sites-enabled/studybuddy
   
   # Check if app directory exists
   ls -la /home/ubuntu/studybuddy
   ```

2. **If not set up, run the setup script:**
   ```bash
   # Copy setup script to EC2
   scp -i DhruvStar_key.pem /app/scripts/ec2-setup.sh ubuntu@13.201.25.124:/home/ubuntu/
   
   # SSH to EC2 and run
   ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
   chmod +x /home/ubuntu/ec2-setup.sh
   ./ec2-setup.sh
   ```

---

## 🔧 Debugging Steps (In Order)

### Step 1: Verify GitHub Secrets Exist

1. Go to: https://github.com/anshavvayeda/DS-latest/settings/secrets/actions

2. Verify these 3 secrets exist:
   - ✅ EC2_HOST
   - ✅ EC2_USERNAME
   - ✅ EC2_SSH_KEY

3. If any are missing, create them (see Issue 1 above)

---

### Step 2: Test SSH Connection Manually

```bash
# On your local machine
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124 "echo 'SSH works!'"
```

**Expected output:** `SSH works!`

**If this fails:**
- Check if you have the correct .pem file
- Check EC2 security group (port 22 open)
- Check if instance is running

---

### Step 3: Create Simple Test Workflow

I'll create a simplified workflow to test SSH connection only:

**File:** `.github/workflows/test-ssh-connection.yml`

```yaml
name: Test SSH Connection

on:
  workflow_dispatch:  # Manual trigger only

jobs:
  test-ssh:
    name: Test SSH to EC2
    runs-on: ubuntu-latest
    
    steps:
      - name: Test SSH Connection
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USERNAME }}
          key: ${{ secrets.EC2_SSH_KEY }}
          port: 22
          script: |
            echo "✅ SSH connection successful!"
            echo "Hostname: $(hostname)"
            echo "User: $(whoami)"
            echo "Date: $(date)"
            echo "Working directory: $(pwd)"
```

---

### Step 4: Run Test Workflow

1. **Commit the test workflow:**
   ```bash
   git add .github/workflows/test-ssh-connection.yml
   git commit -m "Add SSH connection test workflow"
   git push origin main
   ```

2. **Run manually from GitHub:**
   - Go to: https://github.com/anshavvayeda/DS-latest/actions
   - Click "Test SSH Connection"
   - Click "Run workflow"
   - Select branch: `main`
   - Click "Run workflow" button

3. **Check results:**
   - If ✅ **Success**: SSH connection works, problem is elsewhere
   - If ❌ **Fails**: SSH key or connection issue

---

### Step 5: Check GitHub Actions Logs

1. Go to: https://github.com/anshavvayeda/DS-latest/actions

2. Click on the latest failed workflow run

3. Look for error messages:
   - **"Permission denied (publickey)"** → SSH key issue (see Issue 1)
   - **"Connection timeout"** → Security group issue (see Issue 2)
   - **"Name or service not known"** → Wrong EC2_HOST value
   - **"git clone failed"** → Repository access issue (see Issue 3)

---

### Step 6: Fix and Re-run

Based on the error from Step 5, apply the corresponding solution from "Common Issues" section above.

Then trigger deployment again:
```bash
# Make a small change
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test CI/CD pipeline"
git push origin main
```

---

## 📊 Expected Workflow Output

When the deployment works correctly, you should see:

```
🚀 Starting StudyBuddy Deployment
========================================
📦 Deployment Configuration:
  - App Directory: /home/ubuntu/studybuddy
  - Repository: https://github.com/anshavvayeda/DS-latest.git
  - Branch: main

📥 Cloning repository... (or 🔄 Pulling latest changes...)

========================================
🔧 Backend Deployment
========================================
✅ Backend .env exists
📦 Installing Python dependencies...
🛑 Stopping backend service...
▶️  Starting backend service...
✅ Backend service is running

========================================
🎨 Frontend Deployment
========================================
✅ Frontend .env exists
📦 Installing Node dependencies...
🔨 Building frontend...
📋 Deploying to web root...
🔄 Reloading Nginx...
✅ Nginx is running

========================================
✅ Deployment Completed Successfully!
========================================
```

---

## 🆘 Quick Fixes Checklist

Before asking for help, verify:

- [ ] All 3 GitHub Secrets exist (EC2_HOST, EC2_USERNAME, EC2_SSH_KEY)
- [ ] EC2_SSH_KEY contains the FULL .pem file content (including BEGIN/END lines)
- [ ] EC2_SSH_KEY has NO extra newlines at start/end
- [ ] EC2 security group allows SSH (port 22) from 0.0.0.0/0
- [ ] EC2 instance is running (check AWS console)
- [ ] SSH works manually: `ssh -i DhruvStar_key.pem ubuntu@13.201.25.124`
- [ ] EC2 setup script was run (systemd service exists)

---

## 🎯 Next Steps After CI/CD Works

Once deployment is successful:

1. **Configure Production Domain:**
   - Point your domain to EC2 IP (13.201.25.124)
   - Update `frontend/.env` on EC2 with production URL
   - Set up SSL certificate (Let's Encrypt)

2. **Set Up Monitoring:**
   - Enable CloudWatch for EC2
   - Set up alerts for service failures
   - Monitor deployment logs

3. **Security Hardening:**
   - Restrict SSH to specific IPs (remove 0.0.0.0/0)
   - Enable AWS GuardDuty
   - Regular security updates

---

## 📞 Support Resources

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **appleboy/ssh-action**: https://github.com/appleboy/ssh-action
- **EC2 Security Groups**: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html

---

**Created:** March 10, 2026  
**Status:** Ready for debugging
