import logging

from flask import render_template

from bracketeer.config import secrets as arena_secrets
from bracketeer.config import settings as arena_settings


def ac_render_template(template: str, **kwargs):
    # print(*args, **kwargs)
    # We inject the arena templates so that we don't need to manually pass them around.
    return render_template(
        template,
        arena_secrets=arena_secrets,
        arena_settings=arena_settings,
        **kwargs,
    )


from flask import render_template, request
from flask_socketio import emit, join_room, rooms
from piccolo.columns import JSON, UUID, Text
from piccolo.engine.sqlite import SQLiteEngine
from piccolo.table import Table

bracketeer_clients = SQLiteEngine(path="bracketeer_clients.sqlite")


# This is used to handle message registration in a "mutable" way, since
#  it's returned to the global state as an object.  The decorators still
#  work async as intended I *believe* and it's very unlikely to have
# anything race.


class BracketeerClients(Table, db=bracketeer_clients):
    id = UUID(primary_key=True)
    sid = Text()
    information = JSON()


BracketeerClients.create_table(if_not_exists=True).run_sync()


class SocketIOHandlerConstruction:
    def __init__(self, socketio):
        @socketio.on("disconnect")
        def disconnect_handler():
            logging.info(f"🔌 DISCONNECT: SID={request.sid}")

        @socketio.on("client_attests_existence")
        def _handle_attestation(location):
            pass

        @socketio.on("client_notify_schedule")
        def _handle_notif_schedule(location):
            join_room("schedule_update")

        @socketio.on("client_requests_schedule")
        def _handle_schedule_upd():
            pass

        # Wrapper to take note of clients as they connect/reconnect to store in above so we can keep track of their current page.
        @socketio.on("exists")
        def state_client_exists():
            logging.info(f"🌟 CLIENT_EXISTS: SID={request.sid}")
            find_resp = (
                BracketeerClients.select()
                .where(BracketeerClients.sid == request.sid)
                .output(load_json=True)
            ).run_sync()

            if len(find_resp) == 0:
                BracketeerClients.insert(
                    BracketeerClients(sid=request.sid, information=request),
                ).run_sync()
                logging.info(f"📝 New client registered: SID={request.sid}")

            emit("arena_query_location", to=request.sid)
            logging.info(f"📍 Sent arena_query_location to SID={request.sid}")

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
                "timer_event",
                timer_message["message"],
                to=f"cage_no_{timer_message['cageID']}",
            )

        @socketio.on("timer_bg_event")
        def handle_message(timer_bg_data):
            emit(
                "timer_bg_event",
                timer_bg_data,
                to=f"cage_no_{timer_bg_data['cageID']}",
            )

        @socketio.on("join_cage_request")
        def join_cage_handler(request_data: dict):
            logging.info(f"🔗 JOIN_CAGE_REQUEST: SID={request.sid}, data={request_data}")
            if "cage_id" in request_data:
                room_name = f'cage_no_{request_data["cage_id"]}'
                join_room(room_name)
                emit(
                    "client_joined_room",
                    room_name,
                    to=room_name,
                )
                logging.info(
                    f"✅ User SID ({request.sid}) joined room '{room_name}'. Current rooms: {rooms()}",
                )
            else:
                logging.warning(f"❌ JOIN_CAGE_REQUEST missing cage_id: {request_data}")

        @socketio.on("player_ready")
        def handle_message(ready_msg: dict):
            logging.info(f"🎮 PLAYER_READY: SID={request.sid}, data={ready_msg}")
            logging.info(f"📍 Current user rooms: {rooms()}")
            
            if 'cageID' in ready_msg:
                target_room = f"cage_no_{ready_msg['cageID']}"
                logging.info(f"📡 Broadcasting 'control_player_ready_event' to room '{target_room}'")
                emit(
                    "control_player_ready_event",
                    ready_msg,
                    to=target_room,
                )
                logging.info(f"✅ PLAYER_READY broadcast complete")
            else:
                logging.warning(f"❌ PLAYER_READY missing cageID: {ready_msg}")

        @socketio.on("player_tapout")
        def handle_message(tapout_msg: dict):
            logging.info(
                f"player_tapout, {tapout_msg} for room {[ctl_rooms for ctl_rooms in rooms()]}",
            )
            emit(
                "control_player_tapout_event",
                tapout_msg,
                to=f"cage_no_{tapout_msg['cageID']}",
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
