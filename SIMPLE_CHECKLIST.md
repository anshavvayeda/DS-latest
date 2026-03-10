# ✅ CI/CD Fix - Simple Checklist

Print this page and check off each step as you complete it!

---

## Part 1: Push Code ⏱️ 2 minutes

- [ ] **Step 1:** Open terminal/command prompt
- [ ] **Step 2:** Copy and paste: `cd /app && git push origin main`
- [ ] **Step 3:** Press Enter
- [ ] **Step 4:** Wait for "done" message

---

## Part 2: Fix GitHub Secrets ⏱️ 5-10 minutes

### Open GitHub Secrets Page
- [ ] **Step 5:** Open browser
- [ ] **Step 6:** Go to: `https://github.com/anshavvayeda/DS-latest/settings/secrets/actions`

### Create/Update EC2_HOST
- [ ] **Step 7:** Click "New repository secret" (or Update if exists)
- [ ] **Step 8:** Name: `EC2_HOST`
- [ ] **Step 9:** Value: `13.201.25.124`
- [ ] **Step 10:** Click "Add secret"

### Create/Update EC2_USERNAME
- [ ] **Step 11:** Click "New repository secret" (or Update)
- [ ] **Step 12:** Name: `EC2_USERNAME`
- [ ] **Step 13:** Value: `ubuntu`
- [ ] **Step 14:** Click "Add secret"

### Create/Update EC2_SSH_KEY (MOST IMPORTANT!)
- [ ] **Step 15:** Find file `DhruvStar_key.pem` on your computer
- [ ] **Step 16:** Open it with Notepad (Windows) or TextEdit (Mac)
- [ ] **Step 17:** Select all text (Ctrl+A or Cmd+A)
- [ ] **Step 18:** Copy it (Ctrl+C or Cmd+C)
- [ ] **Step 19:** Go back to GitHub
- [ ] **Step 20:** Click "New repository secret" (or Update)
- [ ] **Step 21:** Name: `EC2_SSH_KEY`
- [ ] **Step 22:** Click in Value box and paste (Ctrl+V or Cmd+V)
- [ ] **Step 23:** Check it starts with `-----BEGIN RSA PRIVATE KEY-----`
- [ ] **Step 24:** Check it ends with `-----END RSA PRIVATE KEY-----`
- [ ] **Step 25:** Click "Add secret"

### Verify All Secrets
- [ ] **Step 26:** I can see EC2_HOST in the list
- [ ] **Step 27:** I can see EC2_USERNAME in the list
- [ ] **Step 28:** I can see EC2_SSH_KEY in the list

---

## Part 3: Test Connection ⏱️ 2 minutes

### Run Test
- [ ] **Step 29:** Go to: `https://github.com/anshavvayeda/DS-latest/actions`
- [ ] **Step 30:** Click "Test SSH Connection" in left sidebar
- [ ] **Step 31:** Click "Run workflow" button
- [ ] **Step 32:** Select Branch: main
- [ ] **Step 33:** Click green "Run workflow" button
- [ ] **Step 34:** Wait 10 seconds, then refresh page (F5)

### Check Result
- [ ] **Step 35:** Click on the workflow run that appeared
- [ ] **Step 36:** Click "Test SSH to EC2"
- [ ] **Step 37:** Wait for it to finish (30-60 seconds)

### Did It Work?
- [ ] **✅ I see "SSH Connection Successful!"** → Continue to Part 4
- [ ] **❌ I see an error** → See "Common Errors" section below

---

## Part 4: Deploy! ⏱️ 5-10 minutes

### Trigger Deployment
- [ ] **Step 38:** In terminal, run:
  ```bash
  cd /app
  echo "# Deploy" >> README.md
  git add README.md
  git commit -m "Deploy to EC2"
  git push origin main
  ```
- [ ] **Step 39:** Go to: `https://github.com/anshavvayeda/DS-latest/actions`
- [ ] **Step 40:** Click the newest "Deploy StudyBuddy to EC2" workflow
- [ ] **Step 41:** Click "Deploy to EC2"
- [ ] **Step 42:** Watch the logs (5-10 minutes)

### Verify Success
- [ ] **Step 43:** I see "✅ Deployment Completed Successfully!"
- [ ] **Step 44:** Open browser and visit: `http://13.201.25.124`
- [ ] **Step 45:** I can see my StudyBuddy app!

---

## 🎉 DONE!
You've successfully set up CI/CD! Every time you push code to GitHub, it will now automatically deploy to your EC2 server.

---

## ❌ Common Errors & Quick Fixes

### Error: "Permission denied (publickey)"
**Fix:**
- [ ] Go back to Step 15
- [ ] Make SURE you copied the ENTIRE file
- [ ] Make sure NO blank lines at top or bottom
- [ ] Delete EC2_SSH_KEY secret and create it again

### Error: "Connection timeout"
**Fix:**
- [ ] Tell me you got this error - needs AWS console access
- [ ] We need to fix EC2 security group

### Error: "EC2_SSH_KEY is NOT configured"
**Fix:**
- [ ] Go back to Step 20
- [ ] Create the EC2_SSH_KEY secret
- [ ] Run test again from Step 29

### Error: Can't find "Test SSH Connection" workflow
**Fix:**
- [ ] Go back to Step 2
- [ ] Make sure push succeeded
- [ ] Try: `cd /app && git push origin main --force`
- [ ] Refresh GitHub Actions page

---

## 📞 Need Help?

Tell me:
1. What step number you're on
2. What error you see
3. Screenshot if possible

I'll help you! 😊

---

**Time to complete:** 15-25 minutes total
**Difficulty:** Beginner friendly
**Prerequisites:** Access to GitHub, DhruvStar_key.pem file
