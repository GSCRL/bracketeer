#!/bin/bash
#
# Production startup script for Bracketeer using Gunicorn.
#
# This script starts Bracketeer in production mode with proper logging
# and process management.
#

# Set environment variables
export BRACKETEER_ENV=production
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Create logs directory if it doesn't exist
mkdir -p logs

# Install/update dependencies
echo "Installing production dependencies..."
uv sync

# Start with Flask-SocketIO in production mode
echo "Starting Bracketeer in production mode..."
echo "Server will be available at http://0.0.0.0:80"
echo "To stop the server, use Ctrl+C"

uv run bracketeer --host 0.0.0.0 --port 80 --no-debug