#!/bin/bash
# JurisTech OpenHands UI Wrapper Launcher
# This script starts OpenHands in the background and launches the JurisTech custom UI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENHANDS_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
WRAPPER_DIR="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# PID files for cleanup
OPENHANDS_PID_FILE="/tmp/openhands.pid"
WRAPPER_PID_FILE="/tmp/juristech-wrapper.pid"

cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    
    # Kill wrapper backend
    if [ -f "$WRAPPER_PID_FILE" ]; then
        kill $(cat "$WRAPPER_PID_FILE") 2>/dev/null
        rm -f "$WRAPPER_PID_FILE"
        echo -e "${GREEN}Wrapper backend stopped${NC}"
    fi
    
    # Kill OpenHands
    if [ -f "$OPENHANDS_PID_FILE" ]; then
        kill $(cat "$OPENHANDS_PID_FILE") 2>/dev/null
        rm -f "$OPENHANDS_PID_FILE"
        echo -e "${GREEN}OpenHands stopped${NC}"
    fi
    
    # Also try to stop any make run processes
    pkill -f "make run" 2>/dev/null
    
    echo -e "${GREEN}Cleanup complete${NC}"
    exit 0
}

# Set up trap for cleanup on exit
trap cleanup SIGINT SIGTERM EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  JurisTech OpenHands UI Wrapper${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if OpenHands directory exists
if [ ! -d "$OPENHANDS_ROOT" ] || [ ! -f "$OPENHANDS_ROOT/Makefile" ]; then
    echo -e "${RED}Error: OpenHands not found at $OPENHANDS_ROOT${NC}"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null 2>&1; then
    echo -e "${YELLOW}Starting Docker...${NC}"
    sudo systemctl start docker 2>/dev/null || true
    sleep 3
fi

# Install wrapper backend dependencies if needed
echo -e "${GREEN}Checking wrapper dependencies...${NC}"
cd "$WRAPPER_DIR/backend"
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

# Start OpenHands in background (headless)
echo -e "${GREEN}Starting OpenHands in background...${NC}"
cd "$OPENHANDS_ROOT"
make run > /tmp/openhands.log 2>&1 &
echo $! > "$OPENHANDS_PID_FILE"

# Wait for OpenHands to start
echo -e "${YELLOW}Waiting for OpenHands to start...${NC}"
for i in {1..60}; do
    if curl -s http://127.0.0.1:3001 > /dev/null 2>&1; then
        echo -e "${GREEN}OpenHands is ready!${NC}"
        break
    fi
    sleep 2
    echo -n "."
done
echo ""

# Check if OpenHands started successfully
if ! curl -s http://127.0.0.1:3001 > /dev/null 2>&1; then
    echo -e "${RED}Error: OpenHands failed to start${NC}"
    echo "Check /tmp/openhands.log for details"
    exit 1
fi

# Start wrapper backend
echo -e "${GREEN}Starting JurisTech wrapper backend...${NC}"
cd "$WRAPPER_DIR/backend"
source venv/bin/activate
python main.py > /tmp/juristech-wrapper.log 2>&1 &
echo $! > "$WRAPPER_PID_FILE"

# Wait for wrapper to start
sleep 3

# Check if wrapper started successfully
if ! curl -s http://127.0.0.1:3002/extension/health > /dev/null 2>&1; then
    echo -e "${RED}Error: Wrapper backend failed to start${NC}"
    echo "Check /tmp/juristech-wrapper.log for details"
    exit 1
fi

# Open browser to OpenHands UI directly (wrapper handles extension API only)
echo -e "${GREEN}Opening browser...${NC}"
xdg-open "http://127.0.0.1:3001" 2>/dev/null &

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  JurisTech OpenHands is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${BLUE}OpenHands UI:${NC}  http://127.0.0.1:3001"
echo -e "  ${BLUE}Extension API:${NC} http://127.0.0.1:3002/extension/"
echo ""
echo -e "  ${YELLOW}Note: Extension features (Supervisor AI, RAG, Vision)${NC}"
echo -e "  ${YELLOW}are available via the Extension API on port 3002${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Keep script running and show logs
tail -f /tmp/juristech-wrapper.log /tmp/openhands.log 2>/dev/null &
wait
