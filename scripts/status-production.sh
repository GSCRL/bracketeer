#!/bin/bash
#
# Production status script for Bracketeer.
#
# This script checks the status of the Bracketeer production server and 
# provides useful information about the running process.
#

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
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 Bracketeer Production Server Status${NC}"
echo "=========================================="

# Change to project directory
cd "$PROJECT_DIR"

# Function to format uptime
format_uptime() {
    local seconds=$1
    local days=$((seconds / 86400))
    local hours=$(((seconds % 86400) / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    
    if [ $days -gt 0 ]; then
        echo "${days}d ${hours}h ${minutes}m"
    elif [ $hours -gt 0 ]; then
        echo "${hours}h ${minutes}m"
    elif [ $minutes -gt 0 ]; then
        echo "${minutes}m ${secs}s"
    else
        echo "${secs}s"
    fi
}

# Function to format memory
format_memory() {
    local kb=$1
    if [ $kb -gt 1048576 ]; then
        echo "$((kb / 1024 / 1024))GB"
    elif [ $kb -gt 1024 ]; then
        echo "$((kb / 1024))MB"
    else
        echo "${kb}KB"
    fi
}

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${RED}❌ Server Status: NOT RUNNING${NC}"
    echo "   No PID file found: $PID_FILE"
    
    # Check for orphaned processes
    PIDS=$(pgrep -f "gunicorn.*wsgi:application" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}⚠️  Found orphaned Gunicorn processes:${NC}"
        for pid in $PIDS; do
            echo "   PID: $pid"
        done
        echo "   Run './scripts/stop-production.sh' to clean up"
    fi
    echo ""
    echo "To start: ./scripts/start-production.sh"
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! kill -0 "$PID" 2>/dev/null; then
    echo -e "${RED}❌ Server Status: NOT RUNNING${NC}"
    echo "   PID file exists but process $PID is not running"
    echo "   Run './scripts/stop-production.sh' to clean up"
    exit 1
fi

# Get process information
if command -v ps >/dev/null 2>&1; then
    # Get detailed process info
    PS_OUTPUT=$(ps -p "$PID" -o pid,ppid,user,%cpu,%mem,vsz,rss,tty,stat,start,time,cmd --no-headers 2>/dev/null || true)
    
    if [ -n "$PS_OUTPUT" ]; then
        echo -e "${GREEN}✅ Server Status: RUNNING${NC}"
        echo ""
        
        # Parse ps output
        read -r pid ppid user cpu mem vsz rss tty stat start time cmd <<< "$PS_OUTPUT"
        
        echo -e "${CYAN}Process Information:${NC}"
        echo "   PID: $pid"
        echo "   Parent PID: $ppid"
        echo "   User: $user"
        echo "   Status: $stat"
        echo "   Started: $start"
        echo "   CPU Time: $time"
        echo ""
        
        echo -e "${CYAN}Resource Usage:${NC}"
        echo "   CPU: ${cpu}%"
        echo "   Memory: ${mem}% ($(format_memory $rss))"
        echo "   Virtual Memory: $(format_memory $vsz)"
        echo ""
        
        # Calculate uptime
        if command -v stat >/dev/null 2>&1; then
            if [ -f "/proc/$pid" ]; then
                # Linux
                START_TIME=$(stat -c %Y "/proc/$pid" 2>/dev/null || echo "")
            else
                # macOS - try alternative method
                START_TIME=$(ps -p "$PID" -o lstart= 2>/dev/null | xargs -I {} date -j -f "%a %b %d %H:%M:%S %Y" "{}" "+%s" 2>/dev/null || echo "")
            fi
            
            if [ -n "$START_TIME" ]; then
                CURRENT_TIME=$(date +%s)
                UPTIME=$((CURRENT_TIME - START_TIME))
                echo -e "${CYAN}Uptime:${NC} $(format_uptime $UPTIME)"
                echo ""
            fi
        fi
    fi
else
    echo -e "${GREEN}✅ Server Status: RUNNING${NC}"
    echo "   PID: $PID"
    echo ""
fi

# Check port 80
echo -e "${CYAN}Network Status:${NC}"
if command -v netstat >/dev/null 2>&1; then
    LISTENING=$(netstat -an | grep ":80 " | grep LISTEN || true)
    if [ -n "$LISTENING" ]; then
        echo "   ✅ Port 80: Listening"
    else
        echo "   ❌ Port 80: Not listening"
    fi
elif command -v lsof >/dev/null 2>&1; then
    LISTENING=$(lsof -i :80 | grep LISTEN || true)
    if [ -n "$LISTENING" ]; then
        echo "   ✅ Port 80: Listening"
    else
        echo "   ❌ Port 80: Not listening"
    fi
else
    echo "   ? Port 80: Cannot check (netstat/lsof not available)"
fi

# Check if server responds
echo -n "   HTTP Response: "
if command -v curl >/dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:80/" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ OK (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "${RED}❌ Failed (HTTP $HTTP_CODE)${NC}"
    fi
else
    echo "? Cannot check (curl not available)"
fi

echo ""

# Log file information
echo -e "${CYAN}Log Files:${NC}"
if [ -f "$LOG_DIR/access.log" ]; then
    ACCESS_SIZE=$(wc -l < "$LOG_DIR/access.log" 2>/dev/null || echo "?")
    echo "   Access log: $ACCESS_SIZE lines ($LOG_DIR/access.log)"
else
    echo "   Access log: Not found"
fi

if [ -f "$LOG_DIR/error.log" ]; then
    ERROR_SIZE=$(wc -l < "$LOG_DIR/error.log" 2>/dev/null || echo "?")
    echo "   Error log: $ERROR_SIZE lines ($LOG_DIR/error.log)"
    
    # Check for recent errors
    if command -v tail >/dev/null 2>&1; then
        RECENT_ERRORS=$(tail -20 "$LOG_DIR/error.log" 2>/dev/null | grep -i error | wc -l || echo "0")
        if [ "$RECENT_ERRORS" -gt 0 ]; then
            echo -e "   ${YELLOW}⚠️  Recent errors: $RECENT_ERRORS (last 20 lines)${NC}"
        fi
    fi
else
    echo "   Error log: Not found"
fi

echo ""
echo -e "${CYAN}Management Commands:${NC}"
echo "   Stop server: ./scripts/stop-production.sh"
echo "   Restart: ./scripts/stop-production.sh && ./scripts/start-production.sh"
echo "   View logs: tail -f $LOG_DIR/error.log"
echo "   Web interface: http://$(hostname):80"