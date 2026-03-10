# 🚀 StudyBuddy CI/CD Pipeline - Quick Reference

## 📖 What is this?

This CI/CD (Continuous Integration/Continuous Deployment) pipeline automatically deploys your StudyBuddy application to EC2 whenever you push code to GitHub - from Emergent, local development, or any other source.

## ⚡ Quick Start

### 1. One-Time Setup on EC2 (5 minutes)
```bash
# Copy setup script to EC2
scp -i DhruvStar_key.pem scripts/ec2-setup.sh ubuntu@13.201.25.124:/home/ubuntu/

# Connect and run
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
chmod +x ec2-setup.sh
./ec2-setup.sh
```

### 2. Configure Environment Files on EC2
```bash
# Backend .env
nano /home/ubuntu/studybuddy/backend/.env

# Frontend .env
nano /home/ubuntu/studybuddy/frontend/.env
```
*(Copy your existing .env content)*

### 3. Add GitHub Secrets
Go to: **GitHub Repository → Settings → Secrets → Actions → New repository secret**

Add these 3 secrets:
- **EC2_HOST**: `13.201.25.124`
- **EC2_USERNAME**: `ubuntu`  
- **EC2_SSH_KEY**: *Content of DhruvStar_key.pem file*

### 4. Push and Deploy!
```bash
git add .
git commit -m "Setup CI/CD"
git push origin main
```

Watch the deployment in **GitHub Actions** tab! 🎉

---

## 📁 Files Created

```
.
├── .github/
│   └── workflows/
│       └── deploy-to-ec2.yml        # GitHub Actions workflow
├── scripts/
│   ├── ec2-setup.sh                 # EC2 initial setup script
│   └── cicd-checklist.sh            # Setup verification script
├── CICD_SETUP.md                    # Detailed documentation
└── CICD_README.md                   # This file
```

---

## 🔄 How It Works

```
┌──────────────┐
│   Emergent   │  Makes changes
│   or Local   │  Pushes to GitHub
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    GitHub    │  Receives push
│  Repository  │  Triggers workflow
└──────┬───────┘
       │
       ▼
┌──────────────┐
│GitHub Actions│  Runs deployment
│   Workflow   │  Connects to EC2
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  EC2 Server  │  Pulls code
│              │  Builds & deploys
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ✅ Live App  │  Updated!
└──────────────┘
```

---

## 🛠️ What Gets Deployed

### Backend (FastAPI)
- ✅ Installs Python dependencies
- ✅ Restarts backend service
- ✅ Verifies service is running

### Frontend (React)
- ✅ Installs Node dependencies  
- ✅ Builds production bundle
- ✅ Copies to Nginx web root
- ✅ Reloads Nginx

**Total Time**: ~3-5 minutes per deployment

---

## 🔍 Monitoring

### GitHub Actions
View deployment logs: **GitHub → Actions tab**

### EC2 Services
```bash
# Check backend
sudo systemctl status studybuddy-backend

# Check Nginx
sudo systemctl status nginx

# View logs
sudo journalctl -u studybuddy-backend -f
```

---

## 🆘 Troubleshooting

### Deployment Failed in GitHub Actions
1. Check the **Actions** tab for error details
2. Verify GitHub Secrets are set correctly
3. Ensure EC2 is accessible via SSH

### Backend Not Starting on EC2
```bash
# Check logs
sudo journalctl -u studybuddy-backend -n 50

# Verify .env file
cat /home/ubuntu/studybuddy/backend/.env

# Restart manually
sudo systemctl restart studybuddy-backend
```

### Frontend Not Loading
```bash
# Check Nginx config
sudo nginx -t

# Restart Nginx
sudo systemctl reload nginx

# Check permissions
ls -la /var/www/studybuddy/
```

---

## 📚 Documentation

- **Full Setup Guide**: [CICD_SETUP.md](./CICD_SETUP.md)
- **EC2 Setup Script**: [scripts/ec2-setup.sh](./scripts/ec2-setup.sh)
- **Workflow File**: [.github/workflows/deploy-to-ec2.yml](./.github/workflows/deploy-to-ec2.yml)

---

## ✅ Post-Setup Checklist

After completing setup, verify:

- [ ] EC2 setup script completed successfully
- [ ] Environment files configured on EC2
- [ ] GitHub Secrets added (3 secrets)
- [ ] First deployment succeeded (check Actions tab)
- [ ] Backend service running on EC2
- [ ] Frontend accessible in browser
- [ ] Application works correctly

---

## 🔐 Security Notes

- ✅ `.env` files are **never** committed to GitHub
- ✅ `.env` files persist on EC2 (not overwritten)
- ✅ SSH key stored securely in GitHub Secrets
- ✅ All secrets encrypted by GitHub

---

## 💡 Usage Examples

### From Emergent
```
1. Make changes in Emergent Agent
2. Agent commits: "Fixed teacher analytics"
3. Agent pushes to GitHub
4. ✅ Auto-deploys to EC2
```

### From Local Machine
```bash
git clone <your-repo>
# Make changes
git add .
git commit -m "Added new feature"
git push origin main
# ✅ Auto-deploys to EC2
```

### From Another Emergent Account
```
1. Connect to same GitHub repo
2. Make changes
3. Push changes
4. ✅ Auto-deploys to EC2
```

**Any push to `main` branch = automatic deployment!** 🚀

---

## 📞 Support

For detailed instructions, see [CICD_SETUP.md](./CICD_SETUP.md)

---

**Setup Date**: 2025
**Version**: 1.0
**Status**: ✅ Ready to Use
