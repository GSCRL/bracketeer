import logging

from flask import render_template

from src.config import secrets as arena_secrets
from src.config import settings as arena_settings


def ac_render_template(template: str, **kwargs):
    # print(*args, **kwargs)
    # We inject the arena templates so that we don't need to manually pass them around.
    return render_template(
        template, arena_secrets=arena_secrets, arena_settings=arena_settings, **kwargs
    )


from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room, rooms


class websocket_constructor:
    def __init__(self, socketio):
        @socketio.on("disconnect")
        def disconnect_handler():
            pass

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
            pass

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
                "timer_bg_event", timer_bg_data, to=f"cage_no_{timer_bg_data['cageID']}"
            )

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
            emit(
                "control_player_ready_event",
                ready_msg,
                to=f"cage_no_{ready_msg['cageID']}",
            )

        @socketio.on("player_tapout")
        def handle_message(tapout_msg: dict):
            logging.info(
                f"player_tapout, {tapout_msg} for room {[ctl_rooms for ctl_rooms in rooms()]}"
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
