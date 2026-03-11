# 🔧 Fix 413 Error - Upload Limit Issue

## Problem
When teachers try to upload test PDFs, they get error:
```
Failed to upload test. Request failed with status code 413
```

**Error 413 = Payload Too Large** - PDF files exceed server upload limit

---

## Root Cause
Nginx on EC2 has default upload limit (usually 1-2MB), but PDFs can be much larger (5-50MB).

---

## Solution Applied

### 1. Updated CI/CD Workflow
**File:** `.github/workflows/deploy-to-ec2.yml`

Added automatic Nginx configuration during deployment:
```bash
# Fix Nginx upload limit (for file uploads)
if ! grep -q "client_max_body_size.*100M" /etc/nginx/nginx.conf; then
  sudo sed -i '/http {/a \    client_max_body_size 100M;' /etc/nginx/nginx.conf
fi
sudo systemctl reload nginx
```

### 2. Created Manual Fix Script
**File:** `scripts/fix-nginx-upload-limit.sh`

For immediate manual fix on EC2.

---

## 🚀 Quick Fix (Run This Now on EC2)

SSH to EC2 and run:

```bash
ssh -i DhruvStar_key.pem ubuntu@13.201.25.124
```

Then:

```bash
# Option 1: Use the script
cd /home/ubuntu/studybuddy
chmod +x scripts/fix-nginx-upload-limit.sh
sudo ./scripts/fix-nginx-upload-limit.sh
```

**OR**

```bash
# Option 2: Manual commands
sudo sed -i '/http {/a \    client_max_body_size 100M;' /etc/nginx/nginx.conf
sudo nginx -t
sudo systemctl reload nginx
echo "✅ Upload limit increased to 100MB"
```

---

## Verify the Fix

### Test 1: Check Nginx Config
```bash
grep -A 2 "http {" /etc/nginx/nginx.conf | grep client_max_body_size
```

**Expected output:**
```
    client_max_body_size 100M;
```

### Test 2: Upload PDF Test
1. Login as teacher on http://13.201.25.124
2. Go to "Tests" tab
3. Click "Create Test"
4. Upload test PDF (any size up to 100MB)
5. Should upload successfully ✅

---

## Technical Details

### Before Fix:
```
Nginx default: client_max_body_size 1M
Teacher uploads: 5MB PDF
Result: 413 Error (Payload Too Large)
```

### After Fix:
```
Nginx configured: client_max_body_size 100M
Teacher uploads: 5MB PDF  
Result: ✅ Upload successful
```

### File Size Limits:

| Type | Before | After |
|------|--------|-------|
| Nginx | 1-2MB | 100MB |
| FastAPI | Unlimited | Unlimited |
| S3 | 5GB max | 5GB max |
| **Effective Limit** | **1-2MB** ❌ | **100MB** ✅ |

---

## What Can Be Uploaded Now

After fix, teachers can upload:
- ✅ Test PDFs up to 100MB
- ✅ Model answers up to 100MB
- ✅ Marking schemes up to 100MB
- ✅ Textbook PDFs up to 100MB
- ✅ Homework PDFs up to 100MB

---

## Automatic Fix on Next Deployment

The CI/CD pipeline now includes this fix automatically.

**Next time you push to GitHub:**
1. GitHub Actions runs
2. Deploys code to EC2
3. **Automatically sets Nginx upload limit to 100MB**
4. Reloads Nginx

So this won't happen again! ✅

---

## Files Changed

- `.github/workflows/deploy-to-ec2.yml` - Auto-fix in deployment
- `scripts/fix-nginx-upload-limit.sh` - Manual fix script

---

## Success Criteria

- [ ] Nginx config shows `client_max_body_size 100M;`
- [ ] Nginx reloads without errors
- [ ] Teacher can upload 5MB+ PDF without error
- [ ] No more 413 errors

---

**Status:** Ready to apply
**Priority:** HIGH (blocks teacher functionality)
**Impact:** All teachers uploading PDFs
