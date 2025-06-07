# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Run the application:**
```bash
uv run bracketeer/__main__.py
```

**Install dependencies (development):**
```bash
uv sync --group dev
uv pip install -e .
```

**Code formatting and linting:**
```bash
ruff check
ruff format
black .
isort .
```

**Jupyter notebooks (for additional tools in _notebooks/):**
```bash
jupyter notebook
```

## Architecture Overview

Bracketeer is a Flask-based web application for combat robotics tournament management and match timing. The application serves multiple audiences: judges/organizers via web interface, and spectators via stream overlays.

**Core Components:**
- **Flask app** (`bracketeer/__main__.py`) - Main web server with SocketIO for real-time communication
- **API integrations** - TrueFinals and Challonge tournament bracket APIs with caching layer
- **Match management** - Timer control, match results, and competitor tracking
- **Screen system** - Stream overlay templates for match timers and competitor displays
- **Configuration system** - Dynaconf-based config using `event.json` and `.secrets.json`

**Key Blueprints:**
- `/screens/*` - Timer displays and stream overlays
- `/matches/*` - Match results and bracket management  
- `/debug/*` - Development and debugging tools
- `/control/<cageID>` - Judge timer control interface

**Data Flow:**
1. Tournament data pulled from TrueFinals/Challonge APIs and cached
2. Match timers controlled via SocketIO for real-time updates
3. Stream overlays consume timer state for broadcast graphics
4. Multiple arena/cage support for concurrent matches

**Configuration:**
- `event.json` - Tournament settings, cage definitions, API tournament keys
- `.secrets.json` - API credentials for TrueFinals, RCE, OBS websocket
- Config validation occurs at startup via `mandateConfig()`

**Network Requirements:**
- Host computer must use static IP (default: 192.168.8.250)
- Clients connect to timer displays over local network
- Application serves on port 80 by default