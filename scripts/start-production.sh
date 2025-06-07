#!/bin/bash
"""
Production startup script for Bracketeer using Gunicorn.

This script starts Bracketeer in production mode with proper logging
and process management.
"""

# Set environment variables
export BRACKETEER_ENV=production
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Create logs directory if it doesn't exist
mkdir -p logs

# Install/update dependencies
echo "Installing production dependencies..."
uv sync

# Start with Gunicorn
echo "Starting Bracketeer in production mode..."
echo "Server will be available at http://0.0.0.0:80"
echo "Logs will be written to logs/access.log and logs/error.log"
echo "To stop the server, use: kill \$(cat bracketeer.pid)"

uv run gunicorn --config gunicorn.conf.py wsgi:application