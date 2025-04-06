import logging

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room, rooms

from src.matches.match_results import _json_api_stub, match_results
from src.screens.user_screens import user_screens
from src.util.wrappers import ac_render_template

logging.basicConfig(level="INFO")

app = Flask(__name__, static_folder="src/static", template_folder="src/templates")
socketio = SocketIO(app)

app.register_blueprint(user_screens, url_prefix="/screens")
app.register_blueprint(match_results, url_prefix="/matches")


@app.route("/")
def index():
    return ac_render_template("homepage.html", title="Landing Page")

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
