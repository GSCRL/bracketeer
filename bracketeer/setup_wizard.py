import json
import logging
import time
from pathlib import Path

from flask import Blueprint, flash, jsonify, redirect, request, url_for

from bracketeer.api_truefinals.cached_api import (
    getEventInformation,
    getTournamentDetails,
    getTournamentGames,
    getUserTournaments,
)
from bracketeer.config import secrets, settings
from bracketeer.util.wrappers import ac_render_template

setup_wizard = Blueprint("setup_wizard", __name__)


def test_truefinals_connection():
    """Test if TrueFinals API credentials are working"""
    try:
        if not secrets.truefinals.api_key or not secrets.truefinals.user_id:
            return False, "TrueFinals API credentials not configured"
        
        tournaments = getUserTournaments()
        if tournaments and len(tournaments) > 0:
            return True, "Connection successful"
        else:
            return False, "No tournaments found or API error"
    except Exception as e:
        return False, f"API Error: {str(e)}"


def get_available_tournaments():
    """Get list of available tournaments from TrueFinals API with enriched details"""
    try:
        tournaments_data = getUserTournaments()
        if not tournaments_data or len(tournaments_data) == 0:
            logging.warning("No tournaments data returned from getUserTournaments()")
            return []
        
        tournaments = tournaments_data[0].get('response', [])
        logging.info(f"Found {len(tournaments)} tournaments from API")
        for t in tournaments[:5]:  # Log first 5 tournaments for debugging
            logging.info(f"Tournament from API: {t.get('id')} - Status: {t.get('status', 'unknown')}")
        
        # Note: Manual tournaments can now be added via the UI
        
        # Filter for tournaments that are not completed
        available_tournaments = []
        for tournament in tournaments:
            status = tournament.get('status', 'unknown').lower()
            
            # Only include tournaments that are not completed (exclude finished tournaments)
            if status in ['created', 'checkin', 'active', 'scheduled', 'unknown'] or status == '':
                # Get tournament details to show actual name and info
                try:
                    logging.info(f"Fetching details for tournament {tournament.get('id')}")
                    # Try lightweight details first, fallback to full tournament data
                    details_data = None
                    try:
                        details_data = getTournamentDetails(tournament['id'])
                    except Exception as e:
                        logging.warning(f"Lightweight details failed for {tournament['id']}, trying full data: {e}")
                        details_data = getEventInformation(tournament['id'])
                    
                    if details_data and len(details_data) > 0:
                        details = details_data[0].get('response', {})
                        # Use correct fields from TrueFinals API
                        tournament['display_name'] = details.get('title', tournament.get('name', tournament['id']))
                        tournament['player_count'] = len(details.get('players', []))
                        tournament['event_location'] = details.get('eventLocation', '')
                        tournament['description'] = details.get('description', '')
                        tournament['created_date'] = details.get('createTime', 0)
                        tournament['start_time'] = details.get('scheduledStartTime', 0)
                        tournament['end_time'] = details.get('endTime', 0)
                        
                        # Get games data for more accurate status - only if we have lightweight details
                        games = details.get('games', [])
                        if not games:
                            # If no games in details, try fetching them separately (but handle errors)
                            try:
                                games_data = getTournamentGames(tournament['id'])
                                if games_data and len(games_data) > 0:
                                    # Handle different response formats
                                    games_response = games_data[0]
                                    if isinstance(games_response, dict):
                                        games = games_response.get('response', [])
                                    elif isinstance(games_response, list):
                                        games = games_response
                                    else:
                                        games = []
                            except Exception as e:
                                logging.warning(f"Could not fetch games for tournament {tournament['id']}: {e}")
                                games = []
                        
                        active_games = [g for g in games if g.get('state') in ['called', 'active', 'hold']]
                        completed_games = [g for g in games if g.get('state') == 'done']
                        
                        current_time = time.time() * 1000  # Convert to milliseconds
                        end_time = details.get('endTime') or 0
                        start_time = details.get('startTime') or 0
                        scheduled_start = details.get('scheduledStartTime') or 0
                        
                        # Determine status based on game activity first, then timing
                        if active_games:
                            tournament['status'] = 'active'
                        elif end_time > 0 and current_time > end_time:
                            tournament['status'] = 'completed'
                        elif len(games) > 0 and len(completed_games) == len(games):
                            tournament['status'] = 'completed'  # All games done
                        elif start_time > 0 and current_time > start_time:
                            tournament['status'] = 'active'
                        elif scheduled_start > 0:
                            tournament['status'] = 'scheduled'
                        else:
                            tournament['status'] = 'created'
                        
                        # Skip completed tournaments
                        if tournament['status'] == 'completed':
                            logging.info(f"Skipping completed tournament: {tournament.get('id')} - {tournament.get('display_name')}")
                            continue
                        
                        logging.info(f"Including tournament: {tournament.get('id')} - {tournament.get('display_name')} - Status: {tournament['status']}")
                    else:
                        # Fallback if details can't be fetched
                        tournament['display_name'] = tournament.get('name', tournament['id'])
                        tournament['player_count'] = '?'
                        tournament['status'] = 'unknown'
                        tournament['created_date'] = 0
                        tournament['event_location'] = ''
                    
                    available_tournaments.append(tournament)
                    
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "rate limit" in error_str.lower():
                        logging.warning(f"Rate limited while fetching tournament {tournament.get('id')}, adding with basic info")
                    else:
                        logging.warning(f"Could not get details for tournament {tournament.get('id')}: {e}")
                    
                    # Add tournament with basic info as fallback
                    tournament['display_name'] = tournament.get('name', tournament['id'])
                    tournament['player_count'] = '?'
                    tournament['status'] = 'unknown'
                    tournament['created_date'] = 0
                    tournament['event_location'] = ''
                    available_tournaments.append(tournament)
        
        # Sort by most recent tournaments first
        # Priority: scheduled start time (if available), then creation time, then as fallback
        def sort_key(tournament):
            # Use scheduled start time if available (upcoming tournaments first)
            start_time = tournament.get('start_time') or 0
            created_time = tournament.get('created_date') or 0
            
            # Ensure we have numeric values
            try:
                start_time = float(start_time) if start_time else 0
                created_time = float(created_time) if created_time else 0
                current_time = time.time() * 1000
            except (ValueError, TypeError):
                return (2, 0)  # Fallback for invalid data
            
            # For upcoming scheduled tournaments, use negative start time to sort them first
            if start_time > current_time:  # Future tournament
                return (0, -start_time)  # 0 = highest priority, negative to sort by closest first
            elif created_time > 0:
                return (1, -created_time)  # 1 = second priority, most recent creation first
            else:
                return (2, 0)  # 2 = lowest priority for tournaments without dates
        
        available_tournaments.sort(key=sort_key)
        
        # Return the latest 15 tournaments to give good selection
        return available_tournaments[:15]
        
    except Exception as e:
        logging.error(f"Error fetching tournaments: {e}")
        return []


