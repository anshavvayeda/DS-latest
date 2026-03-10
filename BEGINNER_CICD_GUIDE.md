# 🚀 CI/CD Fix - Complete Beginner's Guide

## What We're Going to Do

We need to fix the automatic deployment from GitHub to your EC2 server. Think of it like setting up a delivery system - when you send code to GitHub, it should automatically deliver to your EC2 server. Right now, that delivery isn't working.

**Time needed:** 15-20 minutes

---

## 📋 What You'll Need

Before starting, make sure you have:
- [ ] Access to GitHub.com
- [ ] Your GitHub account logged in
- [ ] The file `DhruvStar_key.pem` (your EC2 SSH key) on your computer

---

## Part 1: Push the Debugging Tools to GitHub

### Step 1: Push Code from This Environment

We've created some helpful files. Let's send them to GitHub.

**Copy and paste this command:**
```bash
cd /app && git push origin main
```

**What will happen:**
- You'll see some text scrolling
- It should say "Writing objects: 100%"
- At the end: "branch 'main' set up to track 'origin/main'"

**If you see an error about authentication:**
- This is normal if the repository is private
- We'll use the GitHub website instead (continue to Step 2)

---

## Part 2: Fix GitHub Secrets (THE MAIN FIX)

### Step 2: Open GitHub Secrets Page

1. **Open your web browser** (Chrome, Firefox, Safari, etc.)

2. **Copy this link and paste it in your browser:**
   ```
   https://github.com/anshavvayeda/DS-latest/settings/secrets/actions
   ```

3. **Press Enter**

4. **What you should see:**
   - A page with the title "Actions secrets and variables"
   - A section called "Repository secrets"
   - Maybe you see some secrets listed (EC2_HOST, EC2_USERNAME, EC2_SSH_KEY)
   - OR maybe the list is empty

---

### Step 3: Check What Secrets Exist

**Look at the "Repository secrets" section.**

**Do you see these 3 secrets listed?**
- EC2_HOST
- EC2_USERNAME  
- EC2_SSH_KEY

**Choose your situation:**
- ✅ **I see all 3 secrets** → Go to Step 4
- ❌ **I see some but not all** → Go to Step 5
- ❌ **I see none / the list is empty** → Go to Step 5

---

### Step 4: Update Existing Secrets (If You See Them)

**Let's update them to make sure they're correct.**

#### 4a. Update EC2_HOST

1. Find **EC2_HOST** in the list
2. Click the **pencil icon** (✏️) or "Update" button next to it
3. In the "Value" box, delete everything and type exactly:
   ```
   13.201.25.124
   ```
4. Click **"Update secret"** (green button)

#### 4b. Update EC2_USERNAME

1. Find **EC2_USERNAME** in the list
2. Click the **pencil icon** (✏️) or "Update" button
3. In the "Value" box, delete everything and type exactly:
   ```
   ubuntu
   ```
4. Click **"Update secret"**

#### 4c. Update EC2_SSH_KEY (MOST IMPORTANT!)

This is the trickiest one. Follow carefully:

1. Find **EC2_SSH_KEY** in the list
2. Click the **pencil icon** (✏️) or "Update" button
3. **Now we need to get the SSH key content:**

   **On Windows:**
   - Find the file `DhruvStar_key.pem` on your computer
   - Right-click it → Open with → Notepad
   - Click inside the Notepad window
   - Press `Ctrl + A` (select all)
   - Press `Ctrl + C` (copy)

   **On Mac:**
   - Find the file `DhruvStar_key.pem` on your computer
   - Right-click it → Open with → TextEdit
   - Click inside the TextEdit window
   - Press `Cmd + A` (select all)
   - Press `Cmd + C` (copy)

4. **Go back to the GitHub page**
5. Click inside the large "Value" text box
6. Delete everything that's there (if anything)
7. **Paste** what you copied (`Ctrl + V` on Windows, `Cmd + V` on Mac)

