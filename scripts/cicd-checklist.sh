#!/bin/bash
# Quick CI/CD Setup Checklist Script

echo "========================================="
echo "🚀 StudyBuddy CI/CD Setup Checklist"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_mark="${GREEN}✅${NC}"
cross_mark="${RED}❌${NC}"
warning_mark="${YELLOW}⚠️${NC}"

echo "📋 Checking local setup..."
echo ""

# Check if GitHub workflow exists
if [ -f ".github/workflows/deploy-to-ec2.yml" ]; then
    echo -e "${check_mark} GitHub workflow file exists"
else
    echo -e "${cross_mark} GitHub workflow file missing"
    echo "   Run this from the repository root"
fi

# Check if EC2 setup script exists
if [ -f "scripts/ec2-setup.sh" ]; then
    echo -e "${check_mark} EC2 setup script exists"
else
    echo -e "${cross_mark} EC2 setup script missing"
fi

# Check if documentation exists
if [ -f "CICD_SETUP.md" ]; then
    echo -e "${check_mark} CI/CD documentation exists"
else
    echo -e "${cross_mark} CI/CD documentation missing"
fi

# Check if .gitignore includes .env
if grep -q "*.env" .gitignore 2>/dev/null; then
    echo -e "${check_mark} .gitignore includes .env files"
else
    echo -e "${warning_mark} .gitignore might not exclude .env files"
fi

# Check if connected to GitHub
if git remote get-url origin &>/dev/null; then
    REPO_URL=$(git remote get-url origin)
    echo -e "${check_mark} Connected to GitHub: $REPO_URL"
else
    echo -e "${cross_mark} Not connected to GitHub repository"
    echo "   Connect with: git remote add origin <your-repo-url>"
fi

echo ""
echo "========================================="
echo "📝 Next Steps:"
echo "========================================="
echo ""
echo "1️⃣  Transfer ec2-setup.sh to EC2 and run it:"
echo "   scp -i DhruvStar_key.pem scripts/ec2-setup.sh ubuntu@13.201.25.124:/home/ubuntu/"
echo "   ssh -i DhruvStar_key.pem ubuntu@13.201.25.124"
echo "   chmod +x ec2-setup.sh && ./ec2-setup.sh"
echo ""
echo "2️⃣  Configure environment files on EC2:"
echo "   - /home/ubuntu/studybuddy/backend/.env"
echo "   - /home/ubuntu/studybuddy/frontend/.env"
echo ""
echo "3️⃣  Add GitHub Secrets (in repository Settings → Secrets):"
echo "   - EC2_HOST = 13.201.25.124"
echo "   - EC2_USERNAME = ubuntu"
echo "   - EC2_SSH_KEY = <content of DhruvStar_key.pem>"
echo ""
echo "4️⃣  Commit and push to trigger deployment:"
echo "   git add ."
echo "   git commit -m 'Setup CI/CD pipeline'"
echo "   git push origin main"
echo ""
echo "5️⃣  Monitor deployment in GitHub Actions tab"
echo ""
echo "========================================="
echo "📚 Full documentation: CICD_SETUP.md"
echo "========================================="
