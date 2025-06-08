from flask import Blueprint, jsonify, render_template, request, Response
import datetime
import re

from bracketeer.api_truefinals.cached_wrapper import getAllTournamentsMatchesWithPlayers
from bracketeer.util.wrappers import ac_render_template


def derive_tournament_status(tournament_data):
    """
    Derive tournament status from API data since TrueFinals may not always provide explicit status.
    
    Known TrueFinals tournament statuses (from setup wizard):
    - "completed" - Tournament is finished
    - "active" - Tournament is currently running  
    - "created" - Tournament is created but not started
    - "checkin" - Tournament is in check-in phase
    - "scheduled" - Tournament is scheduled but not active
    - "unknown" - Status cannot be determined
    """
    # If API provides explicit status, use it
    if 'status' in tournament_data:
        return tournament_data['status']
    
    # Derive status from timestamps
    start_time = tournament_data.get('startTime')
    end_time = tournament_data.get('endTime')
    create_time = tournament_data.get('createTime')
    scheduled_start = tournament_data.get('scheduledStartTime')
    
    # Tournament has ended
    if end_time:
        return "completed"
    
    # Tournament has started but not ended
    if start_time:
        return "active"
    
    # Tournament is scheduled to start
    if scheduled_start:
        return "scheduled"
    
    # Tournament created but not started
    if create_time:
        return "created"
    
    # Cannot determine status
    return "unknown"

