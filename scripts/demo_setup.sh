#!/bin/bash
# =============================================================================
# StudyBuddy WhatsApp Demo Setup Script
# =============================================================================
# This script simplifies the process of updating credentials for WhatsApp
# chatbot demos on EC2 instances.
#
# Usage: bash demo_setup.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  StudyBuddy WhatsApp Demo Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Detect environment
ENV_FILE=""
SERVICE_NAME=""
VENV_PATH=""

if [ -f "/home/ubuntu/studybuddy/backend/.env" ]; then
    ENV_FILE="/home/ubuntu/studybuddy/backend/.env"
    SERVICE_NAME="studybuddy-backend"
    VENV_PATH="/home/ubuntu/studybuddy/venv"
    echo -e "${GREEN}Detected: EC2 deployment${NC}"
elif [ -f "/app/backend/.env" ]; then
    ENV_FILE="/app/backend/.env"
    SERVICE_NAME="backend"
    echo -e "${GREEN}Detected: Emergent preview environment${NC}"
else
    echo -e "${RED}Error: Cannot find backend .env file${NC}"
    echo "Expected at /home/ubuntu/studybuddy/backend/.env or /app/backend/.env"
    exit 1
fi

echo -e "Using env file: ${YELLOW}$ENV_FILE${NC}"
echo ""

