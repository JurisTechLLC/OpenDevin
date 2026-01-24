#!/bin/bash
# JurisTech OpenHands Launcher
# Double-click this file to start OpenHands with the JurisTech extension

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENHANDS_DIR="$(dirname "$SCRIPT_DIR")"
OPENHANDS_ROOT="$(dirname "$OPENHANDS_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  JurisTech OpenHands Launcher${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "$OPENHANDS_ROOT/Makefile" ]; then
    echo -e "${RED}Error: OpenHands not found at $OPENHANDS_ROOT${NC}"
    echo "Please ensure this script is in the juristech-ext/scripts directory"
    read -p "Press Enter to exit..."
    exit 1
fi

cd "$OPENHANDS_ROOT"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed or not in PATH${NC}"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${YELLOW}Docker is not running. Attempting to start...${NC}"
    sudo systemctl start docker 2>/dev/null || true
    sleep 3
    if ! docker info &> /dev/null; then
        echo -e "${RED}Error: Could not start Docker${NC}"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

echo -e "${GREEN}Docker is running${NC}"

# Load environment variables if .env exists
if [ -f "$OPENHANDS_ROOT/.env" ]; then
    echo "Loading environment from .env file..."
    export $(grep -v '^#' "$OPENHANDS_ROOT/.env" | xargs)
fi

# Check for required environment variables
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}Warning: No API keys found in environment${NC}"
    echo "You may need to configure API keys in the OpenHands settings"
fi

# Start OpenHands
echo ""
echo -e "${GREEN}Starting OpenHands...${NC}"
echo "This may take a moment on first run while containers are pulled."
echo ""

# Use make run if available, otherwise use docker-compose
if [ -f "$OPENHANDS_ROOT/Makefile" ]; then
    make run &
else
    docker-compose up -d
fi

# Wait for the server to start
echo "Waiting for server to start..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://127.0.0.1:3001 > /dev/null 2>&1; then
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}Server may still be starting. Opening browser anyway...${NC}"
fi

# Open the browser
echo -e "${GREEN}Opening browser...${NC}"
if command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:3001" &
elif command -v gnome-open &> /dev/null; then
    gnome-open "http://127.0.0.1:3001" &
elif command -v open &> /dev/null; then
    open "http://127.0.0.1:3001" &
else
    echo "Please open http://127.0.0.1:3001 in your browser"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  OpenHands is running!${NC}"
echo -e "${GREEN}  Access at: http://127.0.0.1:3001${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Keep the terminal open and show logs
wait