# Template filter for formatting video timestamps
def format_video_timestamp(seconds):
    """Format seconds as video timestamp (MM:SS or H:MM:SS)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

match_results = Blueprint(
    "match_results",
    __name__,
    static_folder="./static",
    template_folder="./templates",
)

# Template filters
def timestamp_to_time(timestamp):
    """Convert Unix timestamp to readable time"""
    import datetime
    if timestamp:
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime('%H:%M')
    return '-'

# Register template filters
match_results.add_app_template_filter(format_video_timestamp, 'format_video_timestamp')
match_results.add_app_template_filter(timestamp_to_time, 'timestamp_to_time')


class reversor:
    def __init__(self, obj):
        self.obj = obj

    def __eq__(self, other):
        return other.obj == self.obj

    def __lt__(self, other):
        return other.obj < self.obj


def filtering_func(x):
    # Include matches that are called, ready, active, or available (upcoming)
    # Exclude completed ("done") and unavailable matches
    if "state" in x:
        return x["state"] in ["called", "ready", "active", "available"]
    return False


def _json_api_stub():
    matches = getAllTournamentsMatchesWithPlayers(filterFunction=filtering_func)
    
    # Get tournament display names for better identification
    from bracketeer.config import settings
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    
    tournament_names = {}
    tournament_keys = settings.get('tournament_keys', [])
    
    for tournament in tournament_keys:
        if tournament.get('tourn_type') == 'truefinals':
            try:
                tournament_details = getTournamentDetails(tournament['id'])
                if tournament_details:
                    if isinstance(tournament_details, list) and len(tournament_details) > 0:
                        cache_entry = tournament_details[0]
                        api_data = cache_entry.get('response', cache_entry)
                    elif isinstance(tournament_details, dict):
                        api_data = tournament_details.get('response', tournament_details)
                    else:
                        api_data = None
                    
                    if api_data and isinstance(api_data, dict):
                        name_fields = ['title', 'name', 'tournamentName', 'event_name']
                        tournament_name = None
                        for field in name_fields:
                            if field in api_data:
                                tournament_name = api_data[field]
                                break
                        
                        if tournament_name:
                            tournament_names[tournament['id']] = tournament_name
                        else:
                            tournament_names[tournament['id']] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
            except Exception:
                tournament_names[tournament['id']] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
        else:
            tournament_names[tournament['id']] = tournament.get('weightclass', f'Tournament {tournament["id"]}')
    
    # Organize matches by status and add tournament display names
    organized_matches = {
        'active': [],      # Currently fighting
        'on_deck': [],     # Called to arena, ready to fight
        'upcoming': []     # Available but not yet called
    }
    
    for match in matches:
        # Add tournament display name to match
        tournament_id = match.get('tournamentID')
        if tournament_id in tournament_names:
            match['tournament_display_name'] = tournament_names[tournament_id]
        
        if match.get('state') == 'active':
            organized_matches['active'].append(match)
        elif match.get('state') in ['called', 'ready']:
            organized_matches['on_deck'].append(match)
        elif match.get('state') == 'available':
            organized_matches['upcoming'].append(match)
    
    # Sort each category
    # Active: by how long they've been active (newest first)
    organized_matches['active'].sort(
        key=lambda x: x.get('calledSince') or 0,
        reverse=True
    )
    
    # On deck: by how long they've been called (oldest first - first called fights first)
    organized_matches['on_deck'].sort(
        key=lambda x: x.get('calledSince') or 0,
        reverse=False
    )
    
    # Upcoming: keep tournament order (no specific sorting needed)
    
    # Combine for backward compatibility
    all_matches = organized_matches['active'] + organized_matches['on_deck'] + organized_matches['upcoming']
    
    # Add the organized data for the enhanced template
    result = type('MatchData', (), {
        '_matches': all_matches,
        'organized': organized_matches,
        'active_count': len(organized_matches['active']),
        'on_deck_count': len(organized_matches['on_deck']),
        'upcoming_count': len(organized_matches['upcoming'])
    })()
    
    return result


@match_results.route("/upcoming.json")
def _json_api_results():
    match_data = _json_api_stub()

    return jsonify(match_data._matches)


@match_results.route("/debug/raw")
def _debug_raw_matches():
    """Debug route to see raw match data with states"""
    from bracketeer.api_truefinals.cached_wrapper import getAllTournamentsMatchesWithPlayers
    
    # Get all matches without filtering to see states
    all_matches = getAllTournamentsMatchesWithPlayers()
    
    # Create summary of match states
    state_summary = {}
    match_details = []
    
    for match in all_matches:
        state = match.get('state', 'unknown')
        if state not in state_summary:
            state_summary[state] = 0
        state_summary[state] += 1
        
        match_details.append({
            'name': match.get('name', 'Unknown'),
            'state': state,
            'tournament': match.get('tournamentID', 'Unknown'),
            'winner': match.get('winner'),
            'has_winner': bool(match.get('winner'))
        })
    
    return jsonify({
        'state_summary': state_summary,
        'total_matches': len(all_matches),
        'match_details': match_details[:20]  # First 20 matches for inspection
    })


@match_results.route("/debug/owned-tournaments")
def debug_owned_tournaments():
    """Debug route to inspect owned tournaments API response"""
    from bracketeer.api_truefinals.cached_api import getUserTournaments, getOwnedTournamentsWithDetails, getTournamentDetails
    import logging
    
    logging.info("=== DEBUG: Starting owned tournaments debug ===")
    
    # Step 1: Raw /v1/user/tournaments response
    logging.info("=== DEBUG: Calling getUserTournaments ===")
    raw_user_tournaments = getUserTournaments()
    logging.info(f"=== DEBUG: getUserTournaments returned: {len(raw_user_tournaments) if raw_user_tournaments else 0} items ===")
    
    # Step 2: Processed owned tournaments with details
    logging.info("=== DEBUG: Calling getOwnedTournamentsWithDetails ===")
    owned_tournaments = getOwnedTournamentsWithDetails()
    logging.info(f"=== DEBUG: getOwnedTournamentsWithDetails returned: {len(owned_tournaments) if owned_tournaments else 0} items ===")
    
    # Step 3: Check tournament structure
    sample_tournament_details = None
    tournaments_list = []
    if raw_user_tournaments and len(raw_user_tournaments) > 0:
        tournaments_list = raw_user_tournaments[0].get('response', [])
        logging.info(f"=== DEBUG: Found {len(tournaments_list)} tournaments in response ===")
        if tournaments_list and len(tournaments_list) > 0:
            sample_tournament_id = tournaments_list[0].get('id')
            logging.info(f"=== DEBUG: Sample tournament ID: {sample_tournament_id} ===")
            if sample_tournament_id:
                sample_tournament_details = getTournamentDetails(sample_tournament_id)
                logging.info(f"=== DEBUG: Sample tournament details: {len(sample_tournament_details) if sample_tournament_details else 0} items ===")
    
    return jsonify({
        "debug_info": "Check server logs for detailed debugging",
        "step1_raw_user_tournaments": raw_user_tournaments,
        "step1_count": len(raw_user_tournaments) if raw_user_tournaments else 0,
        "step1_response_structure": list(raw_user_tournaments[0].keys()) if raw_user_tournaments and len(raw_user_tournaments) > 0 else [],
        "step1_tournaments_list": tournaments_list[:3] if tournaments_list else [],  # First 3 tournaments
        
        "step2_owned_tournaments": owned_tournaments,
        "step2_count": len(owned_tournaments) if owned_tournaments else 0,
        
        "step3_sample_tournament_details": sample_tournament_details,
        "step3_sample_count": len(sample_tournament_details) if sample_tournament_details else 0,
        
        "error_check": "If step2_count is 0 but step1_count > 0, there's an issue in getOwnedTournamentsWithDetails"
    })


@match_results.route("/upcoming")
def routeForUpcomingMatches():
    autoreload = request.args.get("autoreload")
    show_header = request.args.get("show_header")
    refresh = request.args.get("refresh")

    # Force cache refresh if requested
    if refresh:
        from bracketeer.api_truefinals.cached_api import purge_API_Cache
        purge_API_Cache(timer_passed=0)  # Purge all cache entries

    match_data = _json_api_stub()

    return ac_render_template(
        "queueing/upcoming_matches.html",
        div_matches=match_data._matches,
        match_data=match_data,
        autoreload=autoreload,
        show_header=show_header,
    )


@match_results.route("/completed")
def routeForLastMatches():
    autoreload = request.args.get("autoreload")

    matches = []

    return ac_render_template(
        "queueing/last_matches.html",
        div_matches=matches,
        autoreload=autoreload,
    )


@match_results.route("/fight-log")
def routeForFightLog():
    """Fight log showing all completed matches organized by tournament"""
    from bracketeer.api_truefinals.cached_wrapper import getAllTournamentsMatchesWithPlayers
    from bracketeer.config import settings
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    
    # Get tournament filter if specified
    tournament_filter = request.args.get('tournament')
    autoreload = request.args.get("autoreload")
    
    # Get all matches including completed ones
    def all_matches_filter(x):
        # Include all matches that have results or are completed
        if "state" in x:
            return x["state"] in ["done", "active", "called", "ready", "available"]
        return True
    
    all_matches = getAllTournamentsMatchesWithPlayers(filterFunction=all_matches_filter)
    
    # Get tournament names for display
    tournament_names = {}
    tournament_keys = settings.get('tournament_keys', [])
    
    for tournament in tournament_keys:
        if tournament.get('tourn_type') == 'truefinals':
            try:
                tournament_details = getTournamentDetails(tournament['id'])
                if tournament_details:
                    if isinstance(tournament_details, list) and len(tournament_details) > 0:
                        cache_entry = tournament_details[0]
                        api_data = cache_entry.get('response', cache_entry)
                    elif isinstance(tournament_details, dict):
                        api_data = tournament_details.get('response', tournament_details)
                    else:
                        api_data = None
                    
                    if api_data and isinstance(api_data, dict):
                        name_fields = ['title', 'name', 'tournamentName', 'event_name']
                        tournament_name = None
                        for field in name_fields:
                            if field in api_data:
                                tournament_name = api_data[field]
                                break
                        
                        if tournament_name:
                            tournament_names[tournament['id']] = tournament_name
                        else:
                            tournament_names[tournament['id']] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
            except Exception:
                tournament_names[tournament['id']] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
        else:
            tournament_names[tournament['id']] = tournament.get('weightclass', f'Tournament {tournament["id"]}')
    
    # Organize matches by tournament
    tournaments_data = {}
    
    for match in all_matches:
        tournament_id = match.get('tournamentID')
        
        # Apply tournament filter if specified
        if tournament_filter and tournament_id != tournament_filter:
            continue
            
        if tournament_id not in tournaments_data:
            tournaments_data[tournament_id] = {
                'id': tournament_id,
                'name': tournament_names.get(tournament_id, f'Tournament {tournament_id[:8]}'),
                'completed_matches': [],
                'in_progress_matches': [],
                'upcoming_matches': [],
                'stats': {
                    'total_matches': 0,
                    'completed': 0,
                    'in_progress': 0,
                    'upcoming': 0
                }
            }
        
        # Add tournament display name to match
        match['tournament_display_name'] = tournaments_data[tournament_id]['name']
        
        # Categorize matches
        state = match.get('state', 'unknown')
        if state == 'done':
            tournaments_data[tournament_id]['completed_matches'].append(match)
            tournaments_data[tournament_id]['stats']['completed'] += 1
        elif state in ['active', 'called', 'ready']:
            tournaments_data[tournament_id]['in_progress_matches'].append(match)
            tournaments_data[tournament_id]['stats']['in_progress'] += 1
        elif state == 'available':
            tournaments_data[tournament_id]['upcoming_matches'].append(match)
            tournaments_data[tournament_id]['stats']['upcoming'] += 1
        
        tournaments_data[tournament_id]['stats']['total_matches'] += 1
    
    # Sort matches within each tournament by completion time (most recent first) for completed,
    # and by call time for in-progress
    for tournament_data in tournaments_data.values():
        # Sort completed matches by most recent first (handle None values)
        tournament_data['completed_matches'].sort(
            key=lambda x: x.get('calledSince') or 0,
            reverse=True
        )
        
        # Sort in-progress by earliest called first (handle None values)
        tournament_data['in_progress_matches'].sort(
            key=lambda x: x.get('calledSince') or 0,
            reverse=False
        )
    
    # Create list of tournaments for filter dropdown
    available_tournaments = [
        {'id': tid, 'name': data['name']} 
        for tid, data in tournaments_data.items()
    ]
    available_tournaments.sort(key=lambda x: x['name'])
    
    return ac_render_template(
        "queueing/fight_log.html",
        tournaments_data=tournaments_data,
        available_tournaments=available_tournaments,
        current_filter=tournament_filter,
        autoreload=autoreload,
    )


@match_results.route("/tournament-archive")
def tournament_archive():
    """Tournament archive page showing owned tournaments with efficient API usage"""
    autoreload = request.args.get("autoreload")
    debug_mode = request.args.get("debug")
    
    # Get owned tournaments directly from TrueFinals API - same as setup wizard
    from bracketeer.api_truefinals.cached_api import getUserTournaments, getCompletedMatchesForTournament
    from bracketeer.config import settings
    import logging
    
    # Debug: Check raw API response
    if debug_mode:
        raw_user_tournaments = getUserTournaments()
        return jsonify({
            "debug": True,
            "raw_user_tournaments": raw_user_tournaments,
            "raw_user_tournaments_type": type(raw_user_tournaments).__name__,
            "raw_user_tournaments_length": len(raw_user_tournaments) if raw_user_tournaments else 0
        })
    
    # Use the SAME approach as the working setup wizard
    try:
        tournaments_data_raw = getUserTournaments()
        if not tournaments_data_raw or len(tournaments_data_raw) == 0:
            logging.warning("No tournaments data returned from getUserTournaments()")
            owned_tournaments = []
        else:
            owned_tournaments = tournaments_data_raw[0].get('response', [])
            logging.info(f"Tournament Archive: Found {len(owned_tournaments)} tournaments from API")
    except Exception as e:
        logging.error(f"Tournament Archive: Error getting tournaments: {e}")
        owned_tournaments = []
    
    tournaments_data = {}
    
    # Process tournaments simply - same as setup wizard approach
    for tournament in owned_tournaments:
        tournament_id = tournament.get('id')
        if not tournament_id:
            continue
            
        # Use basic tournament data from API response
        # Convert timestamps to human-readable format for template
        create_time = tournament.get('createTime')
        event_date_str = None
        if create_time:
            try:
                import datetime
                event_date_str = datetime.datetime.fromtimestamp(create_time).strftime('%Y-%m-%d')
            except:
                event_date_str = 'Date unknown'
        
        tournament_info = {
            'id': tournament_id,
            'name': tournament.get('title') or tournament.get('name') or f'Tournament {tournament_id[:8]}',
            'status': derive_tournament_status(tournament),
            'privacy': tournament.get('privacy', 'unknown'),
            'create_time': create_time,
            'end_time': tournament.get('endTime'),
            'start_time': tournament.get('startTime'),
            'event_date': event_date_str,  # Template-friendly date string
            'sort_timestamp': tournament.get('endTime') or tournament.get('startTime') or create_time or 0,  # For sorting
            
            # Template expects these fields - set defaults since we're not loading match data yet
            'completion_percentage': 100 if derive_tournament_status(tournament) == 'completed' else 0,
            'total_matches': 0,  # Will be populated when matches are loaded
            'completed_count': 0,  # Will be populated when matches are loaded
            'is_historical': derive_tournament_status(tournament) == 'completed',
            'winners': [],  # Will be populated when matches are loaded
            'total_duration': 0,  # Will be populated when matches are loaded
            
            'raw_tournament_data': tournament  # Keep raw data for debugging
        }
        
        tournaments_data[tournament_id] = tournament_info
        logging.info(f"Tournament Archive: Processed {tournament_id} - Status: {tournament_info['status']}")
    
    # STEP 1: Just get the tournament list - NO match data fetching yet
    # Match data will be fetched on-demand when user selects a specific tournament
    
    # Sort tournaments using API data directly  
    tournament_list = list(tournaments_data.values())
    
    # Sort by most recent first (using numeric timestamps for proper sorting)
    tournament_list.sort(key=lambda x: x.get('sort_timestamp', 0), reverse=True)
    
    # Categorize tournaments by status for display
    tournaments_by_status = {
        'completed': [t for t in tournament_list if t['status'] == 'completed'],
        'active': [t for t in tournament_list if t['status'] == 'active'], 
        'created': [t for t in tournament_list if t['status'] == 'created'],
        'checkin': [t for t in tournament_list if t['status'] == 'checkin'],
        'scheduled': [t for t in tournament_list if t['status'] == 'scheduled'],
        'unknown': [t for t in tournament_list if t['status'] == 'unknown']
    }
    
    # Get event information for context
    event_config = {
        'name': settings.get('event_name', 'Unknown Event'),
        'league': settings.get('event_league', 'Unknown League'),
        'date': settings.get('event_date', 'Unknown Date')
    }
    
    # Debug info for troubleshooting
    debug_info = {
        'api_call_success': len(owned_tournaments) > 0,
        'raw_tournaments_count': len(owned_tournaments), 
        'processed_tournaments_count': len(tournaments_data),
        'tournament_statuses': {tid: data['status'] for tid, data in tournaments_data.items()},
        'status_counts': {status: len(tournaments) for status, tournaments in tournaments_by_status.items()},
        'sample_tournaments': [
            {
                'id': t.get('id'),
                'title': t.get('title'),
                'status': derive_tournament_status(t) if t else 'none'
            } for t in owned_tournaments[:3]
        ] if owned_tournaments else []
    }
    
    return ac_render_template(
        "queueing/tournament_archive.html",
        historical_tournaments=tournaments_by_status['completed'],  # Template expects this name
        completed_tournaments=tournaments_by_status['completed'],
        active_tournaments=tournaments_by_status['active'],
        created_tournaments=tournaments_by_status['created'],
        all_tournaments=tournament_list,
        tournaments_by_status=tournaments_by_status,
        event_config=event_config,
        debug_info=debug_info,
        autoreload=autoreload,
    )


@match_results.route("/tournament-summary/<tournament_id>")
def tournament_summary(tournament_id):
    """Detailed tournament summary with VTT and YouTube chapter options"""
    import logging
    logging.warning(f"=== TOURNAMENT SUMMARY ROUTE CALLED FOR {tournament_id} ===")
    
    autoreload = request.args.get("autoreload")
    
    # Get matches with player data for this specific tournament efficiently
    from bracketeer.api_truefinals.cached_api import getTournamentMatchesWithPlayers
    
    logging.info(f"Tournament Summary: Loading enriched matches for tournament {tournament_id}")
    
    # Get ALL matches with player data for this tournament
    try:
        tournament_matches = getTournamentMatchesWithPlayers(tournament_id)
        logging.info(f"Tournament Summary: Found {len(tournament_matches)} enriched matches")
    except Exception as e:
        logging.error(f"Tournament Summary: Error getting enriched matches for {tournament_id}: {e}")
        tournament_matches = []
    
    # Get tournament details
    from bracketeer.config import settings
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    
    tournament_name = f'Tournament {tournament_id[:8]}'
    try:
        tournament_details = getTournamentDetails(tournament_id)
        if tournament_details:
            if isinstance(tournament_details, list) and len(tournament_details) > 0:
                cache_entry = tournament_details[0]
                api_data = cache_entry.get('response', cache_entry)
            elif isinstance(tournament_details, dict):
                api_data = tournament_details.get('response', tournament_details)
            else:
                api_data = None
            
            if api_data and isinstance(api_data, dict):
                name_fields = ['title', 'name', 'tournamentName', 'event_name']
                for field in name_fields:
                    if field in api_data:
                        tournament_name = api_data[field]
                        break
    except Exception:
        pass
    
    # Sort matches chronologically by start time
    completed_matches = [m for m in tournament_matches if m.get('state') == 'done']
    completed_matches.sort(key=lambda x: x.get('calledSince') or 0)
    
    # Transform match data to template-friendly format
    for match in completed_matches:
        # Create simplified players array from slots with bracketeer_player_data
        match['players'] = []
        match['result'] = {'winner': None}
        
        if 'slots' in match:
            for slot in match['slots']:
                player_data = slot.get('bracketeer_player_data', {})
                player_name = player_data.get('name', 'Unknown')
                
                # Handle default player data case and byes
                if player_name == 'Default Player Information':
                    player_name = 'Unknown'
                elif player_name == 'BYE':
                    player_name = 'BYE'
                
                player_info = {
                    'name': player_name,
                    'id': player_data.get('id'),
                    'is_winner': slot.get('slotState') == 'winner'
                }
                match['players'].append(player_info)
                
                # Set winner if this slot won
                if slot.get('slotState') == 'winner':
                    match['result']['winner'] = player_info
    
    # Calculate match statistics
    total_matches = len(tournament_matches)
    completed_count = len(completed_matches)
    
    # Get event configuration for additional context
    event_config = {
        'name': settings.get('event_name', 'Unknown Event'),
        'league': settings.get('event_league', 'Unknown League'),
        'date': settings.get('event_date', 'Unknown Date'),
        'match_duration': settings.get('match_duration', 150)
    }
    
    return ac_render_template(
        "queueing/tournament_summary.html",
        tournament_id=tournament_id,
        tournament_name=tournament_name,
        tournament_matches=completed_matches,
        total_matches=total_matches,
        completed_count=completed_count,
        event_config=event_config,
        autoreload=autoreload,
    )


@match_results.route("/tournament-vtt/<tournament_id>")
def generate_vtt(tournament_id):
    """Generate VTT subtitle file for tournament matches"""
    import logging
    from bracketeer.api_truefinals.cached_api import getCompletedMatchesWithPlayersForTournament
    
    logging.info(f"VTT Generation: Getting completed matches with players for tournament {tournament_id}")
    
    # Get completed matches with player data for this tournament efficiently
    tournament_matches = getCompletedMatchesWithPlayersForTournament(tournament_id)
    if tournament_matches:
        logging.info(f"VTT Generation: Found {len(tournament_matches)} completed matches with players")
        tournament_matches.sort(key=lambda x: x.get('calledSince') or 0)
    else:
        logging.warning(f"VTT Generation: No completed matches found for tournament {tournament_id}")
        tournament_matches = []
    
    if not tournament_matches:
        return Response("No completed matches found for this tournament", status=404)
    
    # Get tournament name
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    tournament_name = f'Tournament {tournament_id[:8]}'
    try:
        tournament_details = getTournamentDetails(tournament_id)
        if tournament_details:
            # Extract tournament name from API response
            if isinstance(tournament_details, list) and len(tournament_details) > 0:
                cache_entry = tournament_details[0]
                api_data = cache_entry.get('response', cache_entry)
            elif isinstance(tournament_details, dict):
                api_data = tournament_details.get('response', tournament_details)
            else:
                api_data = None
            
            if api_data and isinstance(api_data, dict):
                name_fields = ['title', 'name', 'tournamentName', 'event_name']
                for field in name_fields:
                    if field in api_data:
                        tournament_name = api_data[field]
                        break
    except Exception:
        pass
    
    # Generate VTT content
    vtt_content = "WEBVTT\n\n"
    
    # Calculate relative timestamps (assuming matches are sequential)
    current_time = 0  # Start at 0 seconds
    match_duration = 150  # Default 2.5 minutes per match
    break_duration = 60   # 1 minute between matches
    
    for i, match in enumerate(tournament_matches):
        # Calculate match timing
        start_time = current_time
        end_time = current_time + match_duration
        
        # Format timestamp (HH:MM:SS.mmm)
        start_formatted = format_vtt_timestamp(start_time)
        end_formatted = format_vtt_timestamp(end_time)
        
        # Get competitor names from TrueFinals slots structure
        player1_name = "Unknown"
        player2_name = "Unknown"
        
        if 'slots' in match and len(match['slots']) >= 2:
            # Use enriched player data
            slot1 = match['slots'][0]
            slot2 = match['slots'][1]
            
            if 'bracketeer_player_data' in slot1:
                name1 = slot1['bracketeer_player_data'].get('name', 'Unknown')
                if name1 == 'Default Player Information':
                    player1_name = 'Unknown'
                elif name1 == 'BYE':
                    player1_name = 'BYE'
                else:
                    player1_name = name1
            
            if 'bracketeer_player_data' in slot2:
                name2 = slot2['bracketeer_player_data'].get('name', 'Unknown')
                if name2 == 'Default Player Information':
                    player2_name = 'Unknown'
                elif name2 == 'BYE':
                    player2_name = 'BYE'
                else:
                    player2_name = name2
        
        # Determine result from slots
        result_text = ""
        winner_name = "Unknown"
        if 'slots' in match:
            for slot in match['slots']:
                if slot.get('slotState') == 'winner':
                    if 'bracketeer_player_data' in slot:
                        name = slot['bracketeer_player_data'].get('name', 'Unknown')
                        if name == 'Default Player Information':
                            winner_name = 'Unknown'
                        elif name == 'BYE':
                            winner_name = 'BYE'
                        else:
                            winner_name = name
                        result_text = f" - Winner: {winner_name}"
                        break
        
        # Create VTT entry
        vtt_content += f"{i + 1}\n"
        vtt_content += f"{start_formatted} --> {end_formatted}\n"
        vtt_content += f"Match {i + 1}: {player1_name} vs {player2_name}{result_text}\n\n"
        
        # Move to next match time
        current_time = end_time + break_duration
    
    # Create filename
    safe_tournament_name = re.sub(r'[^\w\s-]', '', tournament_name).strip()
    safe_tournament_name = re.sub(r'[-\s]+', '-', safe_tournament_name)
    filename = f"{safe_tournament_name}-matches.vtt"
    
    return Response(
        vtt_content,
        mimetype='text/vtt',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@match_results.route("/tournament-youtube-chapters/<tournament_id>")
def generate_youtube_chapters(tournament_id):
    """Generate YouTube chapter markers for tournament matches"""
    import logging
    from bracketeer.api_truefinals.cached_api import getCompletedMatchesWithPlayersForTournament
    
    logging.info(f"YouTube Chapters: Getting completed matches with players for tournament {tournament_id}")
    
    # Get completed matches with player data for this tournament efficiently
    tournament_matches = getCompletedMatchesWithPlayersForTournament(tournament_id)
    if tournament_matches:
        logging.info(f"YouTube Chapters: Found {len(tournament_matches)} completed matches with players")
        tournament_matches.sort(key=lambda x: x.get('calledSince') or 0)
    else:
        logging.warning(f"YouTube Chapters: No completed matches found for tournament {tournament_id}")
        tournament_matches = []
    
    if not tournament_matches:
        return Response("No completed matches found for this tournament", status=404)
    
    # Generate YouTube chapters
    chapters_content = ""
    
    # Calculate relative timestamps
    current_time = 0
    match_duration = 150  # 2.5 minutes per match
    break_duration = 60   # 1 minute between matches
    
    for i, match in enumerate(tournament_matches):
        # Format timestamp for YouTube (MM:SS or H:MM:SS)
        timestamp = format_youtube_timestamp(current_time)
        
        # Get competitor names from TrueFinals slots structure
        player1_name = "Unknown"
        player2_name = "Unknown"
        
        if 'slots' in match and len(match['slots']) >= 2:
            # Use enriched player data
            slot1 = match['slots'][0]
            slot2 = match['slots'][1]
            
            if 'bracketeer_player_data' in slot1:
                name1 = slot1['bracketeer_player_data'].get('name', 'Unknown')
                if name1 == 'Default Player Information':
                    player1_name = 'Unknown'
                elif name1 == 'BYE':
                    player1_name = 'BYE'
                else:
                    player1_name = name1
            
            if 'bracketeer_player_data' in slot2:
                name2 = slot2['bracketeer_player_data'].get('name', 'Unknown')
                if name2 == 'Default Player Information':
                    player2_name = 'Unknown'
                elif name2 == 'BYE':
                    player2_name = 'BYE'
                else:
                    player2_name = name2
        
        # Create chapter entry
        chapters_content += f"{timestamp} Match {i + 1}: {player1_name} vs {player2_name}\n"
        
        # Move to next match time
        current_time += match_duration + break_duration
    
    # Get tournament name for filename
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    tournament_name = f'Tournament {tournament_id[:8]}'
    try:
        tournament_details = getTournamentDetails(tournament_id)
        if tournament_details:
            if isinstance(tournament_details, list) and len(tournament_details) > 0:
                cache_entry = tournament_details[0]
                api_data = cache_entry.get('response', cache_entry)
            elif isinstance(tournament_details, dict):
                api_data = tournament_details.get('response', tournament_details)
            else:
                api_data = None
            
            if api_data and isinstance(api_data, dict):
                name_fields = ['title', 'name', 'tournamentName', 'event_name']
                for field in name_fields:
                    if field in api_data:
                        tournament_name = api_data[field]
                        break
    except Exception:
        pass
    
    safe_tournament_name = re.sub(r'[^\w\s-]', '', tournament_name).strip()
    safe_tournament_name = re.sub(r'[-\s]+', '-', safe_tournament_name)
    filename = f"{safe_tournament_name}-youtube-chapters.txt"
    
    return Response(
        chapters_content,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


def format_vtt_timestamp(seconds):
    """Format seconds as VTT timestamp (HH:MM:SS.mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def format_youtube_timestamp(seconds):
    """Format seconds as YouTube timestamp (MM:SS or H:MM:SS)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


@match_results.errorhandler(500)
def internal_error(error):
    autoreload = request.args.get("autoreload")
    return render_template(
        "base.html",
        autoreload=autoreload,
        errormsg="Sorry, this page has produced an error while generating.  Please try again in 30s.",
    )
