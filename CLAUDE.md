# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Run the application:**
```bash
# Default mode (port 80, fails if port in use)
uv run bracketeer/__main__.py

# Development mode (auto-find available port)
uv run bracketeer/__main__.py --dev

# Specify custom port
uv run bracketeer/__main__.py --port 8080

# Custom host and port
uv run bracketeer/__main__.py --host 127.0.0.1 --port 5000

# Disable debug mode
uv run bracketeer/__main__.py --no-debug
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

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.