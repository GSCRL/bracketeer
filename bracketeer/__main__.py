import json
import logging

from flask import Flask, jsonify, request
from flask_socketio import SocketIO

from bracketeer.debug.debug import debug_pages
from bracketeer.matches.match_results import _json_api_stub, match_results
from bracketeer.screens.user_screens import user_screens
from bracketeer.setup_wizard import setup_wizard
from bracketeer.util.wrappers import ac_render_template
from bracketeer.utils import runtime_err_warn

logging.basicConfig(level="INFO")

current_clients = {}

app = Flask(__name__, static_folder="static", template_folder="templates")

app.register_blueprint(user_screens, url_prefix="/screens")
app.register_blueprint(match_results, url_prefix="/matches")
app.register_blueprint(debug_pages, url_prefix="/debug")
app.register_blueprint(setup_wizard, url_prefix="/setup")

app.config["SECRET_KEY"] = "secret secret key (required)!"
socketio = SocketIO(app)

# Initialize SocketIO handlers
from bracketeer.util.wrappers import SocketIOHandlerConstruction

SocketIOHandlerConstruction(socketio)


@app.route("/")
def index():
    from bracketeer.config import settings
    from bracketeer.api_truefinals.cached_api import getTournamentDetails
    
    # Get basic event configuration
    event_config = {
        'name': settings.get('event_name', 'No Event Configured'),
        'league': settings.get('event_league', 'Unknown League'),
        'date': settings.get('event_date', 'Date not set'),
        'match_duration': settings.get('match_duration', 150),
        'countdown_duration': settings.get('countdown_duration', 3),
        'tournaments': [],
        'cages': settings.get('tournament_cages', [])
    }
    
    # Enhance tournament data with actual names from API
    tournament_keys = settings.get('tournament_keys', [])
    for tournament in tournament_keys:
        enhanced_tournament = tournament.copy()
        
        # Try to get the real tournament title from TrueFinals API
        if tournament.get('tourn_type') == 'truefinals':
            try:
                tournament_details = getTournamentDetails(tournament['id'])
                
                if tournament_details:
                    # Handle the cached API response format
                    if isinstance(tournament_details, list) and len(tournament_details) > 0:
                        cache_entry = tournament_details[0]
                        # Extract the actual API response from the cache structure
                        api_data = cache_entry.get('response', cache_entry)
                    elif isinstance(tournament_details, dict):
                        api_data = tournament_details.get('response', tournament_details)
                    else:
                        api_data = None
                    
                    if api_data and isinstance(api_data, dict):
                        # Try different possible field names for tournament name
                        name_fields = ['title', 'name', 'tournamentName', 'event_name']
                        tournament_name = None
                        
                        for field in name_fields:
                            if field in api_data:
                                tournament_name = api_data[field]
                                break
                        
                        if tournament_name:
                            enhanced_tournament['display_name'] = tournament_name
                        else:
                            enhanced_tournament['display_name'] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
                    else:
                        enhanced_tournament['display_name'] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
                else:
                    enhanced_tournament['display_name'] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
            except Exception as e:
                # Fallback to weightclass if API call fails
                logging.warning(f"Failed to fetch tournament details for {tournament['id']}: {e}")
                enhanced_tournament['display_name'] = tournament.get('weightclass', f'Tournament {tournament["id"][:8]}')
        else:
            # For non-TrueFinals tournaments, use weightclass
            enhanced_tournament['display_name'] = tournament.get('weightclass', f'Tournament {tournament["id"]}')
        
        event_config['tournaments'].append(enhanced_tournament)
    
    return ac_render_template("homepage.html", title="Landing Page", event_config=event_config)


@app.route("/control/<int:cageID>")
def realTimer(cageID):
    return ac_render_template(
        "ctimer.html",
        user_screens=user_screens,
        title="Controller",
        cageID=cageID,
    )


@app.route("/settings", methods=("GET", "POST"))
@runtime_err_warn
def generateSettingsPage():
    if request.method == "GET":
        return ac_render_template(
            "app_settings.html",
        )
    elif request.method == "POST":
        from flask import flash, redirect, url_for

        from bracketeer.setup_wizard import save_secrets_config
        
        # Handle TrueFinals credentials update
        user_id = request.form.get('truefinals_user_id', '').strip()
        api_key = request.form.get('truefinals_api_key', '').strip()
        
        if user_id and api_key:
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
                flash("TrueFinals credentials updated successfully", "success")
            else:
                flash(f"Error saving credentials: {message}", "error")
        
        return redirect(url_for('generateSettingsPage'))


@app.route("/debug/requests")
def _debug_requests():
    from api_truefinals.cached_api import TrueFinalsAPICache

    return jsonify(
        TrueFinalsAPICache.select()
        .order_by(TrueFinalsAPICache.last_requested)
        .limit(100)
        .output(load_json=True)
        .run_sync(),
    )


@app.route("/clients", methods=("GET", "POST"))
def _temp_clients_page():
    return jsonify(current_clients)


@app.route("/matches.json")
def _debug_route_matches():
    return jsonify(_json_api_stub()._matches)


@app.errorhandler(500)
def internal_error(error):
    autoreload = request.args.get("autoreload")
    return ac_render_template(
        "base.html",
        autoreload=autoreload,
        errormsg="Sorry, this page has produced an error while generating.  Please try again in 30s.",
    )


logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

socketio.run(app, host="0.0.0.0", port=80, debug=True, allow_unsafe_werkzeug=True)
