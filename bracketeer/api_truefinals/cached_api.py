import logging

# Text type is VarChar without limit, probably fine?
from time import time

from piccolo.columns import JSON, UUID, BigInt, Boolean, Text
from piccolo.engine.sqlite import SQLiteEngine

# ORM Test, ty Devyn.
from piccolo.table import Table

from bracketeer.api_truefinals.api import makeAPIRequest

lru_DB = SQLiteEngine(path="tf_lru.sqlite")

"""
The true ratelimit of TrueFinals is 10 requests in 10 seconds, 
unsure of interval of observation.  However, this neglects the
 reality that the web frontend ALSO counts towards this reque-
 st limit.  
 
As such, our limit is half of the rated one by default, and as 
well is accomodating of the need for some requests that may 
not be done yet, and or still result in rate-limiting.

TrueFinals also returns the rate limit information in headers like so:

X-RateLimit-Limit: Maximum number of requests allowed within a window (10s).
X-RateLimit-Remaining: How many requests the user has left within the current window.
X-RateLimit-Reset: Unix timestamp in milliseconds when the limits are reset.

They are stored below, so we should look for the last response overall to 
validate rate limiting, and remove ones past their expiry most likely, 
rather than keeping them in perpetuity.

"""


def are_rate_limited() -> bool:
    requests_thing = (
        TrueFinalsAPICache.select()
        .where((time() - 10) > TrueFinalsAPICache.last_requested)
        .run_sync()
    )
    if (
        len(requests_thing) >= 5
    ):  # half of calls can be API due to web panel causing headaches.
        return True
    return False


class TrueFinalsAPICache(Table, db=lru_DB):
    id = UUID(primary_key=True)
    response = JSON()
    last_requested = BigInt()
    api_path = Text()
    successful = Boolean()
    resp_code = BigInt()
    resp_headers = JSON()


# This is only used as a persistent cache in the same datastore to avoid headaches.
class TrueFinalsTournamentsPlayers(Table, db=lru_DB):
    pk_id = UUID(primary_key=True)
    tournament_id = Text()
    id = Text()
    last_updated = BigInt()
    player_data = JSON()


# Need to assert that the table exists first, or else it fails horridly.
TrueFinalsAPICache.create_table(if_not_exists=True).run_sync()
TrueFinalsTournamentsPlayers.create_table(if_not_exists=True).run_sync()


def _generate_cache_query(api_endpoint, expiry=60, expired_is_ok=False):
    find_response = (
        TrueFinalsAPICache.select(
            TrueFinalsAPICache.api_path,
            TrueFinalsAPICache.last_requested,
            TrueFinalsAPICache.response,
            TrueFinalsAPICache.resp_code,
        )
        .where(TrueFinalsAPICache.api_path == api_endpoint)
        .where(TrueFinalsAPICache.successful == True)
    )
    if not expired_is_ok:
        find_response = find_response.where(
            (TrueFinalsAPICache.last_requested + expiry > time()),
        )

    find_response = (
        find_response.order_by(TrueFinalsAPICache.last_requested, ascending=False)
        .limit(1)
        .output(load_json=True)
    )

    return find_response


def getAPIEndpointRespectfully(api_endpoint: str, expiry=60):
    logging.info(f"expiry is {expiry} while calling {api_endpoint}")

    find_response = _generate_cache_query(api_endpoint, expiry).run_sync()

    # Key is not present.
    if len(find_response) == 0:
        logging.info(f"No valid keys, adding new request for {api_endpoint}")
        # TODO change to enqueue system and run in distinct thread I think?
        # That or a global worker for DB operations to avoid headaches or something.

        query_remote = makeAPIRequest(api_endpoint)
        # print(query_remote.headers)
        insert_query = TrueFinalsAPICache.insert(
            TrueFinalsAPICache(
                response=query_remote.json(),
                successful=(
                    (query_remote.status_code >= 200)
                    and (query_remote.status_code < 500)
                ),
                last_requested=time(),
                api_path=api_endpoint,
                resp_code=query_remote.status_code,
                resp_headers=query_remote.headers,
            ),
        ).run_sync()

        TrueFinalsAPICache.update(force=True)
    else:
        logging.info(f"Valid keys found, not requesting {api_endpoint}.")

    find_response = _generate_cache_query(
        api_endpoint=api_endpoint,
        expiry=expiry,
    ).run_sync()

    # last ditch effort of "if we didn't get good data the last
    # invocation, we try to return known stale data we have a
    # copy of."

    if len(find_response) == 0:
        _generate_cache_query(
            api_endpoint=api_endpoint,
            expiry=expiry,
            expired_is_ok=True,
        ).run_sync()

    return find_response


