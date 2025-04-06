import logging

from httpx import Client

from config import secrets as arena_secrets

challonge_api_session = Client()

# Challonge API is *either* Basic Authentication *or*
# the key and username passed as URLargs per:
# https://api.challonge.com/v1

# Even non-auth requests require a user to sign in.


def makeAPIRequest(endpoint: str) -> list:
    if "challonge" in arena_secrets:
        if "api_key" in arena_secrets["challonge"]:
            api_key = arena_secrets.challonge.api_key
            credentials = {"api_key": api_key}

            headers = {
                "x-api-user-id": credentials["user_id"],
                "x-api-key": credentials["api_key"],
            }

    root_endpoint = """https://api.challonge.com/v1/"""

    logging.info(f"value {endpoint} is not in cache, trying request now!")
    resp = challonge_api_session.get((f"{root_endpoint}{endpoint}"), headers=headers)
    return resp