8. **IMPORTANT CHECK:** Your pasted text should look like this:
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA... (lots of random letters and numbers)
   ... (many lines)
   -----END RSA PRIVATE KEY-----
   ```

9. **Make sure:**
   - ✅ First line is `-----BEGIN RSA PRIVATE KEY-----`
   - ✅ Last line is `-----END RSA PRIVATE KEY-----`
   - ✅ No blank lines BEFORE the BEGIN line
   - ✅ No blank lines AFTER the END line

10. Click **"Update secret"** (green button)

**Done!** → Skip to Step 6

---

### Step 5: Create New Secrets (If They Don't Exist)

**We'll create all 3 secrets from scratch.**

#### 5a. Create EC2_HOST

1. Click the **"New repository secret"** button (top right, green button)
2. In "Name" box, type exactly:
   ```
   EC2_HOST
   ```
3. In "Secret" box, type exactly:
   ```
   13.201.25.124
   ```
4. Click **"Add secret"** (green button at bottom)

#### 5b. Create EC2_USERNAME

1. Click **"New repository secret"** again
2. In "Name" box, type exactly:
   ```
   EC2_USERNAME
   ```
3. In "Secret" box, type exactly:
   ```
   ubuntu
   ```
4. Click **"Add secret"**

#### 5c. Create EC2_SSH_KEY

1. Click **"New repository secret"** again
2. In "Name" box, type exactly:
   ```
   EC2_SSH_KEY
   ```
3. **Now get the SSH key content:**

   **On Windows:**
   - Find the file `DhruvStar_key.pem` on your computer
   - Right-click it → Open with → Notepad
   - Press `Ctrl + A` (select all)
   - Press `Ctrl + C` (copy)

   **On Mac:**
   - Find the file `DhruvStar_key.pem` on your computer
   - Right-click it → Open with → TextEdit
   - Press `Cmd + A` (select all)
   - Press `Cmd + C` (copy)

4. **Go back to GitHub**
5. Click inside the large "Secret" box
6. **Paste** what you copied (`Ctrl + V` or `Cmd + V`)

7. **IMPORTANT CHECK:** Your pasted text should look like:
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEpAIBAAKCAQEA... (lots of random text)
   ... (many lines)
   -----END RSA PRIVATE KEY-----
   ```

8. **Verify:**
   - ✅ Starts with `-----BEGIN RSA PRIVATE KEY-----`
   - ✅ Ends with `-----END RSA PRIVATE KEY-----`
   - ✅ No extra blank lines at top or bottom

9. Click **"Add secret"**

---

### Step 6: Verify All 3 Secrets Are There

**You should now see in the "Repository secrets" section:**
- ✅ EC2_HOST
- ✅ EC2_USERNAME
- ✅ EC2_SSH_KEY

**If you see all 3:** Great! Continue to Part 3

**If any are missing:** Go back and create the missing one(s)

---

## Part 3: Test the Connection

Now let's test if GitHub can connect to your EC2 server.

### Step 7: Go to GitHub Actions Page

1. **Copy this link and open it in your browser:**
   ```
   https://github.com/anshavvayeda/DS-latest/actions
   ```

2. **What you should see:**
   - A page titled "Actions"
   - A left sidebar with workflow names
   - Maybe some workflow runs in the middle

---

### Step 8: Run the Test Workflow

1. **In the left sidebar**, look for **"Test SSH Connection"**
   - If you DON'T see it, it means the code wasn't pushed yet
   - Go back to Step 1 and try pushing again

2. **Click on "Test SSH Connection"**

3. **You'll see a button that says "Run workflow"** (top right area, might be a dropdown)

4. **Click "Run workflow"**

5. **A small popup appears:**
   - Make sure "Branch: main" is selected
   - Click the green **"Run workflow"** button

6. **Wait 5-10 seconds, then refresh the page** (press F5 or click refresh)

7. **You should see a new workflow run appear** with a yellow dot (🟡) - this means it's running

---

### Step 9: Watch the Test Run

