#!/bin/bash
set -e

# BugZap.ai SSL Setup Script
# This script sets up Let's Encrypt SSL certificates using Docker-based certbot
# It also configures the VS Code editor port for remote access

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "BugZap.ai SSL Setup Script"
echo "=========================================="

# Default values for bugzap.ai
DOMAIN="${1:-bugzap.ai}"
EMAIL="${2:-admin@bugzap.ai}"

echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup-ssl.sh $DOMAIN $EMAIL)"
    exit 1
fi

# Determine docker compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Step 1: Create required directories
echo "Step 1: Creating certbot directories..."
mkdir -p ./certbot/www ./certbot/conf

# Step 2: Open firewall ports
echo "Step 2: Opening firewall ports..."
ufw allow 80 || true
ufw allow 443 || true
ufw allow 41234 || true  # VS Code editor port

# Step 3: Stop existing containers
echo "Step 3: Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.prod.yml down || true

# Step 4: Start a temporary nginx for certificate acquisition
echo "Step 4: Starting temporary nginx for certificate acquisition..."
cat > ./nginx/nginx-temp.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name _;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 200 'SSL setup in progress...';
            add_header Content-Type text/plain;
        }
    }
}
EOF

docker run -d --name nginx-temp \
    -p 80:80 \
    -v $(pwd)/nginx/nginx-temp.conf:/etc/nginx/nginx.conf:ro \
    -v $(pwd)/certbot/www:/var/www/certbot:ro \
    nginx:alpine

# Wait for nginx to start
sleep 3

# Step 5: Obtain SSL certificate using Docker certbot
echo "Step 5: Obtaining SSL certificate from Let's Encrypt..."
docker run --rm \
    -v $(pwd)/certbot/www:/var/www/certbot:rw \
    -v $(pwd)/certbot/conf:/etc/letsencrypt:rw \
    certbot/certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# Step 6: Stop temporary nginx
echo "Step 6: Stopping temporary nginx..."
docker stop nginx-temp && docker rm nginx-temp
rm -f ./nginx/nginx-temp.conf

# Step 7: Start the full stack with SSL
echo "Step 7: Starting full stack with SSL enabled..."
$COMPOSE_CMD -f docker-compose.prod.yml up -d --build

echo ""
echo "=========================================="
echo "SSL Setup Complete!"
echo "=========================================="
echo ""
echo "Your BugZap.ai instance is now available at: https://$DOMAIN"
echo ""
echo "Features enabled:"
echo "  - HTTPS with Let's Encrypt (auto-renewal via certbot container)"
echo "  - VS Code editor port (41234) for remote repository access"
echo "  - Password protection via .htpasswd"
echo "  - V0 API for WebSocket compatibility"
echo ""
echo "To verify the certificate:"
echo "  curl -I https://$DOMAIN"
echo ""
echo "Certificate renewal is automatic via the certbot container (every 12 hours)."
echo ""
