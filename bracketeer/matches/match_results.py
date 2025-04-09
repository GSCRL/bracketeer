from flask import Blueprint, jsonify, render_template, request

from src.api_truefinals.cached_wrapper import getAllTournamentsMatchesWithPlayers
from src.util.wrappers import ac_render_template

match_results = Blueprint(
    "match_results", __name__, static_folder="./static", template_folder="./templates"
)


class reversor:
    def __init__(self, obj):
        self.obj = obj

    def __eq__(self, other):
        return other.obj == self.obj

    def __lt__(self, other):
        return other.obj < self.obj


def filtering_func(x):
    # print(x)
    if "state" in x:
        return x["state"] in ["called", "ready", "active"]
    return False


def _json_api_stub():
    matches = getAllTournamentsMatchesWithPlayers(filterFunction=filtering_func)
    # import json

    # with open("matches_with_plauers.json",'w') as outy:
    #    outy.write(json.dumps(matches, indent=4))
    # matches = [m for m in matches if m["state"] in ]

    matches = sorted(
        matches,
        key=lambda x: (
            x["calledSince"] or float(0),
            reversor(x["state"] == "unavailable"),
        ),
        reverse=False,
    )

    return matches


@match_results.route("/upcoming.json")
def _json_api_results():
    matches = _json_api_stub()

    return jsonify(matches)


@match_results.route("/upcoming")
def routeForUpcomingMatches():
    autoreload = request.args.get("autoreload")
    show_header = request.args.get("show_header")

    matches = _json_api_stub()

    return ac_render_template(
        "queueing/upcoming_matches.html",
        div_matches=matches,
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


@match_results.errorhandler(500)
def internal_error(error):
    autoreload = request.args.get("autoreload")
    return render_template(
        "base.html",
        autoreload=autoreload,
        errormsg="Sorry, this page has produced an error while generating.  Please try again in 30s.",
    )