1. **Click on the workflow run** (it'll say "Test SSH Connection" with your commit message)

2. **Click on "Test SSH to EC2"** (you'll see this in the middle of the page)

3. **You'll see logs scrolling** - this shows what's happening

4. **Wait 30-60 seconds for it to complete**

---

### Step 10: Check If It Worked

**Look at the logs. You should see one of two results:**

#### ✅ SUCCESS - You'll See:
```
✅ EC2_HOST is configured
✅ EC2_USERNAME is configured
✅ EC2_SSH_KEY is configured
========================================
✅ SSH Connection Successful!
========================================
Hostname: ip-xxx-xx-xx-xxx
User: ubuntu
```

**If you see this:** 🎉 **SUCCESS!** Your GitHub can now connect to EC2!
→ **Go to Part 4**

---

#### ❌ FAILURE - You Might See:

**Error 1: "Permission denied (publickey)"**
```
Permission denied (publickey)
```
**This means:** Your SSH key is wrong or formatted incorrectly

**Fix:** 
- Go back to Step 4c or 5c
- Make SURE you copied the ENTIRE file content
- Make sure there are NO extra blank lines
- Try copying again carefully

---

**Error 2: "Connection timeout"**
```
ssh: connect to host 13.201.25.124 port 22: Connection timed out
```
**This means:** EC2 firewall is blocking GitHub

**Fix:** 
- You need to change EC2 security settings
- This requires AWS Console access
- Tell me "I got connection timeout error" and I'll help you fix it

---

**Error 3: "EC2_SSH_KEY is NOT configured"**
```
❌ EC2_SSH_KEY is NOT configured
```
**This means:** The secret wasn't created

**Fix:**
- Go back to Step 5c
- Create the EC2_SSH_KEY secret
- Run the test again (Step 8)

---

## Part 4: Deploy to EC2

Once the test succeeds, let's do the actual deployment!

### Step 11: Trigger Automatic Deployment

**Option A: Make a Small Change**

1. In your Emergent environment, run:
   ```bash
   cd /app
   echo "# Deployment test" >> README.md
   git add README.md
   git commit -m "Test deployment"
   git push origin main
   ```

2. **Go to GitHub Actions:**
   ```
   https://github.com/anshavvayeda/DS-latest/actions
   ```

3. **You should see a new workflow running** called "Deploy StudyBuddy to EC2"

4. **Click on it and watch the logs**

---

**Option B: Manual Trigger**

1. **Go to GitHub Actions:**
   ```
   https://github.com/anshavvayeda/DS-latest/actions
   ```

2. **Click "Deploy StudyBuddy to EC2"** in left sidebar

3. **Click "Run workflow"** button

4. Select "Branch: main"

5. Click green **"Run workflow"** button

---

### Step 12: Watch the Deployment

1. **Click on the running workflow**

2. **Click on "Deploy to EC2"**

3. **Watch the logs - you should see:**
   ```
   🚀 Starting StudyBuddy Deployment
   📥 Cloning repository...
   🔧 Backend Deployment
   📦 Installing Python dependencies...
   ▶️  Starting backend service...
   ✅ Backend service is running
   🎨 Frontend Deployment
   📦 Installing Node dependencies...
   🔨 Building frontend...
   ✅ Deployment Completed Successfully!
   ```

4. **Wait 5-10 minutes** for the full deployment

---

### Step 13: Verify Deployment Worked

**After deployment completes:**

1. **Open your browser**

2. **Visit your EC2 IP:**
   ```
   http://13.201.25.124
   ```

3. **You should see:** Your StudyBuddy application!

---

## 🎉 You're Done!

**What you've accomplished:**
- ✅ Set up GitHub Secrets
- ✅ Fixed the CI/CD pipeline
- ✅ Deployed StudyBuddy to EC2
- ✅ Now every time you push to GitHub, it auto-deploys!

---

## 🆘 Still Having Problems?

### Problem: Can't find DhruvStar_key.pem file

**Solution:**
- Check your Downloads folder
- Check your Desktop
- Search your computer for "DhruvStar_key.pem"
- If you can't find it, you need to download it again from AWS

---

### Problem: Test says "Permission denied" even after fixing

**Solution:**
1. Try opening `DhruvStar_key.pem` in a plain text editor (Notepad, TextEdit)
2. Make 100% sure you're copying ALL the text including the BEGIN and END lines
3. Delete the EC2_SSH_KEY secret in GitHub and create it fresh
4. Try the test again

---

### Problem: GitHub Actions page shows no workflows

**Solution:**
- The code wasn't pushed to GitHub yet
- Try this command again:
  ```bash
  cd /app && git push origin main
  ```
- Refresh the GitHub Actions page

---

### Problem: Can't access GitHub because "not authorized"

**Solution:**
- Make sure you're logged into the correct GitHub account
- The repository owner needs to give you access
- Contact the repository owner (anshavvayeda)

---

## 📞 Need More Help?

Just tell me:
- What step you're on
- What error message you see (copy and paste it)
- What happened vs what you expected

I'll help you fix it! 😊