# Below are the stubs we hope to use to use the above APICache antics we've made.

# They are rough analogues to the original as made in api.py, and should be used
# instead whenever possible, as the originals may be deprecate at any point.  The
# below functions are "synthetic view" functions, where it uses the most up to date
# version of any endpoint, but also tries to get the new result if it doesn't exist.
# If there's truly no version inside of it, we should probably just... block until
# we'll become unblocked I guess.

# That's a long ten seconds.


# Below functions assume you ONLY want the unexpired items.
# This would obviously present a headache for some use cases.
def getEventInformation(tournamentID: str) -> dict:
    return getAPIEndpointRespectfully(f"/v1/tournaments/{tournamentID}")


def getAllGames(tournamentID: str) -> list[dict]:
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/games",
        expiry=5,  # Reduced to 5 seconds for faster match state updates
    )


def getAllPlayersInTournament(tournamentID: str) -> list[dict]:
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/players",
        expiry=(5 * 60),
    )


def getEventLocations(tournamentID: str) -> list[dict]:
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/locations",
        expiry=(60 * 60),
    )


def getUserTournaments() -> list[dict]:
    """Get tournaments owned/created by the authenticated user (event manager view)"""
    return getAPIEndpointRespectfully(
        "/v1/user/tournaments",
        expiry=(10 * 60),  # Cache longer since owned tournaments change infrequently
    )


def getOwnedTournamentsWithDetails() -> list[dict]:
    """Get owned tournaments with lightweight details for efficient archive building"""
    import logging
    
    owned_tournaments = getUserTournaments()
    logging.info(f"getUserTournaments returned: {type(owned_tournaments)} with length {len(owned_tournaments) if owned_tournaments else 0}")
    
    if not owned_tournaments or len(owned_tournaments) == 0:
        logging.info("No owned tournaments found - returning empty list")
        return []
    
    # Extract tournament list from cache response
    tournaments_list = owned_tournaments[0].get('response', [])
    logging.info(f"Extracted tournaments_list: {type(tournaments_list)} with length {len(tournaments_list) if isinstance(tournaments_list, list) else 'not a list'}")
    
    if not isinstance(tournaments_list, list):
        logging.warning(f"tournaments_list is not a list, it's: {type(tournaments_list)}")
        return []
    
    # For each owned tournament, get lightweight details
    tournaments_with_details = []
    for i, tournament in enumerate(tournaments_list):
        tournament_id = tournament.get('id') if isinstance(tournament, dict) else None
        logging.info(f"Processing tournament {i}: id={tournament_id}, type={type(tournament)}")
        
        if tournament_id:
            details = getTournamentDetails(tournament_id)
            if details and len(details) > 0:
                tournament_detail = details[0].get('response', {})
                # Combine basic info with detailed info
                combined = {**tournament, **tournament_detail}
                tournaments_with_details.append(combined)
                logging.info(f"Added tournament {tournament_id} to results")
            else:
                logging.warning(f"No details found for tournament {tournament_id}")
        else:
            logging.warning(f"Tournament {i} has no ID: {tournament}")
    
    logging.info(f"Returning {len(tournaments_with_details)} tournaments with details")
    return tournaments_with_details


def getTournamentDetails(tournamentID: str) -> list[dict]:
    """Get lightweight tournament details (faster than full tournament data)"""
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/details",
        expiry=(2 * 60),  # Cache for 2 minutes - details change less frequently
    )


def getTournamentGames(tournamentID: str) -> list[dict]:
    """Get all games/matches for a tournament"""
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/games",
        expiry=15,  # 15 seconds - games change frequently
    )


def getTournamentGamesForArchive(tournamentID: str) -> list[dict]:
    """Get tournament games optimized for archive usage (longer cache, completed matches focus)"""
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/games",
        expiry=(5 * 60),  # 5 minutes - archive doesn't need real-time updates
    )


def getCompletedMatchesForTournament(tournamentID: str) -> list[dict]:
    """Get only completed matches for a tournament - efficient for historical data"""
    games_data = getTournamentGamesForArchive(tournamentID)
    
    if not games_data or len(games_data) == 0:
        return []
    
    all_games = games_data[0].get('response', [])
    if not isinstance(all_games, list):
        return []
    
    # Filter to only completed matches
    completed_matches = [
        game for game in all_games 
        if game.get('state') == 'done'
    ]
    
    return completed_matches


