from pprint import pprint

from api_truefinals.cached_wrapper import getAllTournamentsMatchesSimple

# logging.basicConfig()
# logging.getLogger().setLevel(logging.INFO)

matches_list = getAllTournamentsMatchesSimple()
from api_truefinals.cached_wrapper import getPlayerByIds

output = []

for match in matches_list:
    output.append(
        {
            "match_key": match["id"],
            "tournament_key": match["tournamentID"],
            "players": [
                getPlayerByIds(match["tournamentID"], player["playerID"])
                for player in match["slots"]
            ],
        },
    )

pprint(output)
