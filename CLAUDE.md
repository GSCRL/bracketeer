# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Run the application:**

*Development Mode (recommended for development/testing):*
```bash
# Quick start - development server with auto port detection
./scripts/start-development.sh

# Manual development server (using uv)
uv run bracketeer --dev

# Custom development configuration
uv run bracketeer --port 8080 --dev --debug

# Direct Python execution (requires manual dependency management)
python -m bracketeer --dev
```

*Production Mode (recommended for tournaments/events):*
```bash
# Quick start - production server with Gunicorn
./scripts/start-production.sh

# Stop production server
./scripts/stop-production.sh

# Restart production server
./scripts/restart-production.sh

# Check server status
./scripts/status-production.sh

# View logs
./scripts/logs-production.sh          # View error log
./scripts/logs-production.sh access   # View access log
./scripts/logs-production.sh tail     # Follow error log

# Manual production server (using uv - not recommended)
export BRACKETEER_ENV=production
uv run bracketeer --host 0.0.0.0 --port 80 --no-debug
```

*Development Server Options:*
```bash
# Default mode (port 80, fails if port in use)
uv run bracketeer

# Custom host and port
uv run bracketeer --host 127.0.0.1 --port 5000

# Enable debug mode explicitly
uv run bracketeer --debug
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
- `/matches/*` - Match results, bracket management, fight log, and upcoming matches
- `/debug/*` - Development and debugging tools
- `/control/<cageID>` - Judge timer control interface
- `/setup/*` - Setup wizard for initial configuration

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

## TrueFinals API Best Practices

### API Endpoints Available (Read-Only)

**Tournament Discovery:**
- `GET /v1/user/tournaments` - Returns tournaments you **own/created** (not all accessible tournaments)
- `GET /v1/tournaments/{tournamentID}` - Full tournament data by ID

**Tournament Data:**
- `GET /v1/tournaments/{tournamentID}/details` - Lightweight tournament metadata
- `GET /v1/tournaments/{tournamentID}/games` - All matches/games  
- `GET /v1/tournaments/{tournamentID}/players` - Participant list
- `GET /v1/tournaments/{tournamentID}/locations` - Arena/venue information
- `GET /v1/tournaments/{tournamentID}/format` - Bracket format details
- `GET /v1/tournaments/{tournamentID}/overlayParams` - Stream overlay data

### Game States
TrueFinals uses these official game states (use instead of custom status logic):
- `"unavailable"` - Not ready to play
- `"available"` - Ready to be called  
- `"called"` - Called to arena, waiting for players
- `"active"` - Currently being played
- `"hold"` - Temporarily paused
- `"done"` - Completed

### Rate Limiting Best Practices
- **Limit**: ~10 requests per 10 seconds (shared with web interface usage)
- **Strategy**: Use caching extensively (current SQLite implementation is good)
- **Bulk Operations**: Prefer single tournament details call over multiple individual calls
- **Polling**: Use reasonable intervals (current 15s for games, 5min for players is appropriate)

### Tournament Discovery Limitation
**Important**: `/v1/user/tournaments` only returns tournaments you **created/own**, not tournaments where you're a participant or have admin access. For tournaments where you're not the creator:
- Users must manually enter tournament IDs
- Consider adding manual tournament entry feature in setup wizard
- Tournament URLs follow pattern: `https://truefinals.com/tournament/{tournamentID}`

### Data Optimization Opportunities
1. **Use `/tournaments/{id}/details`** for lightweight metadata instead of full tournament call
2. **Implement `/tournaments/{id}/locations`** to map games to physical arenas
3. **Use official game states** instead of time-based status calculation
4. **Cache player data longer** (players change infrequently vs games)
5. **Implement overlay data** for streaming integration

### Error Handling
- Handle `429 Too Many Requests` with exponential backoff
- Graceful degradation when tournament details can't be fetched
- Validate tournament IDs before making API calls (pattern: `^[a-zA-Z0-9-_]+$`)

## Testing

### Comprehensive Test Suite

The project includes extensive testing infrastructure:

**Run all tests:**
```bash
uv run pytest
```

**Test categories:**
- **Unit Tests:** Core functionality, API integrations, match management
- **Integration Tests:** SocketIO real-time communication, multi-browser scenarios  
- **End-to-End Tests:** Full workflow testing with Playwright browser automation

**Key Test Files:**
- `tests/test_fight_log.py` - Fight log functionality and tournament filtering
- `tests/test_match_queue.py` - Match queue enhancements and upcoming matches
- `tests/test_homepage_dashboard.py` - Dashboard functionality and tournament display
- `tests/test_socketio_integration.py` - Real-time SocketIO communication testing

## Production Deployment

### Web Server Configuration

Bracketeer supports both development and production deployment modes:

**Development Server:**
- Best for: Development, testing, debugging
- Features: Auto-reload, detailed error pages, port auto-detection
- Performance: Single-threaded, includes development debugging
- Usage: `./scripts/start-development.sh` or `uv run bracketeer --dev`

**Production Server:**
- Best for: Tournaments, events, production environments  
- Features: Gunicorn WSGI server, process management, production logging, graceful shutdown
- Performance: Optimized for concurrent users and real-time WebSocket connections
- Process Management: PID file, daemon mode, signal handling
- Usage: `./scripts/start-production.sh`

**Production Management Commands:**
```bash
./scripts/start-production.sh    # Start server
./scripts/stop-production.sh     # Graceful shutdown
./scripts/restart-production.sh  # Stop and start
./scripts/status-production.sh   # Check server status
./scripts/logs-production.sh     # View logs
```

### Environment Configuration

Set `BRACKETEER_ENV` environment variable:
- `development` - Development mode with debug enabled by default
- `production` - Production mode with debug disabled, optimized logging

### Production Checklist

1. **Install Dependencies:** `uv sync` (production dependencies only)
2. **Configure Environment:** `export BRACKETEER_ENV=production`
3. **Network Configuration:** Configure firewall for port 80 (or custom port)
4. **TrueFinals API:** Configure credentials via setup wizard (`/setup`) or settings page (`/settings`)
5. **Start Server:** `./scripts/start-production.sh`
6. **Verify Operation:** Check homepage shows tournaments and match queue functions

### Performance Considerations

- **Flask-SocketIO Production Mode:** Optimized for real-time WebSocket communication
- **Memory Usage:** Typical usage ~50-100MB per tournament
- **CPU Usage:** Low during normal operation, spikes during match state changes  
- **Network:** Designed for local network deployment (tournament venue)
- **API Caching:** SQLite-based caching reduces TrueFinals API load

### Security Notes

- Default binding: `0.0.0.0:80` (all interfaces)
- For internet deployment: Use reverse proxy (nginx) with SSL termination
- API credentials stored in `.secrets.json` - ensure proper file permissions (600)
- No authentication required for local tournament network usage

### Key Features Added

- **Fight Log System:** Complete match history and robot records (`/matches/fight-log`)
- **Enhanced Match Queue:** Tournament context and "on deck" indicators (`/matches/upcoming`) 
- **Setup Wizard:** Guided initial configuration (`/setup`)
- **Production Scripts:** Automated deployment with `./scripts/start-production.sh`
- **Port Auto-Detection:** Development mode automatically finds available ports
- **Enhanced Dashboard:** Tournament overview with real tournament names from API

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.