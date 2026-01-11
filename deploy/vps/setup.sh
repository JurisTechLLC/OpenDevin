#!/bin/bash
set -e

# OpenHands VPS Setup Script
# This script sets up a fresh VPS for running OpenHands

echo "=========================================="
echo "OpenHands VPS Setup Script"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup.sh)"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS. Please install Docker manually."
    exit 1
fi

echo "Detected OS: $OS"

# Update system
echo "Updating system packages..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get update
    apt-get upgrade -y
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
    yum update -y
fi

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    echo "Docker installed successfully!"
else
    echo "Docker is already installed."
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed successfully!"
else
    echo "Docker Compose is already installed."
fi

# Install additional utilities
echo "Installing additional utilities..."
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get install -y curl git htop certbot
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
    yum install -y curl git htop certbot
fi

# Create OpenHands directories
echo "Creating OpenHands directories..."
mkdir -p /opt/openhands/workspace
mkdir -p /opt/openhands/data
mkdir -p /opt/openhands/ssl

# Set permissions
chmod 755 /opt/openhands
chmod 755 /opt/openhands/workspace
chmod 755 /opt/openhands/data

# Configure firewall (if ufw is available)
if command -v ufw &> /dev/null; then
    echo "Configuring firewall..."
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw --force enable
    echo "Firewall configured."
fi

# Configure Docker to start on boot
systemctl enable docker

# Print Docker info
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version 2>/dev/null || docker-compose --version)"
echo ""
echo "Next steps:"
echo "1. Copy your .env file to this directory"
echo "2. Update the .env file with your configuration"
echo "3. Run: ./deploy.sh"
echo ""
echo "For SSL setup, run: ./setup-ssl.sh your-domain.com your-email@example.com"
echo ""
