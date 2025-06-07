from flask import Blueprint, jsonify, render_template, request

from bracketeer.api_truefinals.cached_wrapper import getAllTournamentsMatchesWithPlayers
from bracketeer.util.wrappers import ac_render_template

match_results = Blueprint(
    "match_results",
    __name__,
    static_folder="./static",
    template_folder="./templates",
)


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
        key=lambda x: x.get('calledSince', 0),
        reverse=True
    )
    
    # On deck: by how long they've been called (oldest first - first called fights first)
    organized_matches['on_deck'].sort(
        key=lambda x: x.get('calledSince', 0),
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
        # Sort completed matches by most recent first (if we had completion time)
        tournament_data['completed_matches'].sort(
            key=lambda x: x.get('calledSince', 0),
            reverse=True
        )
        
        # Sort in-progress by earliest called first
        tournament_data['in_progress_matches'].sort(
            key=lambda x: x.get('calledSince', 0),
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


@match_results.errorhandler(500)
def internal_error(error):
    autoreload = request.args.get("autoreload")
    return render_template(
        "base.html",
        autoreload=autoreload,
        errormsg="Sorry, this page has produced an error while generating.  Please try again in 30s.",
    )