def getTournamentMatchesWithPlayers(tournamentID: str) -> list[dict]:
    """Get tournament matches with player data enrichment - efficient single tournament version"""
    import logging
    from bracketeer.api_truefinals.cached_wrapper import getPlayerByIds
    
    logging.info(f"Getting matches with players for tournament {tournamentID}")
    
    # Get all matches for this tournament
    games_data = getTournamentGames(tournamentID)
    if not games_data or len(games_data) == 0:
        logging.warning(f"No games data found for tournament {tournamentID}")
        return []
    
    matches = games_data[0].get('response', [])
    if not isinstance(matches, list):
        logging.warning(f"Games data is not a list for tournament {tournamentID}")
        return []
    
    logging.info(f"Found {len(matches)} matches, enriching with player data")
    
    # Debug: Log first match structure
    if matches:
        logging.info(f"Sample match structure: {list(matches[0].keys())}")
        if 'slots' in matches[0]:
            logging.info(f"Sample slots structure: {matches[0]['slots'][:2] if matches[0]['slots'] else []}")
            # Log what player information might already be in slots
            for i, slot in enumerate(matches[0]['slots'][:2]):
                logging.info(f"Slot {i} keys: {list(slot.keys()) if isinstance(slot, dict) else 'not a dict'}")
                if isinstance(slot, dict):
                    logging.info(f"Slot {i} playerID: {slot.get('playerID')}")
                    logging.info(f"Slot {i} playerName: {slot.get('playerName', 'NO_PLAYER_NAME')}")
                    logging.info(f"Slot {i} name: {slot.get('name', 'NO_NAME')}")
    
    # Enrich each match with player information
    enriched_matches = []
    for i, match in enumerate(matches):
        # Add tournament ID to match for consistency
        match["tournamentID"] = tournamentID
        
        # Enrich player data in slots
        if "slots" in match:
            for j, player_slot in enumerate(match["slots"]):
                player_id = player_slot.get("playerID")
                if player_id:
                    # Check if this is a bye player (starts with "bye-")
                    if player_id.startswith("bye-"):
                        # Handle bye slots properly
                        player_slot["bracketeer_player_data"] = {
                            "id": player_id,
                            "name": "BYE",
                            "isBye": True,
                            "source": "bye_slot"
                        }
                    else:
                        # Real player - lookup from cache
                        player_data = getPlayerByIds(tournamentID, player_id)
                        
                        # If player lookup failed, try to use name from the slot itself
                        if player_data and player_data.get('name') == 'Default Player Information':
                            # Check if slot has player name directly
                            slot_name = player_slot.get('playerName') or player_slot.get('name')
                            if slot_name:
                                logging.info(f"Using slot name '{slot_name}' for player {player_id} (lookup failed)")
                                player_data = {
                                    "id": player_id,
                                    "name": slot_name,
                                    "source": "slot_fallback"
                                }
                            else:
                                logging.warning(f"No name found in slot for player {player_id}, keeping default")
                        
                        player_slot["bracketeer_player_data"] = player_data
                        if i == 0 and j == 0:  # Debug first player of first match
                            logging.info(f"Sample player data for {player_id}: {player_data}")
                            logging.info(f"Player name from data: {player_data.get('name', 'NAME_NOT_FOUND') if player_data else 'PLAYER_DATA_IS_NONE'}")
                else:
                    # Handle empty slots (no playerID)
                    player_slot["bracketeer_player_data"] = {
                        "id": None,
                        "name": "TBD",
                        "isBye": False
                    }
                    if i == 0 and j == 0:  # Debug first empty slot
                        logging.info(f"Empty slot in match {i}, slot {j}: {player_slot}")
        
        enriched_matches.append(match)
    
    logging.info(f"Enriched {len(enriched_matches)} matches with player data")
    return enriched_matches


def getCompletedMatchesWithPlayersForTournament(tournamentID: str) -> list[dict]:
    """Get completed matches with player data for a tournament - most efficient for VTT/chapters"""
    all_matches = getTournamentMatchesWithPlayers(tournamentID)
    
    # Filter to only completed matches
    completed_matches = [
        match for match in all_matches 
        if match.get('state') == 'done'
    ]
    
    return completed_matches


def getTournamentLocations(tournamentID: str) -> list[dict]:
    """Get tournament locations/arenas"""
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/locations",
        expiry=(10 * 60),  # 10 minutes - locations change rarely
    )


# DO NOT USE LIGHTLY.  THIS EMPTIES THE FILE.
def purge_API_Cache(timer_passed=3600):
    # We only care about the last 10 minutes of event match failures I suspect.
    TrueFinalsAPICache.delete().where(
        TrueFinalsAPICache.last_requested + 600 < time(),
    ).where(TrueFinalsAPICache.successful == False).run_sync()

    # Anything past the last hour we get rid of.
    TrueFinalsAPICache.delete().where(
        (TrueFinalsAPICache.last_requested + timer_passed < time()),
    ).run_sync()
