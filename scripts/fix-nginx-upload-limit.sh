#!/bin/bash
# Fix Nginx 413 Error - Increase Upload Limit
# This script increases the file upload size limit on EC2

echo "🔧 Fixing Nginx Upload Limit (413 Error)"
echo "=========================================="

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "❌ Nginx not found"
    exit 1
fi

# Find the main Nginx configuration file
NGINX_CONF="/etc/nginx/nginx.conf"
SITE_CONF="/etc/nginx/sites-available/studybuddy"
SITE_ENABLED="/etc/nginx/sites-enabled/studybuddy"

# Backup current config
sudo cp $NGINX_CONF ${NGINX_CONF}.backup
echo "✅ Backed up nginx.conf"

# Check if client_max_body_size is already set in main config
if grep -q "client_max_body_size" $NGINX_CONF; then
    echo "⚠️  client_max_body_size already exists in nginx.conf"
    sudo sed -i 's/client_max_body_size.*/client_max_body_size 30M;/' $NGINX_CONF
    echo "✅ Updated existing client_max_body_size to 30M"
else
    # Add to http block
    sudo sed -i '/http {/a \    client_max_body_size 30M;' $NGINX_CONF
    echo "✅ Added client_max_body_size 30M to http block"
fi

# Also update in site-specific config if it exists
if [ -f "$SITE_CONF" ]; then
    sudo sed -i 's/client_max_body_size.*/client_max_body_size 30M;/' $SITE_CONF
    echo "✅ Updated site-specific config"
fi

# Test Nginx configuration
echo ""
echo "Testing Nginx configuration..."
if sudo nginx -t; then
    echo "✅ Nginx configuration is valid"
    
    # Reload Nginx
    echo ""
    echo "Reloading Nginx..."
    sudo systemctl reload nginx
    
    if [ $? -eq 0 ]; then
        echo "✅ Nginx reloaded successfully"
        echo ""
        echo "=========================================="
        echo "✅ Fix Applied Successfully!"
        echo "=========================================="
        echo "Upload limit increased to 30MB"
        echo "Teachers can now upload PDFs up to 30MB"
        echo "=========================================="
    else
        echo "❌ Failed to reload Nginx"
        exit 1
    fi
else
    echo "❌ Nginx configuration has errors"
    echo "Restoring backup..."
    sudo cp ${NGINX_CONF}.backup $NGINX_CONF
    exit 1
fi
