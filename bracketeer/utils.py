from pathlib import Path

from dynaconf import Dynaconf
from flask import flash

secrets = Dynaconf(envvar_prefix="DYNACONF", settings_files=[Path(".secrets.json")])


def runtime_err_warn(func):
    """Decorator that reports the execution time."""

    def wrap(*args, **kwargs):
        # start = time.time()

        if "challonge" not in secrets:
            flash(
                "Challonge tokens / user credentials not provided, requests made with POSTs / that aren't static <i>will</i> fail.<br><br>Use Settings to change.",
            )

        if "truefinals" not in secrets:
            flash(
                "TrueFinals user_id and token not provided, requests to the site <i>will</i> fail.<br><br>Use Settings to change.",
            )

        if "obs_ws" not in secrets:
            flash(
                "No local credentials for OBS WebSockets provided.  This will still allow all operation to continue, but will not attempt to provide control buttons for OBS websockets in the match control pane.",
            )

        result = func(*args, **kwargs)
        # end = time.time()

        # print(func.__name__, end-start)
        return result

    return wrap
