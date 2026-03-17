#!/bin/bash
# =============================================================================
# WhatsApp Chatbot Setup Script for EC2
# Run this ONCE after CI/CD deploys the WhatsApp code
# Usage: bash scripts/setup_whatsapp_ec2.sh
# =============================================================================

set -e
APP_DIR="/home/ubuntu/studybuddy"
ENV_FILE="$APP_DIR/backend/.env"

echo "========================================"
echo "WhatsApp Chatbot - EC2 Setup"
echo "========================================"

# 1. Add WhatsApp env vars to backend .env (if not already present)
if grep -q "WHATSAPP_PHONE_NUMBER_ID" "$ENV_FILE" 2>/dev/null; then
    echo "✅ WhatsApp env vars already exist in .env"
else
    echo ""
    echo "Adding WhatsApp credentials to $ENV_FILE..."
    cat >> "$ENV_FILE" << 'WHATSAPP_ENV'

WHATSAPP_PHONE_NUMBER_ID=1076686518851192
WHATSAPP_ACCESS_TOKEN=EAANSIehahqEBQ8F7ApaTysQ0OwhKUVKIAuFw7nF0ZCY9krrMESankx4Ak8R6cYvNp1zpRQavOvANkjjuZBIfINp6QvRDZCui4ZCKB7lCDnNtvxheJ321NSpyRRzuZCRdqszwTDfWtWXomSWsky2AXCmDzxk2qlIeHhfb7UBcGhvDWEZBXhmaZAhATgDBXZBWZBoZAQdInqvZAfxmhcn8RXzw1HvCxk3eU1d8NaGSBosXo5u4iL6DYJ75CO39bItVuKFeVPZAOPBInyNpRSRcuv9q2GANODfd
WHATSAPP_BUSINESS_ACCOUNT_ID=906392475486834
WHATSAPP_VERIFY_TOKEN=studybuddy_webhook
WHATSAPP_ENV
    echo "✅ WhatsApp env vars added"
fi

# 2. Add WHATSAPP_BASE_URL (ngrok URL - UPDATE THIS with your ngrok URL)
echo ""
read -p "Enter your ngrok HTTPS URL (e.g. https://abc123.ngrok-free.app): " NGROK_URL

if [ -n "$NGROK_URL" ]; then
    # Remove trailing slash
    NGROK_URL="${NGROK_URL%/}"
    
    if grep -q "WHATSAPP_BASE_URL" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|WHATSAPP_BASE_URL=.*|WHATSAPP_BASE_URL=$NGROK_URL|" "$ENV_FILE"
    else
        echo "WHATSAPP_BASE_URL=$NGROK_URL" >> "$ENV_FILE"
    fi
    echo "✅ WHATSAPP_BASE_URL set to $NGROK_URL"
fi

# 3. Restart backend
echo ""
echo "Restarting backend..."
sudo systemctl restart studybuddy-backend
sleep 5

if sudo systemctl is-active --quiet studybuddy-backend; then
    echo "✅ Backend is running"
else
    echo "❌ Backend failed to start. Check logs:"
    echo "   sudo journalctl -u studybuddy-backend -n 30 --no-pager"
    exit 1
fi

# 4. Test webhook
echo ""
echo "Testing webhook verification..."
RESPONSE=$(curl -s "http://localhost:8001/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=studybuddy_webhook&hub.challenge=test_ok")
if [ "$RESPONSE" = "test_ok" ]; then
    echo "✅ Webhook verification working!"
else
    echo "❌ Webhook test failed. Response: $RESPONSE"
    exit 1
fi

echo ""
echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Start ngrok:  ngrok http 80"
echo "2. Copy the HTTPS URL from ngrok output"
echo "3. Go to Meta Developer Portal → WhatsApp → Configuration"
echo "4. Set Callback URL: <ngrok-url>/api/whatsapp/webhook"
echo "5. Set Verify Token: studybuddy_webhook"
echo "6. Subscribe to 'messages' field"
echo "7. Send a WhatsApp message to test!"
echo ""
echo "If you change ngrok URL, run this script again to update WHATSAPP_BASE_URL"
echo "========================================"
