import logging

# Text type is VarChar without limit, probably fine?
from time import time

from piccolo.columns import JSON, UUID, BigInt, Boolean, Text
from piccolo.engine.sqlite import SQLiteEngine

# ORM Test, ty Devyn.
from piccolo.table import Table

from bracketeer.api_truefinals.api import makeAPIRequest

lru_DB = SQLiteEngine(path="tf_lru.sqlite")

"""
The true ratelimit of TrueFinals is 10 requests in 10 seconds, 
unsure of interval of observation.  However, this neglects the
 reality that the web frontend ALSO counts towards this reque-
 st limit.  
 
As such, our limit is half of the rated one by default, and as 
well is accomodating of the need for some requests that may 
not be done yet, and or still result in rate-limiting.

TrueFinals also returns the rate limit information in headers like so:

X-RateLimit-Limit: Maximum number of requests allowed within a window (10s).
X-RateLimit-Remaining: How many requests the user has left within the current window.
X-RateLimit-Reset: Unix timestamp in milliseconds when the limits are reset.

They are stored below, so we should look for the last response overall to 
validate rate limiting, and remove ones past their expiry most likely, 
rather than keeping them in perpetuity.

"""


def are_rate_limited() -> bool:
    requests_thing = (
        TrueFinalsAPICache.select()
        .where((time() - 10) > TrueFinalsAPICache.last_requested)
        .run_sync()
    )
    if (
        len(requests_thing) >= 5
    ):  # half of calls can be API due to web panel causing headaches.
        return True
    return False


class TrueFinalsAPICache(Table, db=lru_DB):
    id = UUID(primary_key=True)
    response = JSON()
    last_requested = BigInt()
    api_path = Text()
    successful = Boolean()
    resp_code = BigInt()
    resp_headers = JSON()


# This is only used as a persistent cache in the same datastore to avoid headaches.
class TrueFinalsTournamentsPlayers(Table, db=lru_DB):
    pk_id = UUID(primary_key=True)
    tournament_id = Text()
    id = Text()
    last_updated = BigInt()
    player_data = JSON()


# Need to assert that the table exists first, or else it fails horridly.
TrueFinalsAPICache.create_table(if_not_exists=True).run_sync()
TrueFinalsTournamentsPlayers.create_table(if_not_exists=True).run_sync()


def _generate_cache_query(api_endpoint, expiry=60, expired_is_ok=False):
    find_response = (
        TrueFinalsAPICache.select(
            TrueFinalsAPICache.api_path,
            TrueFinalsAPICache.last_requested,
            TrueFinalsAPICache.response,
            TrueFinalsAPICache.resp_code,
        )
        .where(TrueFinalsAPICache.api_path == api_endpoint)
        .where(TrueFinalsAPICache.successful == True)
    )
    if not expired_is_ok:
        find_response = find_response.where(
            (TrueFinalsAPICache.last_requested + expiry > time())
        )

    find_response = (
        find_response.order_by(TrueFinalsAPICache.last_requested, ascending=False)
        .limit(1)
        .output(load_json=True)
    )

    return find_response


def getAPIEndpointRespectfully(api_endpoint: str, expiry=60):
    logging.info(f"expiry is {expiry} while calling {api_endpoint}")

    find_response = _generate_cache_query(api_endpoint, expiry).run_sync()

    # Key is not present.
    if len(find_response) == 0:
        logging.info(f"No valid keys, adding new request for {api_endpoint}")
        # TODO change to enqueue system and run in distinct thread I think?
        # That or a global worker for DB operations to avoid headaches or something.

        query_remote = makeAPIRequest(api_endpoint)
        # print(query_remote.headers)
        insert_query = TrueFinalsAPICache.insert(
            TrueFinalsAPICache(
                response=query_remote.json(),
                successful=(
                    (query_remote.status_code >= 200)
                    and (query_remote.status_code < 500)
                ),
                last_requested=time(),
                api_path=api_endpoint,
                resp_code=query_remote.status_code,
                resp_headers=query_remote.headers,
            )
        ).run_sync()

        TrueFinalsAPICache.update(force=True)
    else:
        logging.info(f"Valid keys found, not requesting {api_endpoint}.")

    find_response = _generate_cache_query(
        api_endpoint=api_endpoint, expiry=expiry
    ).run_sync()

    # last ditch effort of "if we didn't get good data the last
    # invocation, we try to return known stale data we have a
    # copy of."

    if len(find_response) == 0:
        _generate_cache_query(
            api_endpoint=api_endpoint, expiry=expiry, expired_is_ok=True
        ).run_sync()

    return find_response


# Below are the stubs we hope to use to use the above APICache antics we've made.

# They are rough analogues to the original as made in api.py, and should be used
# instead whenever possible, as the originals may be deprecate at any point.  The
# below functions are "synthetic view" functions, where it uses the most up to date
# version of any endpoint, but also tries to get the new result if it doesn't exist.
# If there's truly no version inside of it, we should probably just... block until
# we'll become unblocked I guess.

# That's a long ten seconds.


# Below functions assume you ONLY want the unexpired items.
# This would obviously present a headache for some use cases.
def getEventInformation(tournamentID: str) -> dict:
    return getAPIEndpointRespectfully(f"/v1/tournaments/{tournamentID}")


def getAllGames(tournamentID: str) -> list[dict]:
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/games", expiry=15
    )


def getAllPlayersInTournament(tournamentID: str) -> list[dict]:
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/players", expiry=(5 * 60)
    )


def getEventLocations(tournamentID: str) -> list[dict]:
    return getAPIEndpointRespectfully(
        f"/v1/tournaments/{tournamentID}/locations", expiry=(60 * 60)
    )


# DO NOT USE LIGHTLY.  THIS EMPTIES THE FILE.
def purge_API_Cache(timer_passed=3600):
    # We only care about the last 10 minutes of event match failures I suspect.
    TrueFinalsAPICache.delete().where(
        TrueFinalsAPICache.last_requested + 600 < time()
    ).where(not TrueFinalsAPICache.successful).run_sync()

    # Anything past the last hour we get rid of.
    TrueFinalsAPICache.delete().where(
        (TrueFinalsAPICache.last_requested + timer_passed < time())
    ).run_sync()
