from flask import Blueprint, jsonify, render_template, request, Response
import datetime
import re

from bracketeer.api_truefinals.cached_wrapper import getAllTournamentsMatchesWithPlayers
from bracketeer.util.wrappers import ac_render_template

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
    """Tournament archive page showing historical list of tournaments with match details"""
    autoreload = request.args.get("autoreload")
    
    # Get all matches including completed ones - no filtering to see everything
    def archive_filter(x):
        # Include all matches regardless of state for archive
        return True
    
    all_matches = getAllTournamentsMatchesWithPlayers(filterFunction=archive_filter)
    
    # Get tournament display names and details from API
    from bracketeer.config import settings
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    
    tournaments_data = {}
    tournament_keys = settings.get('tournament_keys', [])
    
    # First, get all tournament metadata from API
    for tournament in tournament_keys:
        tournament_id = tournament['id']
        tournament_info = {
            'id': tournament_id,
            'name': tournament.get('weightclass', f'Tournament {tournament_id[:8]}'),
            'weight_class': tournament.get('weightclass', 'Unknown'),
            'all_matches': [],
            'completed_matches': [],
            'in_progress_matches': [],
            'upcoming_matches': [],
            'total_matches': 0,
            'completed_count': 0,
            'completion_percentage': 0,
            'start_time': None,
            'end_time': None,
            'event_date': None,
            'is_historical': False,
            'winners': [],
            'total_duration': 0
        }
        
        # Try to get tournament details from TrueFinals API
        if tournament.get('tourn_type') == 'truefinals':
            try:
                tournament_details = getTournamentDetails(tournament_id)
                if tournament_details:
                    # Extract API data
                    if isinstance(tournament_details, list) and len(tournament_details) > 0:
                        cache_entry = tournament_details[0]
                        api_data = cache_entry.get('response', cache_entry)
                    elif isinstance(tournament_details, dict):
                        api_data = tournament_details.get('response', tournament_details)
                    else:
                        api_data = None
                    
                    if api_data and isinstance(api_data, dict):
                        # Get tournament name
                        name_fields = ['title', 'name', 'tournamentName', 'event_name']
                        for field in name_fields:
                            if field in api_data:
                                tournament_info['name'] = api_data[field]
                                break
                        
                        # Get tournament date/time info
                        if 'createdAt' in api_data:
                            tournament_info['event_date'] = api_data['createdAt']
                        if 'startTime' in api_data:
                            tournament_info['start_time'] = api_data['startTime']
                        if 'endTime' in api_data:
                            tournament_info['end_time'] = api_data['endTime']
                            
            except Exception:
                # Fallback to config name if API fails
                pass
        
        tournaments_data[tournament_id] = tournament_info
    
    # Process matches and organize by tournament with detailed match data
    for match in all_matches:
        tournament_id = match.get('tournamentID')
        
        if tournament_id in tournaments_data:
            tournament_info = tournaments_data[tournament_id]
            tournament_info['all_matches'].append(match)
            tournament_info['total_matches'] += 1
            
            # Categorize matches by state
            match_state = match.get('state', 'unknown')
            
            if match_state == 'done':
                tournament_info['completed_matches'].append(match)
                tournament_info['completed_count'] += 1
                
                # Extract winner information for summary
                if 'result' in match and match['result']:
                    winner = match['result'].get('winner')
                    if winner and winner.get('name'):
                        tournament_info['winners'].append({
                            'name': winner['name'],
                            'match': match.get('bracketLabel', f"Match {len(tournament_info['completed_matches'])}"),
                            'players': [p.get('name', 'Unknown') for p in match.get('players', [])],
                            'time': match.get('calledSince')
                        })
                
                # Track match times for duration calculation
                match_time = match.get('calledSince')
                if match_time:
                    if not tournament_info['start_time'] or match_time < tournament_info['start_time']:
                        tournament_info['start_time'] = match_time
                    if not tournament_info['end_time'] or match_time > tournament_info['end_time']:
                        tournament_info['end_time'] = match_time
                        
            elif match_state in ['active', 'called', 'ready']:
                tournament_info['in_progress_matches'].append(match)
            elif match_state == 'available':
                tournament_info['upcoming_matches'].append(match)
    
    # Calculate completion percentages and determine historical status
    for tournament_info in tournaments_data.values():
        total = tournament_info['total_matches']
        completed = tournament_info['completed_count']
        
        tournament_info['completion_percentage'] = (completed / total * 100) if total > 0 else 0
        
        # Calculate total duration
        if tournament_info['start_time'] and tournament_info['end_time']:
            tournament_info['total_duration'] = (tournament_info['end_time'] - tournament_info['start_time']) / 60  # in minutes
        
        # Mark as historical/completed based on different criteria:
        # 1. Tournament has substantial completion (>=75%) OR
        # 2. Tournament is fully complete (100%) OR  
        # 3. Tournament has significant match history (>=10 completed matches)
        completion_ratio = completed / total if total > 0 else 0
        tournament_info['is_historical'] = (
            completion_ratio >= 0.75 or 
            completion_ratio == 1.0 or 
            completed >= 10
        )
        
        # Sort completed matches chronologically
        tournament_info['completed_matches'].sort(key=lambda x: x.get('calledSince') or 0)
        
        # Sort winners chronologically
        tournament_info['winners'].sort(key=lambda x: x.get('time') or 0)
    
    # Sort tournaments by most recent activity (end_time) for historical ordering
    tournament_list = list(tournaments_data.values())
    tournament_list.sort(key=lambda x: x.get('end_time') or x.get('start_time') or 0, reverse=True)
    
    # Separate historical (has completed matches) and current tournaments
    historical_tournaments = [t for t in tournament_list if t['is_historical']]
    current_tournaments = [t for t in tournament_list if not t['is_historical']]
    
    # Get event information for context
    event_config = {
        'name': settings.get('event_name', 'Unknown Event'),
        'league': settings.get('event_league', 'Unknown League'),
        'date': settings.get('event_date', 'Unknown Date')
    }
    
    return ac_render_template(
        "queueing/tournament_archive.html",
        historical_tournaments=historical_tournaments,
        current_tournaments=current_tournaments,
        event_config=event_config,
        autoreload=autoreload,
    )


@match_results.route("/tournament-summary/<tournament_id>")
def tournament_summary(tournament_id):
    """Detailed tournament summary with VTT and YouTube chapter options"""
    autoreload = request.args.get("autoreload")
    
    # Get all matches for this tournament
    def tournament_filter(x):
        return x.get('tournamentID') == tournament_id
    
    tournament_matches = getAllTournamentsMatchesWithPlayers(filterFunction=tournament_filter)
    
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
    
    # Get tournament matches
    def tournament_filter(x):
        return x.get('tournamentID') == tournament_id and x.get('state') == 'done'
    
    tournament_matches = getAllTournamentsMatchesWithPlayers(filterFunction=tournament_filter)
    tournament_matches.sort(key=lambda x: x.get('calledSince') or 0)
    
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
        
        # Get competitor names
        player1_name = "Unknown"
        player2_name = "Unknown"
        
        if 'players' in match and len(match['players']) >= 2:
            player1_name = match['players'][0].get('name', 'Unknown')
            player2_name = match['players'][1].get('name', 'Unknown')
        
        # Determine result
        result_text = ""
        if 'result' in match:
            if match['result'].get('winner'):
                winner_name = match['result']['winner'].get('name', 'Unknown')
                result_text = f" - Winner: {winner_name}"
        
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
    
    # Get tournament matches
    def tournament_filter(x):
        return x.get('tournamentID') == tournament_id and x.get('state') == 'done'
    
    tournament_matches = getAllTournamentsMatchesWithPlayers(filterFunction=tournament_filter)
    tournament_matches.sort(key=lambda x: x.get('calledSince') or 0)
    
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
        
        # Get competitor names
        player1_name = "Unknown"
        player2_name = "Unknown"
        
        if 'players' in match and len(match['players']) >= 2:
            player1_name = match['players'][0].get('name', 'Unknown')
            player2_name = match['players'][1].get('name', 'Unknown')
        
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
