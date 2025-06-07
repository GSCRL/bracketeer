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


@match_results.errorhandler(500)
def internal_error(error):
    autoreload = request.args.get("autoreload")
    return render_template(
        "base.html",
        autoreload=autoreload,
        errormsg="Sorry, this page has produced an error while generating.  Please try again in 30s.",
    )
