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
    return ac_render_template("homepage.html", title="Landing Page")


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
