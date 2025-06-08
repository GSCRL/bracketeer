#!/bin/bash
#
# Production restart script for Bracketeer.
#
# This script safely restarts the Bracketeer production server by stopping
# the current instance and starting a new one.
#

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔄 Restarting Bracketeer Production Server${NC}"
echo "=============================================="

# Stop the server if running
echo "Step 1: Stopping current server..."
"$SCRIPT_DIR/stop-production.sh"

echo ""
echo "Step 2: Starting server..."

# Start the server
"$SCRIPT_DIR/start-production.sh"

echo ""
echo -e "${GREEN}✅ Restart complete!${NC}"
echo ""
echo "Check status: ./scripts/status-production.sh"