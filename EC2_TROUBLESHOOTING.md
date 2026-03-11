# 🔧 EC2 Deployment Troubleshooting Guide

## Issue: "Not authenticated" on Teacher Registration + Empty Admin Dashboard

### Root Causes:
1. Frontend might not be rebuilt with latest code
2. Browser cache holding old JavaScript
3. EC2 database is empty (different from Emergent database)

---

## ✅ Solution Steps

### Step 1: Verify Latest Code on EC2

Run from PowerShell:
```powershell
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124 "cd /home/ubuntu/studybuddy && git log --oneline -3"
```

**Expected:** Should see `b18ebdb Add public teacher registration endpoint and UI`

---

### Step 2: Force Rebuild on EC2

SSH into EC2 and rebuild:

```bash
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
```

Then run:

```bash
cd /home/ubuntu/studybuddy

# Pull latest code
git fetch origin
git reset --hard origin/main

# Rebuild backend
cd backend
source /home/ubuntu/studybuddy/venv/bin/activate
grep -v "emergentintegrations" requirements.txt > requirements_ec2.txt
pip install -q -r requirements_ec2.txt

# Restart backend
sudo systemctl restart studybuddy-backend
sleep 3
sudo systemctl status studybuddy-backend --no-pager

# Rebuild frontend (IMPORTANT!)
cd /home/ubuntu/studybuddy/frontend
rm -rf build node_modules/.cache
yarn install
yarn build

# Deploy frontend
sudo rm -rf /var/www/studybuddy/*
sudo cp -r build/* /var/www/studybuddy/

# Reload Nginx
sudo systemctl reload nginx

echo "✅ Rebuild complete!"
```

---

### Step 3: Initialize Admin User in EC2 Database

The EC2 database is empty. Create admin user:

```bash
cd /home/ubuntu/studybuddy/backend
source /home/ubuntu/studybuddy/venv/bin/activate
python3 init_ec2_admin.py
```

**Output:**
```
✅ Admin user created successfully!

Login credentials:
  Username: admin
  Password: Admin@123
```

---

### Step 4: Clear Browser Cache & Test

**Important:** The browser might have cached old JavaScript

1. **Open browser in Incognito/Private mode**
2. Go to: `http://13.201.25.124`
3. You should see "Register as Teacher" link
4. Click it and try registering

**OR**

1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+F5)
3. Try again

---

### Step 5: Test Teacher Registration

**Test via browser:**
1. Go to http://13.201.25.124
2. Click "Register as Teacher"
3. Fill in form:
   - Name: Test Teacher
   - School: Test School
   - Roll No: T001
   - Phone: 9999999999
   - Password: test123
4. Click Register

**Test via API directly:**
```bash
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124

curl -X POST http://localhost:8001/api/auth/register-teacher \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Teacher",
    "school_name": "Test School",
    "phone": "9999999999",
    "roll_no": "T001",
    "password": "test123",
    "role": "teacher"
  }'
```

**Expected:** Success message, not "Not authenticated"

---

### Step 6: Login as Admin

1. Go to http://13.201.25.124
2. Click "Admin Login"
3. Username: `admin`
4. Password: `Admin@123`
5. You should see the admin dashboard

Now you can register students from admin panel!

---

## 🎯 Common Issues & Fixes

### Issue: Still getting "Not authenticated"

**Cause:** Old frontend cached in browser

**Fix:**
1. Open browser DevTools (F12)
2. Go to Network tab
3. Check "Disable cache"
4. Hard refresh (Ctrl+F5)
5. Or use Incognito mode

---

### Issue: Teacher registration endpoint not found (404)

**Cause:** Backend not restarted or code not deployed

**Fix:**
```bash
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
cd /home/ubuntu/studybuddy/backend
grep -n "auth/register-teacher" server.py

# If not found, pull latest:
git fetch origin && git reset --hard origin/main

# Restart backend
sudo systemctl restart studybuddy-backend
```

---

### Issue: Admin sees no students/teachers

**Cause:** Different databases (Emergent vs EC2)

**Fix:** This is expected!
- Emergent has test data
- EC2 has production database (empty initially)
- Register teachers via the registration form
- Register students via admin panel

---

## 📋 Quick Checklist

- [ ] Latest code pulled on EC2 (`git log` shows commit b18ebdb)
- [ ] Backend restarted
- [ ] Frontend rebuilt and deployed
- [ ] Browser cache cleared (use Incognito mode)
- [ ] Admin user created in EC2 database
- [ ] Teacher registration works (no "Not authenticated" error)
- [ ] Admin login works
- [ ] Can register students from admin panel

---

## 🚀 After Everything Works

1. **Change admin password** (use Forgot Password feature)
2. **Register your real teachers**
3. **Register students via admin panel**
4. **Start using the platform!**

---

**Need more help?** Tell me which step is failing and I'll debug further!