def save_event_config(event_data):
    """Save event configuration to event.json"""
    try:
        config_path = Path("event.json")
        with open(config_path, 'w') as f:
            json.dump(event_data, f, indent=2)
        return True, "Configuration saved successfully"
    except Exception as e:
        return False, f"Error saving configuration: {str(e)}"


def save_secrets_config(secrets_data):
    """Save secrets configuration to .secrets.json"""
    try:
        # Create a clean dict with only serializable data
        clean_secrets = {}
        
        # Copy only the actual configuration keys, not Dynaconf metadata
        for key, value in secrets_data.items():
            if not key.startswith('_') and not hasattr(value, '__call__'):
                # Convert any nested objects to basic dict/list/str/int types
                if hasattr(value, 'to_dict'):
                    clean_secrets[key] = value.to_dict()
                elif isinstance(value, dict):
                    clean_secrets[key] = dict(value)
                else:
                    clean_secrets[key] = value
        
        config_path = Path(".secrets.json")
        with open(config_path, 'w') as f:
            json.dump(clean_secrets, f, indent=2)
        return True, "Secrets saved successfully"
    except Exception as e:
        return False, f"Error saving secrets: {str(e)}"


@setup_wizard.route("/")
def wizard_start():
    """Setup wizard landing page"""
    # Check if already configured
    if settings.get('event_name') and settings.get('tournament_keys'):
        configured = True
    else:
        configured = False
    
    return ac_render_template(
        "setup_wizard/start.html", 
        title="Setup Wizard",
        configured=configured
    )


