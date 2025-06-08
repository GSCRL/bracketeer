#!/bin/bash
#
# Production logs viewer script for Bracketeer.
#
# This script provides easy access to view production logs.
#

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Change to project directory
cd "$PROJECT_DIR"

# Function to show usage
show_usage() {
    echo -e "${BLUE}📄 Bracketeer Production Logs Viewer${NC}"
    echo "======================================"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  error, e     - View error log (default)"
    echo "  access, a    - View access log"
    echo "  app          - View application log"
    echo "  all          - View all logs"
    echo "  tail, t      - Tail error log (follow)"
    echo "  tail-all     - Tail all logs"
    echo "  clear        - Clear all log files"
    echo ""
    echo "Examples:"
    echo "  $0           - View recent error log entries"
    echo "  $0 tail      - Follow error log in real-time"
    echo "  $0 access    - View access log"
    echo "  $0 clear     - Clear all logs (requires confirmation)"
}

# Function to view log file
view_log() {
    local logfile="$1"
    local name="$2"
    
    if [ ! -f "$logfile" ]; then
        echo -e "${YELLOW}⚠️  $name log not found: $logfile${NC}"
        return
    fi
    
    local lines=$(wc -l < "$logfile" 2>/dev/null || echo "0")
    echo -e "${CYAN}=== $name Log (${lines} lines) ===${NC}"
    echo -e "${CYAN}File: $logfile${NC}"
    echo ""
    
    # Show last 50 lines by default
    tail -50 "$logfile"
    echo ""
}

# Function to tail log file
tail_log() {
    local logfile="$1"
    local name="$2"
    
    if [ ! -f "$logfile" ]; then
        echo -e "${YELLOW}⚠️  $name log not found: $logfile${NC}"
        return
    fi
    
    echo -e "${CYAN}Following $name log (Ctrl+C to stop)...${NC}"
    echo -e "${CYAN}File: $logfile${NC}"
    echo ""
    tail -f "$logfile"
}

# Function to clear logs
clear_logs() {
    echo -e "${YELLOW}⚠️  This will clear all production log files!${NC}"
    echo "Log files to be cleared:"
    [ -f "$LOG_DIR/error.log" ] && echo "  - $LOG_DIR/error.log"
    [ -f "$LOG_DIR/access.log" ] && echo "  - $LOG_DIR/access.log"
    [ -f "$LOG_DIR/bracketeer.log" ] && echo "  - $LOG_DIR/bracketeer.log"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        [ -f "$LOG_DIR/error.log" ] && > "$LOG_DIR/error.log" && echo "Cleared error.log"
        [ -f "$LOG_DIR/access.log" ] && > "$LOG_DIR/access.log" && echo "Cleared access.log"
        [ -f "$LOG_DIR/bracketeer.log" ] && > "$LOG_DIR/bracketeer.log" && echo "Cleared bracketeer.log"
        echo -e "${GREEN}✅ Logs cleared${NC}"
    else
        echo "Cancelled"
    fi
}

# Main script logic
case "${1:-error}" in
    "error"|"e")
        view_log "$LOG_DIR/error.log" "Error"
        ;;
    "access"|"a")
        view_log "$LOG_DIR/access.log" "Access"
        ;;
    "app")
        view_log "$LOG_DIR/bracketeer.log" "Application"
        ;;
    "all")
        view_log "$LOG_DIR/error.log" "Error"
        view_log "$LOG_DIR/access.log" "Access"
        view_log "$LOG_DIR/bracketeer.log" "Application"
        ;;
    "tail"|"t")
        tail_log "$LOG_DIR/error.log" "Error"
        ;;
    "tail-all")
        echo -e "${CYAN}Following all logs (Ctrl+C to stop)...${NC}"
        echo ""
        if command -v multitail >/dev/null 2>&1; then
            multitail "$LOG_DIR/error.log" "$LOG_DIR/access.log" "$LOG_DIR/bracketeer.log"
        else
            echo "Note: Install 'multitail' for better multi-log viewing"
            tail -f "$LOG_DIR/error.log" "$LOG_DIR/access.log" "$LOG_DIR/bracketeer.log" 2>/dev/null
        fi
        ;;
    "clear")
        clear_logs
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        echo "Unknown option: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac