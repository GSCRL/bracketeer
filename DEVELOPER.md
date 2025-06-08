# DEVELOPER.md

This document contains technical insights and lessons learned during development of Bracketeer's TrueFinals API integration.

## TrueFinals API Architecture & Lessons Learned

### API Endpoint Structure

**Core Endpoints Used:**
- `GET /v1/user/tournaments` - Returns tournaments owned/created by authenticated user
- `GET /v1/tournaments/{tournamentID}/games` - Returns match/game data for a tournament  
- `GET /v1/tournaments/{tournamentID}/players` - Returns player roster for a tournament
- `GET /v1/tournaments/{tournamentID}/details` - Lightweight tournament metadata
- `GET /v1/tournaments/{tournamentID}/locations` - Arena/venue information

### Key API Patterns Discovered

#### 1. Tournament Ownership vs Participation
**Critical Discovery**: `/v1/user/tournaments` only returns tournaments you **own/created**, not tournaments where you're a participant or have admin access.

**Implication**: For event organizers managing their own tournaments, this is perfect. For participants or admins of others' tournaments, manual tournament ID entry is required.

#### 2. Games Data Structure
```json
{
  "id": "string",
  "name": "string", 
  "bracketID": "W",
  "round": 0,
  "scoreToWin": 0,
  "slots": [
    {
      "gameID": "string",
      "slotIdx": 0,
      "playerID": "string or null",
      "checkInTime": "integer or null",
      "waitingTime": "integer or null", 
      "prevGameID": "string or null",
      "score": "integer or number",
      "slotState": "pending|winner|loser|winner_by_default|loser_by_default|tie"
    }
  ],
  "state": "unavailable|available|called|active|hold|done",
  "activeSince": 0,
  "availableSince": 0,
  "calledSince": 0,
  "heldSince": 0,
  "endTime": 0,
  "scheduledTime": 0,
  "nextGameSlotIDs": [],
  "locationID": "string",
  "resultAnnotation": "KO", 
  "winnerPlacement": 0,
  "loserPlacement": 0
}
```

**Key Insights:**
- **Player Names Not Included**: Games contain `playerID` in slots but no player names
- **Enrichment Required**: Must fetch player data separately and cross-reference by ID
- **Bye Handling**: Bye slots have `playerID` starting with `bye-` (e.g., `bye-9258165ed10f46ca`)

#### 3. Players Data Structure  
```json
{
  "id": "string",
  "name": "string",
  "photoUrl": "string", 
  "seed": 0,
  "wins": 0,
  "losses": 0,
  "ties": 0,
  "isBye": true,
  "isDisqualified": true,
  "lastPlayTime": 0,
  "lastBracketGameID": "string",
  "placement": 0,
  "profileInfo": {}
}
```

### Rate Limiting & Caching Strategy

**Rate Limits**: 10 requests per 10 seconds (shared with web interface usage)

**Optimal Caching Strategy Developed:**
```
- User tournaments: 10 minutes (ownership rarely changes)
- Tournament details: 2 minutes (metadata changes infrequently)  
- Games data: 15 seconds (matches change frequently during events)
- Players data: 5 minutes (roster changes infrequently)
- Locations: 10 minutes (venue data rarely changes)
```

**Cache Invalidation**: Implemented SQLite-based caching with automatic expiry and manual purge capabilities.

### Data Enrichment Pattern

**Problem**: Games contain `playerID` references but no player names for display.

**Solution**: Developed two-stage enrichment process:

1. **Bulk Player Cache**: Fetch all players for tournament and cache in database
2. **Match Enrichment**: For each game slot, lookup player by ID and attach as `bracketeer_player_data`

```python
# Core enrichment pattern
for match in matches:
    for slot in match["slots"]:
        player_id = slot.get("playerID") 
        if player_id and not player_id.startswith("bye-"):
            player_data = getPlayerByIds(tournamentID, player_id)
            slot["bracketeer_player_data"] = player_data
        elif player_id and player_id.startswith("bye-"):
            slot["bracketeer_player_data"] = {"name": "BYE", "isBye": True}
```