@setup_wizard.route("/credentials", methods=["GET", "POST"])
def wizard_credentials():
    """Step 1: Configure TrueFinals credentials"""
    if request.method == "POST":
        user_id = request.form.get('truefinals_user_id', '').strip()
        api_key = request.form.get('truefinals_api_key', '').strip()
        
        if not user_id or not api_key:
            flash("Both User ID and API Key are required", "error")
            return ac_render_template("setup_wizard/credentials.html", title="Setup Credentials")
        
        # Read current secrets file directly to avoid Dynaconf metadata
        try:
            with open('.secrets.json', 'r') as f:
                current_secrets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            current_secrets = {}
        
        current_secrets['truefinals'] = {
            'user_id': user_id,
            'api_key': api_key
        }
        
        success, message = save_secrets_config(current_secrets)
        if success:
            flash("Credentials saved successfully", "success")
            return redirect(url_for('setup_wizard.wizard_event'))
        else:
            flash(f"Error saving credentials: {message}", "error")
    
    return ac_render_template(
        "setup_wizard/credentials.html", 
        title="Setup Credentials",
        current_user_id=secrets.truefinals.get('user_id', ''),
        current_api_key=secrets.truefinals.get('api_key', '')
    )


@setup_wizard.route("/event", methods=["GET", "POST"])
def wizard_event():
    """Step 2: Configure event details"""
    if request.method == "POST":
        event_name = request.form.get('event_name', '').strip()
        event_league = request.form.get('event_league', '').strip()
        event_date = request.form.get('event_date', '').strip()
        match_duration = request.form.get('match_duration', '150')
        countdown_duration = request.form.get('countdown_duration', '3')
        cage_count = request.form.get('cage_count', '1')
        
        if not event_name:
            flash("Event name is required", "error")
            return ac_render_template(
                "setup_wizard/event.html", 
                title="Event Setup",
                current_event_name=settings.get('event_name', ''),
                current_event_league=settings.get('event_league', ''),
                current_match_duration=settings.get('match_duration', 150),
                current_countdown_duration=settings.get('countdown_duration', 3)
            )
        
        # Store event info in session for use in next step
        from flask import session
        session['event_info'] = {
            'event_name': event_name,
            'event_league': event_league,
            'event_date': event_date,
            'match_duration': int(match_duration),
            'countdown_duration': int(countdown_duration),
            'cage_count': int(cage_count)
        }
        
        return redirect(url_for('setup_wizard.wizard_tournaments'))
    
    return ac_render_template(
        "setup_wizard/event.html", 
        title="Event Setup",
        current_event_name=settings.get('event_name', ''),
        current_event_league=settings.get('event_league', ''),
        current_match_duration=settings.get('match_duration', 150),
        current_countdown_duration=settings.get('countdown_duration', 3)
    )


@setup_wizard.route("/tournaments", methods=["GET", "POST"])
def wizard_tournaments():
    """Step 3: Select tournaments for this event"""
    # Test connection first
    connected, message = test_truefinals_connection()
    if not connected:
        flash(f"TrueFinals connection failed: {message}", "error")
        return redirect(url_for('setup_wizard.wizard_credentials'))
    
    # Check if we have event info from previous step
    from flask import session
    event_info = session.get('event_info')
    if not event_info:
        flash("Please complete event setup first", "error")
        return redirect(url_for('setup_wizard.wizard_event'))
    
    if request.method == "POST":
        selected_tournaments = []
        
        # Debug: Log all form data
        logging.info(f"Tournament selection form data: {dict(request.form)}")
        
        # Process form data
        for key in request.form.keys():
            if key.startswith('tournament_'):
                tournament_id = key.replace('tournament_', '')
                weightclass = request.form.get(f'weightclass_{tournament_id}', '').strip()
                weight_grams = request.form.get(f'weight_{tournament_id}', '').strip()
                
                # More lenient processing - allow tournaments with missing weight info
                if weightclass or weight_grams:
                    try:
                        weight_int = int(weight_grams) if weight_grams else 0
                        weightclass = weightclass if weightclass else f"Tournament {tournament_id}"
                        
                        selected_tournaments.append({
                            'id': tournament_id,
                            'weightclass': weightclass,
                            'weightInt': weight_int,
                            'tourn_type': 'truefinals'
                        })
                        logging.info(f"Selected tournament: {tournament_id} - {weightclass} ({weight_int}g)")
                    except ValueError:
                        flash(f"Invalid weight value for {weightclass}, using 0", "warning")
                        selected_tournaments.append({
                            'id': tournament_id,
                            'weightclass': weightclass if weightclass else f"Tournament {tournament_id}",
                            'weightInt': 0,
                            'tourn_type': 'truefinals'
                        })
                else:
                    # Tournament is checked but no details filled - add with defaults
                    selected_tournaments.append({
                        'id': tournament_id,
                        'weightclass': f"Tournament {tournament_id}",
                        'weightInt': 0,
                        'tourn_type': 'truefinals'
                    })
                    logging.info(f"Selected tournament with defaults: {tournament_id}")
        
        if not selected_tournaments:
            flash("Please select at least one tournament", "error")
            logging.warning("No tournaments selected - user needs to check checkboxes and fill weight info")
        else:
            # Store selected tournaments in session
            session['selected_tournaments'] = selected_tournaments
            logging.info(f"Successfully selected {len(selected_tournaments)} tournaments")
            return redirect(url_for('setup_wizard.wizard_confirm'))
    
    # Get available tournaments
    tournaments = get_available_tournaments()
    
    return ac_render_template(
        "setup_wizard/tournaments.html", 
        title="Select Tournaments",
        tournaments=tournaments,
        event_info=event_info
    )


