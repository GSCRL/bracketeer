import logging
from time import time

from bracketeer.api_truefinals.cached_api import (
    TrueFinalsTournamentsPlayers,
    getAllGames,
    getAllPlayersInTournament,
    getEventLocations,
)
from bracketeer.config import settings as arena_settings

# used for player lookup to avoid rebuilding constantly.  Should be faster.


"""
Tournament locations call will return a list if there's more than one location / any is defined.

Location will return [] if there are no locations specified.

"""


def getAllTournamentsLocations():
    output_structure = []

    for tournament_key in arena_settings["tournament_keys"]:
        _current_fk = tournament_key["id"]
        _current_name = tournament_key["weightclass"]

        _current_data = getEventLocations(_current_fk)

        for loc in _current_data[0]["response"]:
            loc["root_tournament_fk"] = _current_fk
            loc["staleness_time"] = _current_data[0]["last_requested"]

            output_structure.append(loc)

    return output_structure


def getAllTournamentsPlayers():
    output_structure = []

    for tournament_key in arena_settings["tournament_keys"]:
        _current_fk = tournament_key["id"]
        _current_name = tournament_key["weightclass"]

        if tournament_key["tourn_type"] == "truefinals":
            _current_data = getAllPlayersInTournament(_current_fk)
        elif tournament_key["tourn_type"] == "challonge":
            pass
            # _current_data = getAllChallongePlayers(_current_fk)

        for loc in _current_data[0]["response"]:
            # print(loc)
            loc["root_tournament_fk"] = _current_fk
            loc["staleness_time"] = _current_data[0]["last_requested"]

            output_structure.append(loc)

    # Reset this so we can re-analyze stuff and sanely interact with the data backed by the cache.
    # for item in output_structure:
    #

    return output_structure


"""
This absurd function takes the contents of the temporary database and uses it to
produce a synthetic proto-view for use in building the dictionary for finding
players quickly and effectively across cross-tournament keys.

This being faster than for loops feels absurd, I agree.
"""


def build_player_dict_via_db_proxy():
    player_id_dict = {}
    start_build = time()

    # If there are no valid players we can use to build this
    # data as they've expired since we got them.
    if (
        len(
            TrueFinalsTournamentsPlayers.select()
            .where(TrueFinalsTournamentsPlayers.last_updated + 3600 > time())
            .output(load_json=True)
            .run_sync()
        )
        == 0
    ):
        TrueFinalsTournamentsPlayers.delete(force=True)
        player_id_dict = {}

        all_tournaments_players = getAllTournamentsPlayers()

        refactor_list = [
            {
                "tournament_id": player_moment["root_tournament_fk"],
                "last_updated": time(),
                "player_data": player_moment,
            }
            for player_moment in all_tournaments_players
        ]

        for i in refactor_list:
            TrueFinalsTournamentsPlayers.insert(
                TrueFinalsTournamentsPlayers(
                    id=i["player_data"]["id"],
                    tournament_id=i["tournament_id"],
                    last_updated=i["last_updated"],
                    player_data=i["player_data"],
                )
            ).run_sync()

    for tournament_player in (
        TrueFinalsTournamentsPlayers.select().output(load_json=True).run_sync()
    ):
        if tournament_player["tournament_id"] not in player_id_dict:
            player_id_dict[tournament_player["tournament_id"]] = {}

        if (
            tournament_player["id"]
            not in player_id_dict[tournament_player["tournament_id"]]
        ):
            player_id_dict[tournament_player["tournament_id"]][
                tournament_player["id"]
            ] = tournament_player

    end_build = time()
    logging.info(f"Player dict build step took {end_build - start_build}s")
    return player_id_dict


def getPlayerByIds(tournamentID: str, playerID: str):
    value = build_player_dict_via_db_proxy()

    if tournamentID in value:
        if playerID in value[tournamentID]:
            return value[tournamentID][playerID]["player_data"]
    # fmt: off
    # This reflects all of the needed keys so we're kept sane-ish.  Yay.
    return {"id": None, "name": "Default Player Information",
            "photoUrl": None,
            "seed": -1,
            "wins": -1,
            "losses": -1,
            "ties": -1,
            "isBye": False,
            "isDisqualified": False,
            "lastPlayTime": 1734297074657,
            "lastBracketGameID": None,
            "placement": 99999999999,
            "profileInfo": None,
            "root_tournament_fk": "",
            "staleness_time": 9999999999999,
        }
    # fmt: on


def getAllTournamentsMatchesWithPlayers(filterFunction=None):
    matches = getAllTournamentsMatchesSimple(filterFunction)

    print(len(matches))
    if filterFunction:
        matches = [x for x in matches if filterFunction(x)]

    for match in matches:
        for player in match["slots"]:
            player["bracketeer_player_data"] = getPlayerByIds(
                match["tournamentID"], player["playerID"]
            )

    return matches


def getAllTournamentsMatchesSimple(filterFunction=None):
    output_structure = []

    for tournament_key in arena_settings["tournament_keys"]:
        _current_fk = tournament_key["id"]
        _current_name = tournament_key["weightclass"]

        _current_data = getAllGames(_current_fk)

        if len(_current_data) == 1:
            print(
                f"Exactly one valid response in API cache for this invocation of get all games for tourney_fk of {_current_fk}."
            )

            for match in list(_current_data[0]["response"]):
                # print(_current_data[0]['response'])
                match["tournamentID"] = _current_fk
                match["weightclass"] = _current_name
                match["staleness_time"] = _current_data[0]["last_requested"]

                output_structure.append(match)

        logging.info(f"num matches before filter: {len(output_structure)}")
        if filterFunction:
            _current_data = [x for x in output_structure if filterFunction(x)]

        logging.info(f"num matches after filter: {len(output_structure)}")

    return output_structure
