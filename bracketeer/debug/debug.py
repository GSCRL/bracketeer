from flask import Blueprint, jsonify

from bracketeer.config import settings
from bracketeer.matches.match_results import _json_api_stub

debug_pages = Blueprint(
    "debug",
    __name__,
    static_folder="./static",
    template_folder="./templates",
)


@debug_pages.route("/durations.json")
def _match_duration():
    match_dur = 150
    countdown_dur = 3
    if "match_duration" in settings:
        match_dur = settings["match_duration"]
    if "countdown_duration" in settings:
        countdown_dur = settings["countdown_duration"]
    return jsonify({"countdown_duration": countdown_dur, "match_duration": match_dur})


@debug_pages.route("/truefinals_requests")
def _debug_requests():
    from api_truefinals.cached_api import TrueFinalsAPICache

    return jsonify(
        TrueFinalsAPICache.select()
        .order_by(TrueFinalsAPICache.last_requested)
        .limit(100)
        .output(load_json=True)
        .run_sync(),
    )


# This fails if there's no API keys present.
# Need to work on better error handling / exposure.
@debug_pages.route("/matches.json")
def _debug_route_matches():
    return jsonify(_json_api_stub()._matches)
