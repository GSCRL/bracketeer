import logging

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room, rooms

from matches.match_results import _json_api_stub, match_results
from screens.user_screens import user_screens
from util.wrappers import ac_render_template

logging.basicConfig(level="INFO")

current_clients = {}

app = Flask(__name__, static_folder="static", template_folder="templates")

app.register_blueprint(user_screens, url_prefix="/screens")
app.register_blueprint(match_results, url_prefix="/matches")

app.config["SECRET_KEY"] = "secret secret key (required)!"
socketio = SocketIO(app)


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


from utils import runtime_err_warn


@app.route("/settings", methods=("GET", "POST"))
@runtime_err_warn
def generateSettingsPage():
    if request.method == "GET":
        return ac_render_template(
            "app_settings.html",
        )


@app.route("/debug/requests")
def _debug_requests():
    from api_truefinals.cached_api import TrueFinalsAPICache

    return jsonify(
        TrueFinalsAPICache.select()
        .order_by(TrueFinalsAPICache.last_requested)
        .limit(100)
        .output(load_json=True)
        .run_sync()
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

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
