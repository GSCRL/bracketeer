import logging

# This was shamelessly copied and may not work
# as intended.  The intent is to move the API
# request workers to the background such that
# they can be polled on more regular intervals
# stored in memory, and then periodically giv-
# en to clients for the most up-to-date match
# behavior without needing to potentially hit
# an error state.
from httpx import Client

from config import secrets as arena_secrets

tf_api_session = Client()
# This caches the items less likely to change (if at all during the
# course of the event.  The field software probably shouldn't be
# called until this is set up finally and tournaments are started.


def makeAPIRequest(endpoint: str) -> list:
    api_key = arena_secrets.truefinals.api_key
    user_id = arena_secrets.truefinals.user_id
    credentials = {"user_id": user_id, "api_key": api_key}

    headers = {
        "x-api-user-id": credentials["user_id"],
        "x-api-key": credentials["api_key"],
    }

    root_endpoint = """https://truefinals.com/api"""

    logging.info(f"value {endpoint} is not in cache, trying request now!")
    resp = tf_api_session.get((f"{root_endpoint}{endpoint}"), headers=headers)
    return resp