### Tournament Status Derivation

**Discovery**: TrueFinals doesn't always provide explicit tournament status.

**Solution**: Derive status from timestamps and game states:
```python
def derive_tournament_status(tournament_data):
    # Priority order:
    # 1. Explicit status if provided
    # 2. End time indicates completion
    # 3. Start time indicates active
    # 4. Scheduled start time indicates scheduled
    # 5. Create time indicates created
    # 6. Default to unknown
```

### Bye Slot Handling

**Critical Bug Discovered**: Bye slots were showing as "Unknown" players.

**Root Cause**: Bye slots have `playerID` like `bye-{uuid}` which don't exist in players roster.

**Solution**: 
- Detect bye slots by `playerID.startswith("bye-")`
- Set appropriate display name as "BYE"
- Mark as `isBye: true` for template logic

### API Optimization Insights

#### Efficient Tournament Archive Pattern
**Before**: Loading all tournament data upfront (slow, high API usage)
**After**: Two-stage loading:
1. Load tournament list with basic metadata
2. Load match data on-demand when user drills down

#### Player Data Caching
**Pattern**: Build tournament-scoped player dictionary for fast lookups
```python
player_cache = {
    "tournament_id": {
        "player_id": player_data
    }
}
```

### Error Handling Patterns

**404 Tournament Not Found**: Tournament IDs from old data may no longer exist
**Rate Limiting**: Implement exponential backoff and cache-first strategies  
**Stale Data**: Graceful fallback to cached data when fresh requests fail
**Missing Players**: Handle cases where player lookup fails with sensible defaults

### Performance Characteristics

**Typical Memory Usage**: 50-100MB per tournament
**API Call Efficiency**: 
- Tournament list: 1 call per 10 minutes
- Match data: 1 call per tournament per 15 seconds during active events
- Player data: 1 call per tournament per 5 minutes

**Network Requirements**: Designed for local network deployment at tournament venues

### Template Integration Lessons

**Data Transformation Required**: TrueFinals API structure differs from template expectations:
- Templates expect `players` array, API provides `slots` with `playerID` references
- Transformation layer needed to convert API format to template-friendly format

**Winner Detection**: Use `slotState: "winner"` rather than score comparison

### Security & Deployment Notes

**API Credentials**: Store in `.secrets.json` with proper file permissions (600)
**Tournament Access**: Only tournaments owned by authenticated user are accessible
**Local Network**: Default deployment assumes tournament venue local network

## Development Workflow

### Testing with Real Data
1. Configure valid TrueFinals credentials in `.secrets.json`
2. Use setup wizard to select active tournaments
3. Test with real tournament IDs from owned tournaments
4. Verify both completed matches (with byes) and upcoming matches (player vs player)

### Debugging Player Enrichment
```python
# Check tournament access
tournaments = getUserTournaments()

# Verify match data structure  
matches = getTournamentMatchesWithPlayers(tournament_id)

# Inspect player data
for match in matches:
    for slot in match['slots']:
        player_data = slot.get('bracketeer_player_data', {})
        print(f"Player: {player_data.get('name', 'NO_NAME')}")
```

### Cache Management
```python
# Clear cache for fresh data
from bracketeer.api_truefinals.cached_api import purge_API_Cache
purge_API_Cache(timer_passed=0)  # Purge all
```

## Future Considerations

**API Evolution**: TrueFinals API may add new fields or change structure
**Scale Limits**: Current design optimized for single-event usage  
**Real-time Updates**: Consider WebSocket integration for live match updates
**Tournament Discovery**: May need manual tournament entry for non-owned tournaments

## Documentation References

- TrueFinals API Docs: https://truefinals.com/docs.html
- Rate limiting headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Tournament URL pattern: `https://truefinals.com/tournament/{tournamentID}`