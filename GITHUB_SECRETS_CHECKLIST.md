# 🔐 GitHub Secrets Verification Checklist

## Purpose
This checklist helps you verify and fix the GitHub Secrets needed for CI/CD deployment.

---

## ✅ Step-by-Step Verification

### Step 1: Access GitHub Secrets Page

1. Open your browser and go to:
   ```
   https://github.com/anshavvayeda/DS-latest/settings/secrets/actions
   ```

2. You should see a page titled **"Actions secrets and variables"**

3. Under "Repository secrets", you should see 3 secrets listed

---

### Step 2: Verify Required Secrets Exist

Check if these 3 secrets are present:

- [ ] **EC2_HOST** 
- [ ] **EC2_USERNAME**
- [ ] **EC2_SSH_KEY**

**If ALL 3 exist:** Go to Step 3  
**If ANY are missing:** Go to Step 4 to create them

---

### Step 3: Verify Secret Values (Without Viewing)

GitHub doesn't show secret values for security, but you can verify they're correct by:

1. **EC2_HOST** should be:
   - Value: `13.201.25.124`
   - Click "Update" to change if needed

2. **EC2_USERNAME** should be:
   - Value: `ubuntu`
   - Click "Update" to change if needed

3. **EC2_SSH_KEY** should be:
   - The ENTIRE content of your `DhruvStar_key.pem` file
   - Including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`
   - No extra spaces or newlines at the beginning or end

**If you're not sure EC2_SSH_KEY is correct:** Delete it and recreate (go to Step 4c)

---

### Step 4: Create/Update Secrets

#### 4a. Create EC2_HOST

1. Click **"New repository secret"**
2. Name: `EC2_HOST`
3. Value: `13.201.25.124`
4. Click **"Add secret"**

---

#### 4b. Create EC2_USERNAME

1. Click **"New repository secret"**
2. Name: `EC2_USERNAME`
3. Value: `ubuntu`
4. Click **"Add secret"**

---

#### 4c. Create EC2_SSH_KEY (⚠️ MOST IMPORTANT)

This is the most common source of errors. Follow carefully:

1. **Get your SSH key file** (`DhruvStar_key.pem`)
   - On **Windows**: Open with Notepad
   - On **Mac/Linux**: Use `cat DhruvStar_key.pem`

2. **Copy the ENTIRE file content**
   
   **It should look like this:**
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEAzXc2YourActualKeyContentHere
   (many lines of random characters)
   ...
   -----END RSA PRIVATE KEY-----
   ```

3. **Important requirements:**
   - ✅ Must include `-----BEGIN RSA PRIVATE KEY-----`
   - ✅ Must include `-----END RSA PRIVATE KEY-----`
   - ✅ NO extra blank lines before BEGIN
   - ✅ NO extra blank lines after END
   - ✅ NO extra spaces anywhere

4. **Add to GitHub:**
   - Click **"New repository secret"** (or "Update" if it exists)
   - Name: `EC2_SSH_KEY`
   - Value: Paste the ENTIRE key content
   - Click **"Add secret"** or **"Update secret"**

---

### Step 5: Verify Using Test Workflow

1. **Commit the test workflow to GitHub:**
   ```bash
   cd /app
   git add .github/workflows/test-ssh-connection.yml
   git commit -m "Add SSH connection test workflow"
   git push origin main
   ```

2. **Go to GitHub Actions:**
   ```
   https://github.com/anshavvayeda/DS-latest/actions
   ```

3. **Run the test workflow:**
   - Click "Test SSH Connection" in the left sidebar
   - Click "Run workflow" button (top right)
   - Select branch: `main`
   - Click green "Run workflow" button
   - Wait 30-60 seconds

4. **Check the result:**
   - Click on the workflow run that appears
   - Click "Test SSH to EC2"
   - View the logs

**Expected Output:**
```
✅ EC2_HOST is configured
✅ EC2_USERNAME is configured
✅ EC2_SSH_KEY is configured
EC2_SSH_KEY length: XXXX characters

========================================
✅ SSH Connection Successful!
========================================
Hostname: ip-xxx-xx-xx-xxx
User: ubuntu
...
```

---

### Step 6: Troubleshooting Common Errors

#### Error: "EC2_SSH_KEY is NOT configured"
**Solution:** The secret doesn't exist. Go back to Step 4c.

---

#### Error: "Permission denied (publickey)"
**Solution:** The SSH key is incorrect or corrupted.

**Fix:**
1. Delete the `EC2_SSH_KEY` secret in GitHub
2. Get a fresh copy of `DhruvStar_key.pem`
3. Verify the file is not corrupted:
   ```bash
   # Test locally first
   ssh -i DhruvStar_key.pem ubuntu@13.201.25.124 "echo success"
   ```
4. If local test works, recreate the GitHub secret (Step 4c)
5. Make sure you copy the EXACT content with no modifications

---

#### Error: "Connection timeout" or "Connection refused"
**Solution:** EC2 security group is blocking GitHub Actions.

**Fix:**
1. Go to AWS Console → EC2 → Security Groups
2. Find the security group for your instance (13.201.25.124)
3. Edit inbound rules
4. Ensure SSH (port 22) is allowed from `0.0.0.0/0` (for testing)
5. Re-run the test workflow

---

#### Error: "Host key verification failed"
**Solution:** This is usually not an issue with appleboy/ssh-action, but if it occurs:

**Fix:** Add this to the workflow (already included in our workflow):
```yaml
with:
  host: ${{ secrets.EC2_HOST }}
  username: ${{ secrets.EC2_USERNAME }}
  key: ${{ secrets.EC2_SSH_KEY }}
  port: 22
```

---

## 🎯 Final Checklist

Before proceeding with full deployment, ensure:

- [ ] All 3 secrets exist in GitHub
- [ ] Test SSH workflow passes successfully
- [ ] You can see "✅ SSH Connection Successful!" in the logs
- [ ] EC2 setup script has been run (if warning appears)

---

## 🚀 Next Steps After Secrets Are Fixed

Once the test SSH workflow succeeds:

1. **Run the full deployment:**
   ```bash
   cd /app
   echo "# Test deployment" >> README.md
   git add README.md
   git commit -m "Test full CI/CD deployment"
   git push origin main
   ```

2. **Monitor the deployment:**
   - Go to: https://github.com/anshavvayeda/DS-latest/actions
   - Click on the running workflow
   - Watch the deployment logs

3. **Verify the deployment:**
   - SSH to EC2: `ssh -i DhruvStar_key.pem ubuntu@13.201.25.124`
   - Check backend: `sudo systemctl status studybuddy-backend`
   - Check frontend: `ls -la /var/www/studybuddy`
   - Test in browser: Visit your EC2 IP or domain

---

## 📞 Still Having Issues?

If you've followed all steps and it still fails:

1. **Check the exact error message** in GitHub Actions logs
2. **Share the error message** (without sensitive info)
3. **Verify EC2 instance is running** in AWS Console
4. **Try manual SSH** from your local machine to ensure EC2 is accessible

---

**Document Version:** 1.0  
**Last Updated:** March 10, 2026
