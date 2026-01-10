#!/bin/bash
set -e

# OpenHands Self-Hosted Deployment Script
# Usage: ./deploy.sh [command]
# Commands: start, stop, restart, logs, build, status, setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env() {
    if [ ! -f .env ]; then
        log_error ".env file not found. Please copy .env.example to .env and configure it."
        exit 1
    fi
    
    # Check required variables
    source .env
    if [ -z "$LLM_API_KEY" ] || [ "$LLM_API_KEY" = "your-api-key-here" ]; then
        log_error "LLM_API_KEY is not configured in .env"
        exit 1
    fi
    
    if [ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "your-jwt-secret-here" ]; then
        log_error "JWT_SECRET is not configured in .env"
        exit 1
    fi
    
    if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "your-secure-password-here" ]; then
        log_error "POSTGRES_PASSWORD is not configured in .env"
        exit 1
    fi
}

setup() {
    log_info "Setting up OpenHands deployment..."
    
    # Create .env if it doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env
        log_info "Created .env file from .env.example"
        log_warn "Please edit .env and configure your settings before starting"
        
        # Generate JWT secret
        JWT_SECRET=$(openssl rand -hex 32)
        sed -i "s/your-jwt-secret-here/$JWT_SECRET/" .env
        log_info "Generated JWT_SECRET"
        
        # Generate Postgres password
        POSTGRES_PASSWORD=$(openssl rand -hex 16)
        sed -i "s/your-secure-password-here/$POSTGRES_PASSWORD/" .env
        log_info "Generated POSTGRES_PASSWORD"
    fi
    
    # Create workspace directory
    mkdir -p workspace
    log_info "Created workspace directory"
    
    # Create SSL directory
    mkdir -p nginx/ssl
    log_info "Created SSL directory"
    
    log_info "Setup complete! Please configure your LLM_API_KEY in .env"
}

build() {
    log_info "Building OpenHands Docker image..."
    docker compose -f docker-compose.prod.yml build
    log_info "Build complete!"
}

start() {
    check_env
    log_info "Starting OpenHands..."
    docker compose -f docker-compose.prod.yml up -d
    log_info "OpenHands started! Access it at http://localhost:${OPENHANDS_PORT:-3000}"
}

stop() {
    log_info "Stopping OpenHands..."
    docker compose -f docker-compose.prod.yml down
    log_info "OpenHands stopped."
}

restart() {
    stop
    start
}

logs() {
    docker compose -f docker-compose.prod.yml logs -f "$@"
}

status() {
    docker compose -f docker-compose.prod.yml ps
}

pull() {
    log_info "Pulling latest images..."
    docker compose -f docker-compose.prod.yml pull
}

# Main command handler
case "${1:-help}" in
    setup)
        setup
        ;;
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        shift
        logs "$@"
        ;;
    status)
        status
        ;;
    pull)
        pull
        ;;
    help|*)
        echo "OpenHands Self-Hosted Deployment"
        echo ""
        echo "Usage: ./deploy.sh [command]"
        echo ""
        echo "Commands:"
        echo "  setup    - Initial setup (creates .env, directories)"
        echo "  build    - Build Docker images"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - View logs (add service name for specific logs)"
        echo "  status   - Show service status"
        echo "  pull     - Pull latest images"
        echo "  help     - Show this help message"
        ;;
esac
