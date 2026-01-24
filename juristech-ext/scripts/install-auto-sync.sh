#!/bin/bash
# JurisTech GitHub Auto-Sync Service Installer
# Installs and enables the auto-sync service for automatic repository updates

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  JurisTech GitHub Auto-Sync Installer${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/github-auto-sync.service"
SYNC_SCRIPT="$SCRIPT_DIR/github-auto-sync.py"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run this script as root${NC}"
    echo "Run as your normal user - the script will use sudo when needed"
    exit 1
fi

# Check if the sync script exists
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo -e "${RED}Error: github-auto-sync.py not found at $SYNC_SCRIPT${NC}"
    exit 1
fi

# Make the sync script executable
chmod +x "$SYNC_SCRIPT"
echo -e "${GREEN}Made sync script executable${NC}"

# Create the log directory
LOG_DIR="$HOME/.juristech-openhands"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}Created log directory: $LOG_DIR${NC}"

# Create systemd user directory if it doesn't exist
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

# Create the service file with correct paths
SERVICE_DEST="$SYSTEMD_USER_DIR/github-auto-sync.service"
cat > "$SERVICE_DEST" << EOF
[Unit]
Description=JurisTech GitHub Auto-Sync Service
Documentation=https://github.com/JurisTechLLC/OpenDevin
After=network.target

[Service]
Type=simple
WorkingDirectory=$HOME
ExecStart=/usr/bin/python3 $SYNC_SCRIPT --interval 300
Restart=always
RestartSec=30
StandardOutput=append:$LOG_DIR/auto-sync.log
StandardError=append:$LOG_DIR/auto-sync-error.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

echo -e "${GREEN}Created service file: $SERVICE_DEST${NC}"

# Reload systemd user daemon
systemctl --user daemon-reload
echo -e "${GREEN}Reloaded systemd user daemon${NC}"

# Enable and start the service
systemctl --user enable github-auto-sync.service
echo -e "${GREEN}Enabled github-auto-sync service${NC}"

systemctl --user start github-auto-sync.service
echo -e "${GREEN}Started github-auto-sync service${NC}"

# Enable lingering so the service runs even when not logged in
loginctl enable-linger "$USER" 2>/dev/null || true
echo -e "${GREEN}Enabled user lingering for background service${NC}"

# Show status
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "The auto-sync service is now running and will:"
echo "  - Check for repository updates every 5 minutes"
echo "  - Automatically pull changes when detected"
echo "  - Re-index the RAG database after updates"
echo ""
echo "Useful commands:"
echo "  Check status:    systemctl --user status github-auto-sync"
echo "  View logs:       journalctl --user -u github-auto-sync -f"
echo "  Stop service:    systemctl --user stop github-auto-sync"
echo "  Start service:   systemctl --user start github-auto-sync"
echo "  Disable service: systemctl --user disable github-auto-sync"
echo ""
echo "Log files:"
echo "  $LOG_DIR/auto-sync.log"
echo "  $LOG_DIR/auto-sync-error.log"
echo ""

# Run once to show initial status
echo "Running initial sync..."
python3 "$SYNC_SCRIPT" --once
