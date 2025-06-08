#!/bin/bash
#
# Production stop script for Bracketeer.
#
# This script gracefully stops the Bracketeer production server with proper
# signal handling and cleanup.
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
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping Bracketeer Production Server${NC}"
echo "==============================================="

# Change to project directory
cd "$PROJECT_DIR"

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠️  No PID file found ($PID_FILE)${NC}"
    echo "   Server may not be running or was started manually"
    
    # Try to find process by name
    PIDS=$(pgrep -f "gunicorn.*wsgi:application" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}   Found Gunicorn processes: $PIDS${NC}"
        echo "   Attempting to stop them..."
        for pid in $PIDS; do
            if kill -0 "$pid" 2>/dev/null; then
                echo "   Stopping process $pid..."
                kill -TERM "$pid"
            fi
        done
        sleep 2
        # Force kill if still running
        for pid in $PIDS; do
            if kill -0 "$pid" 2>/dev/null; then
                echo "   Force killing process $pid..."
                kill -KILL "$pid"
            fi
        done
        echo -e "${GREEN}✅ Stopped Gunicorn processes${NC}"
    else
        echo -e "${GREEN}✅ No Bracketeer processes found${NC}"
    fi
    exit 0
fi

# Read PID from file
PID=$(cat "$PID_FILE")
echo "Found PID: $PID"

# Check if process is actually running
if ! kill -0 "$PID" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Process $PID is not running${NC}"
    echo "   Removing stale PID file"
    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
fi

# Graceful shutdown with SIGTERM
echo -e "${YELLOW}📤 Sending SIGTERM to process $PID...${NC}"
kill -TERM "$PID"

# Wait for graceful shutdown (up to 30 seconds)
echo "   Waiting for graceful shutdown..."
TIMEOUT=30
COUNTER=0
while kill -0 "$PID" 2>/dev/null && [ $COUNTER -lt $TIMEOUT ]; do
    sleep 1
    COUNTER=$((COUNTER + 1))
    if [ $((COUNTER % 5)) -eq 0 ]; then
        echo "   Still waiting... (${COUNTER}s/${TIMEOUT}s)"
    fi
done

# Check if process stopped
if kill -0 "$PID" 2>/dev/null; then
    echo -e "${RED}⚠️  Process did not stop gracefully, force killing...${NC}"
    kill -KILL "$PID"
    sleep 1
    
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${RED}❌ Failed to stop process $PID${NC}"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Process force killed${NC}"
    fi
else
    echo -e "${GREEN}✅ Process stopped gracefully${NC}"
fi

# Clean up PID file
if [ -f "$PID_FILE" ]; then
    rm -f "$PID_FILE"
    echo "   Removed PID file"
fi

# Show final status
echo ""
echo -e "${GREEN}✅ Bracketeer production server stopped successfully${NC}"
echo "   Logs preserved in: $LOG_DIR/"
echo ""
echo "To restart: ./scripts/start-production.sh"
echo "To check logs: tail -f $LOG_DIR/error.log"