# Show current values (masked)
echo -e "${BLUE}Current Configuration:${NC}"
CURRENT_TOKEN=$(grep "^WHATSAPP_ACCESS_TOKEN=" "$ENV_FILE" | cut -d'=' -f2-)
CURRENT_NGROK=$(grep "^WHATSAPP_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2-)
CURRENT_OPENROUTER=$(grep "^SARVAM_API_KEY=" "$ENV_FILE" | cut -d'=' -f2-)

if [ -n "$CURRENT_TOKEN" ]; then
    echo -e "  WhatsApp Token: ${YELLOW}${CURRENT_TOKEN:0:15}...${NC}"
else
    echo -e "  WhatsApp Token: ${RED}Not set${NC}"
fi

if [ -n "$CURRENT_NGROK" ]; then
    echo -e "  Base URL:       ${YELLOW}$CURRENT_NGROK${NC}"
else
    echo -e "  Base URL:       ${RED}Not set${NC}"
fi

if [ -n "$CURRENT_OPENROUTER" ]; then
    echo -e "  Sarvam Key:     ${YELLOW}${CURRENT_OPENROUTER:0:15}...${NC}"
else
    echo -e "  Sarvam Key:     ${RED}Not set${NC}"
fi
echo ""

# Menu
echo -e "${BLUE}What would you like to update?${NC}"
echo "  1) WhatsApp Access Token"
echo "  2) ngrok/Public URL (Base URL)"
echo "  3) Sarvam AI API Key"
echo "  4) All of the above"
echo "  5) Clear WhatsApp chat history (for fresh testing)"
echo "  6) Exit"
echo ""
read -p "Choose [1-6]: " CHOICE

update_env_var() {
    local KEY="$1"
    local VALUE="$2"
    local FILE="$3"

    if grep -q "^${KEY}=" "$FILE"; then
        sed -i "s|^${KEY}=.*|${KEY}=${VALUE}|" "$FILE"
    else
        echo "${KEY}=${VALUE}" >> "$FILE"
    fi
}

restart_service() {
    echo ""
    echo -e "${YELLOW}Restarting backend service...${NC}"
    if [ "$SERVICE_NAME" = "studybuddy-backend" ]; then
        sudo systemctl restart "$SERVICE_NAME"
        sleep 2
        if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "${GREEN}Service restarted successfully${NC}"
        else
            echo -e "${RED}Service failed to start. Check logs:${NC}"
            echo "  sudo journalctl -u $SERVICE_NAME -n 20 --no-pager"
        fi
    else
        sudo supervisorctl restart "$SERVICE_NAME"
        sleep 2
        echo -e "${GREEN}Service restarted${NC}"
    fi
}

case $CHOICE in
    1)
        echo ""
        echo -e "${YELLOW}Get a new token from:${NC}"
        echo "  https://developers.facebook.com/tools/explorer/"
        echo "  Select your app > Generate User Token > whatsapp_business_messaging permission"
        echo ""
        read -p "Paste new WhatsApp Access Token: " NEW_TOKEN
        if [ -z "$NEW_TOKEN" ]; then
            echo -e "${RED}No token provided. Exiting.${NC}"
            exit 1
        fi
        update_env_var "WHATSAPP_ACCESS_TOKEN" "$NEW_TOKEN" "$ENV_FILE"
        echo -e "${GREEN}WhatsApp token updated${NC}"
        restart_service
        ;;
    2)
        echo ""
        echo -e "${YELLOW}Steps to get ngrok URL:${NC}"
        echo "  1. Start ngrok: ngrok http 8000"
        echo "  2. Copy the https://xxxxx.ngrok-free.app URL"
        echo "  3. Update Meta webhook: Meta Dashboard > WhatsApp > Configuration"
        echo "     Callback URL: https://xxxxx.ngrok-free.app/api/whatsapp/webhook"
        echo "     Verify Token: studybuddy_webhook"
        echo ""
        read -p "Paste ngrok/public URL (e.g., https://xxxx.ngrok-free.app): " NEW_URL
        if [ -z "$NEW_URL" ]; then
            echo -e "${RED}No URL provided. Exiting.${NC}"
            exit 1
        fi
        NEW_URL="${NEW_URL%/}"
        update_env_var "WHATSAPP_BASE_URL" "$NEW_URL" "$ENV_FILE"
        echo -e "${GREEN}Base URL updated to: $NEW_URL${NC}"
        echo ""
        echo -e "${YELLOW}IMPORTANT: Update the Meta webhook callback URL to:${NC}"
        echo -e "  ${GREEN}${NEW_URL}/api/whatsapp/webhook${NC}"
        echo ""
        restart_service
        ;;
    3)
        echo ""
        read -p "Paste new Sarvam AI API Key: " NEW_KEY
        if [ -z "$NEW_KEY" ]; then
            echo -e "${RED}No key provided. Exiting.${NC}"
            exit 1
        fi
        update_env_var "SARVAM_API_KEY" "$NEW_KEY" "$ENV_FILE"
        echo -e "${GREEN}Sarvam AI key updated${NC}"
        restart_service
        ;;
    4)
        echo ""
        echo -e "${YELLOW}=== Step 1/3: WhatsApp Access Token ===${NC}"
        echo "  Get from: https://developers.facebook.com/tools/explorer/"
        read -p "  Paste token (or press Enter to skip): " NEW_TOKEN
        if [ -n "$NEW_TOKEN" ]; then
            update_env_var "WHATSAPP_ACCESS_TOKEN" "$NEW_TOKEN" "$ENV_FILE"
            echo -e "  ${GREEN}Token updated${NC}"
        else
            echo -e "  ${YELLOW}Skipped${NC}"
        fi

        echo ""
        echo -e "${YELLOW}=== Step 2/3: ngrok/Public URL ===${NC}"
        echo "  Start ngrok: ngrok http 8000"
        read -p "  Paste URL (or press Enter to skip): " NEW_URL
        if [ -n "$NEW_URL" ]; then
            NEW_URL="${NEW_URL%/}"
            update_env_var "WHATSAPP_BASE_URL" "$NEW_URL" "$ENV_FILE"
            echo -e "  ${GREEN}URL updated to: $NEW_URL${NC}"
            echo -e "  ${YELLOW}Remember: Update Meta webhook to: ${NEW_URL}/api/whatsapp/webhook${NC}"
        else
            echo -e "  ${YELLOW}Skipped${NC}"
        fi

        echo ""
        echo -e "${YELLOW}=== Step 3/3: Sarvam AI API Key ===${NC}"
        read -p "  Paste key (or press Enter to skip): " NEW_KEY
        if [ -n "$NEW_KEY" ]; then
            update_env_var "SARVAM_API_KEY" "$NEW_KEY" "$ENV_FILE"
            echo -e "  ${GREEN}Key updated${NC}"
        else
            echo -e "  ${YELLOW}Skipped${NC}"
        fi

        restart_service
        ;;
    5)
        echo ""
        echo -e "${YELLOW}Clearing WhatsApp chat history and cached briefs...${NC}"
        if [ -n "$VENV_PATH" ]; then
            source "$VENV_PATH/bin/activate"
        fi
        python3 -c "
import asyncio, os, sys
sys.path.insert(0, '$(dirname $ENV_FILE)/..')

async def clear():
    from app.models.database import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        await db.execute(text('DELETE FROM whatsapp_chat_memory'))
        await db.execute(text('DELETE FROM whatsapp_parent_briefs'))
        await db.commit()
        print('Chat history and briefs cleared.')

asyncio.run(clear())
" 2>/dev/null || echo -e "${YELLOW}Manual cleanup: Run these SQL commands on your database:${NC}
  DELETE FROM whatsapp_chat_memory;
  DELETE FROM whatsapp_parent_briefs;"
        echo -e "${GREEN}Done. The next WhatsApp message will be treated as a first-time greeting.${NC}"
        ;;
    6)
        echo -e "${GREEN}Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "To verify, check logs:"
if [ "$SERVICE_NAME" = "studybuddy-backend" ]; then
    echo "  sudo journalctl -u $SERVICE_NAME -n 20 --no-pager"
else
    echo "  tail -n 20 /var/log/supervisor/backend.err.log"
fi
echo ""
