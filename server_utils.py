from typing import Any, Dict, List
import random
import pprint

from utils import *


def format_log(log: Dict[str, Any], include: str | None = None) -> str:
    time = log.get("time", "?")
    sender = log.get("sender", "?")
    data = log.get("data", "?")
    type = data.get("type", "?")
    response = log.get("response", "?")
    return (
        f"""[{datetime.fromtimestamp(time).strftime("%a %d %b %Y %H:%M:%S")}]\t[{sender}]\t[{type}]\t\n\t[Response]\t{"\n\t\t\t".join(pprint.pformat(response, width=100).split("\n"))}"""
        if include == "-r"
        else f"""[{datetime.fromtimestamp(time).strftime("%a %d %b %Y %H:%M:%S")}]\t[{sender}]\t[{type}]"""
    )


def generate_random_users(user_state: UserStates, num_users: int):
    for _ in range(num_users):
        new_user_name = f"User {_}"
        generate_connexion(user_state, new_user_name)


if __name__ == "__main__":

    random.seed(42)

    adjacent_list = UserStates()
    generate_random_users(adjacent_list, 5)
    print(adjacent_list.adjacent_list)
    adjacent_list.display_matrix()

    adjacent_matrix = adjacent_list.get_adjacent_matrix()

    for i in range(len(adjacent_matrix)):
        for j in range(i + 1):
            assert adjacent_matrix[j][j] == 0
        assert (
            adjacent_matrix[i][i] == 0
        ), f"Erreur : l'utilisateur {adjacent_list.user_names[i]} est connecté à lui-même."