@setup_wizard.route("/confirm", methods=["GET", "POST"])
def wizard_confirm():
    """Step 4: Confirm all settings and save"""
    from flask import session
    
    event_info = session.get('event_info')
    selected_tournaments = session.get('selected_tournaments')
    
    if not event_info or not selected_tournaments:
        flash("Missing configuration data. Please start over.", "error")
        return redirect(url_for('setup_wizard.wizard_event'))
    
    if request.method == "POST":
        # Generate cages based on cage_count from event_info
        cages = []
        cage_count = event_info.get('cage_count', 1)
        
        for i in range(1, cage_count + 1):
            cage_name = request.form.get(f'cage_name_{i}', f'Arena {i}').strip()
            if cage_name:
                cages.append({
                    'name': cage_name,
                    'id': i
                })
        
        # Build final configuration
        event_config = {
            'event_name': event_info['event_name'],
            'event_league': event_info['event_league'],
            'event_date': event_info.get('event_date', ''),
            'match_duration': event_info['match_duration'],
            'countdown_duration': event_info['countdown_duration'],
            'tournament_keys': selected_tournaments,
            'tournament_cages': cages
        }
        
        # Save configuration
        success, message = save_event_config(event_config)
        if success:
            flash("Event configuration saved successfully!", "success")
            # Clear session data
            session.pop('event_info', None)
            session.pop('selected_tournaments', None)
            return redirect(url_for('setup_wizard.wizard_complete'))
        else:
            flash(f"Error saving configuration: {message}", "error")
    
    return ac_render_template(
        "setup_wizard/confirm.html", 
        title="Confirm Configuration",
        event_info=event_info,
        selected_tournaments=selected_tournaments
    )


@setup_wizard.route("/complete")
def wizard_complete():
    """Setup complete page"""
    return ac_render_template(
        "setup_wizard/complete.html", 
        title="Setup Complete"
    )


@setup_wizard.route("/api/test-connection")
def api_test_connection():
    """API endpoint to test TrueFinals connection"""
    connected, message = test_truefinals_connection()
    return jsonify({
        'success': connected,
        'message': message
    })


@setup_wizard.route("/api/tournaments")
def api_get_tournaments():
    """API endpoint to get available tournaments"""
    tournaments = get_available_tournaments()
    return jsonify({
        'success': len(tournaments) > 0,
        'tournaments': tournaments
    })


@setup_wizard.route("/api/debug-tournament/<tournament_id>")
def api_debug_tournament(tournament_id):
    """Debug specific tournament"""
    try:
        # Test direct API call
        details_data = getEventInformation(tournament_id)
        
        # Also test if it appears in user tournaments
        user_tournaments_data = getUserTournaments()
        user_tournaments = user_tournaments_data[0].get('response', []) if user_tournaments_data else []
        
        found_in_user_list = None
        for t in user_tournaments:
            if t.get('id') == tournament_id:
                found_in_user_list = t
                break
        
        return jsonify({
            'tournament_id': tournament_id,
            'details_data': details_data,
            'found_in_user_list': found_in_user_list,
            'user_tournaments_count': len(user_tournaments)
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'tournament_id': tournament_id
        })