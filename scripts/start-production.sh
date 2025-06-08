#!/bin/bash
#
# Production startup script for Bracketeer using Gunicorn with proper process management.
#
# This script starts Bracketeer in production mode with Gunicorn for better 
# process management, logging, and graceful shutdown capabilities.
#

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/bracketeer.pid"
LOG_DIR="$PROJECT_DIR/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set environment variables
export BRACKETEER_ENV=production
export PYTHONPATH="${PYTHONPATH}:${PROJECT_DIR}"

echo -e "${GREEN}🤖 Starting Bracketeer Production Server${NC}"
echo "=================================================="

# Change to project directory
cd "$PROJECT_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${RED}❌ Bracketeer is already running (PID: $(cat "$PID_FILE"))${NC}"
        echo "   Use './scripts/stop-production.sh' to stop it first"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Removing stale PID file${NC}"
        rm -f "$PID_FILE"
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Install/update dependencies
echo -e "${YELLOW}📦 Installing production dependencies...${NC}"
uv sync

# Validate configuration
echo -e "${YELLOW}⚙️  Validating configuration...${NC}"
if ! uv run python -c "from bracketeer.config import mandateConfig; mandateConfig()" 2>/dev/null; then
    echo -e "${RED}❌ Configuration validation failed${NC}"
    echo "   Run setup wizard: uv run python -m bracketeer.setup_wizard"
    exit 1
fi

# Check if port 80 is available
if ! uv run python -c "
import socket
try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 80))
except OSError:
    exit(1)
" 2>/dev/null; then
    echo -e "${RED}❌ Port 80 is not available${NC}"
    echo "   Either another service is using port 80, or you need sudo privileges"
    echo "   Try: sudo ./scripts/start-production.sh"
    exit 1
fi

# Start Gunicorn with proper configuration
echo -e "${GREEN}🚀 Starting Bracketeer with Gunicorn...${NC}"
echo "   Host: 0.0.0.0:80"
echo "   PID file: $PID_FILE"
echo "   Logs: $LOG_DIR/"
echo ""

# Start server in background
uv run gunicorn \
    --config gunicorn.conf.py \
    --daemon \
    --bind 0.0.0.0:80 \
    --pid "$PID_FILE" \
    wsgi:application

# Wait a moment for startup
sleep 2

# Check if it started successfully
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    PID=$(cat "$PID_FILE")
    echo -e "${GREEN}✅ Bracketeer started successfully!${NC}"
    echo "   PID: $PID"
    echo "   Server: http://$(hostname):80"
    echo "   Access logs: $LOG_DIR/access.log"
    echo "   Error logs: $LOG_DIR/error.log"
    echo ""
    echo "To stop the server: ./scripts/stop-production.sh"
    echo "To check status: ./scripts/status-production.sh"
else
    echo -e "${RED}❌ Failed to start Bracketeer${NC}"
    echo "   Check logs: $LOG_DIR/error.log"
    exit 1
fi