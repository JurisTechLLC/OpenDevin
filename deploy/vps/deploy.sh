#!/bin/bash
set -e

# OpenHands Deployment Script
# This script deploys or updates OpenHands on a VPS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "OpenHands Deployment Script"
echo "=========================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables
source .env

# Validate required environment variables
if [ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "your-secure-jwt-secret-here" ]; then
    echo "Error: JWT_SECRET is not configured in .env"
    exit 1
fi

if [ -z "$GITHUB_APP_CLIENT_ID" ] || [ "$GITHUB_APP_CLIENT_ID" = "your-github-client-id" ]; then
    echo "Error: GITHUB_APP_CLIENT_ID is not configured in .env"
    exit 1
fi

if [ -z "$GITHUB_APP_CLIENT_SECRET" ] || [ "$GITHUB_APP_CLIENT_SECRET" = "your-github-client-secret" ]; then
    echo "Error: GITHUB_APP_CLIENT_SECRET is not configured in .env"
    exit 1
fi

echo "Configuration validated."

# Create necessary directories
echo "Creating directories..."
mkdir -p nginx/ssl
mkdir -p nginx/certbot
mkdir -p "${WORKSPACE_BASE:-/opt/openhands/workspace}"

# Check if we should pull latest code
if [ "$1" = "--update" ] || [ "$1" = "-u" ]; then
    echo "Pulling latest code..."
    cd ../..
    git pull origin main
    cd "$SCRIPT_DIR"
fi

# Build and deploy
echo "Building and deploying OpenHands..."

# Use docker compose (v2) or docker-compose (v1)
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Stop existing containers
echo "Stopping existing containers..."
$COMPOSE_CMD -f docker-compose.prod.yml down --remove-orphans || true

# Build the image
echo "Building Docker image..."
$COMPOSE_CMD -f docker-compose.prod.yml build

# Start the containers
echo "Starting containers..."
$COMPOSE_CMD -f docker-compose.prod.yml up -d

# Wait for health check
echo "Waiting for OpenHands to be ready..."
sleep 10

# Check if containers are running
if $COMPOSE_CMD -f docker-compose.prod.yml ps | grep -q "Up"; then
    echo ""
    echo "=========================================="
    echo "Deployment Successful!"
    echo "=========================================="
    echo ""
    echo "OpenHands is now running!"
    echo ""
    if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "openhands.yourdomain.com" ]; then
        echo "Access your instance at: https://$DOMAIN"
    else
        echo "Access your instance at: http://$(curl -s ifconfig.me):80"
    fi
    echo ""
    echo "To view logs: $COMPOSE_CMD -f docker-compose.prod.yml logs -f"
    echo "To stop: $COMPOSE_CMD -f docker-compose.prod.yml down"
    echo ""
else
    echo "Error: Containers failed to start. Check logs with:"
    echo "$COMPOSE_CMD -f docker-compose.prod.yml logs"
    exit 1
fi
