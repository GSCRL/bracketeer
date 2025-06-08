#!/bin/bash
#
# Development startup script for Bracketeer.
#
# This script starts Bracketeer in development mode with auto-reload
# and the built-in Flask development server.
#

# Set environment variables
export BRACKETEER_ENV=development
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Install/update dependencies
echo "Installing development dependencies..."
uv sync --group dev

# Start development server
echo "Starting Bracketeer in development mode..."
echo "Server will auto-reload on code changes"
echo "Use Ctrl+C to stop the server"

uv run bracketeer --dev --debug