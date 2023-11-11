import logging

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room, rooms

from matches.match_results import _json_api_stub, match_results
from screens.user_screens import user_screens
from util.wrappers import ac_render_template

logging.basicConfig(level="INFO")

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

current_clients = {}

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///combat_robot_event.db"
db.init_app(app)

with app.app_context():
    db.create_all()

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


@socketio.on("disconnect")
def disconnect_handler():
    if request.sid in current_clients:
        del current_clients[request.sid]
        print("Client removed via disconnection.")


@socketio.on("client_attests_existence")
def _handle_attestation(location):
    current_clients[request.sid] = (
        request.remote_addr,
        request.url,
        location["location"],
    )


@socketio.on("client_notify_schedule")
def _handle_notif_schedule(location):
    join_room("schedule_update")


@socketio.on("client_requests_schedule")
def _handle_schedule_upd():
    data = _json_api_stub()
    emit(
        "schedule_data",
        render_template("_partial_template_matches.html", data=data),
        to="schedule_update",
    )


# Wrapper to take note of clients as they connect/reconnect to store in above so we can keep track of their current page.
@socketio.on("exists")
def state_client_exists():
    if request.sid not in current_clients:
        current_clients[request.sid] = (request.remote_addr, request.url)
        print(f"SID {request.sid} added to global store (IP is {request.remote_addr})")
        emit("arena_query_location", to=request.sid)


# Unfortunately not globally used yet, do not trust as a safety system yet.
@socketio.on("globalESTOP")
def global_safety_eSTOP():
    valid_rooms = [ctl_rooms for ctl_rooms in rooms()]
    for v in valid_rooms:
        emit("timer_event", "STOP", to=v)
        emit("timer_bg_event", {"color": "red", "cageID": 999}, to=v)


# Old global handler, should probably be moved to globally accessible timer area.
@socketio.on("timer_event")
def handle_message(timer_message):
    print(timer_message)
    emit(
        "timer_event", timer_message["message"], to=f"cage_no_{timer_message['cageID']}"
    )


@socketio.on("timer_bg_event")
def handle_message(timer_bg_data):
    emit("timer_bg_event", timer_bg_data, to=f"cage_no_{timer_bg_data['cageID']}")


@socketio.on("join_cage_request")
def join_cage_handler(request_data: dict):
    if "cage_id" in request_data:
        join_room(f'cage_no_{request_data["cage_id"]}')
        emit(
            "client_joined_room",
            f'cage_no_{request_data["cage_id"]}',
            to=f"cage_no_{request_data['cage_id']}",
        )
        logging.info(
            f"User SID ({request.sid}) has joined Cage #{request_data['cage_id']}"
        )


@socketio.on("player_ready")
def handle_message(ready_msg: dict):
    logging.info(
        f"player_ready, {ready_msg} for room {[ctl_rooms for ctl_rooms in rooms()]}"
    )
    logging.info(ready_msg)
    emit("control_player_ready_event", ready_msg, to=f"cage_no_{ready_msg['cageID']}")


@socketio.on("player_tapout")
def handle_message(tapout_msg: dict):
    logging.info(
        f"player_tapout, {tapout_msg} for room {[ctl_rooms for ctl_rooms in rooms()]}"
    )
    emit(
        "control_player_tapout_event", tapout_msg, to=f"cage_no_{tapout_msg['cageID']}"
    )


# This takes in the message sent out from ctimer.html and re-broadcasts it to the room as two messages, etc.
@socketio.on("robot_match_color_name")
def _handler_colors(cageID, red_name, blue_name):
    emit("robot_match_share_name", ["red", red_name], to=f"cage_no_{cageID}")
    emit("robot_match_share_name", ["blue", blue_name], to=f"cage_no_{cageID}")


@socketio.on("c_play_sound_event")
def _handle_sound_playback(input_struct):
    emit(
        "play_sound_event",
        input_struct["sound"],
        to=f"cage_no_{input_struct['cageID']}",
    )


@socketio.on("reset_screen_states")
def handle_message(reset_data):
    emit("reset_screen_states", to=f"cage_no_{reset_data['cageID']}")


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
