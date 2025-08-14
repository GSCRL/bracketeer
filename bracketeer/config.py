import logging
from pathlib import Path

from dynaconf import Dynaconf

# We should prefer secrets explicitly specified by flag, then in pwd, and finally by default.
# This is unfinished, but works decently as-is.  Wait for Rick's changes back to include
# any uv fixes before resolving path inconsistencies.

if (Path.cwd() / ".secrets.json").exists():
    secrets = Dynaconf(envvar_prefix="DYNACONF", settings_files=[Path(".secrets.json")])

if (Path.cwd() / "event.json").exists():
    settings = Dynaconf(envvar_prefix="DYNACONF", settings_files=[Path("event.json")])


def mandateConfig():
    logging.info("Running initial configuration assertion.")

    if "match_duration" not in settings:
        logging.warning("Match duration was not present, assuming 2m30s.")
        settings["match_duration"] = (
            150.9  # we start at .9 such that the JS antics behave correctly.
        )

    if "tournament_cages" not in settings:
        logging.warning("No event cages / locations set, assuming new event.")
        settings["tournament_cages"] = []

    if "tournament_keys" not in settings:
        logging.warning("No event divisions set, assuming new event.")
        settings["tournament_keys"] = []

    if "event_name" not in settings:
        logging.warning("No event name set, assuming new event with empty name.")
        settings["event_name"] = ""

    if "event_league" not in settings:
        logging.info("No league name set, assuming None.")
        settings["event_league"] = ""  # Empty by default, fine.

    if "truefinals" not in secrets:
        secrets["truefinals"] = {"api_key": "", "user_id": ""}
        logging.warning(
            "TrueFinals API keys not set up.  App will not be able to run upcoming / last matches, or run match results directly.",
        )

    if "robotcombatevents" not in secrets:
        secrets["robotcombatevents"] = {"username": "", "password": ""}
        logging.warning(
            "RCE credentials not provided.  Cannot automate import of brackets.",
        )

    if "obs_ws" not in secrets:
        settings["obs_ws"] = []
        logging.warning(
            "No targets set for OBS Websocket control.  Please specify targets in Settings for this feature to work.",
        )
    else:
        for item in secrets["obs_ws"]:
            if "uri" not in item:
                item["uri"] = ""
                logging.warning(
                    "Empty URI for OBSWS target.  Cannot be used, resetting.",
                )
            if "friendly_name" not in item:
                item["friendly_name"] = ""
            if "token" not in item:
                item["token"] = ""
            if "scene" not in item:
                item["scene"] = ""


mandateConfig()


def getCages():
    if "tournament_cages" not in settings:
        settings["tournament_cages"] = []

    return settings["tournament_cages"]


def addCage(cageName: str = None, cageID: int = None):
    if "tournament_cages" not in settings:
        settings["tournament_cages"] = []

    def _getHighestCage():
        _maximum_cage_id = -1
        for cage in settings["tournament_cages"]:
            if "id" in cage:
                if cage["id"] > _maximum_cage_id:
                    _maximum_cage_id = cage["id"]

        return _maximum_cage_id

    if cageName == None:
        settings["tournament_cages"].append(
            {"name": f"Cage {_getHighestCage()+1}", "id": cageID + 1},
        )
    else:
        settings["tournament_cages"].append({"name": f"{cageName}", "id": cageID + 1})
