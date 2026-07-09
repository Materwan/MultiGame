from typing import Any, Dict, List, Callable
import random
from datetime import datetime
import time

DEFAULT_CPU = 10
DEFAULT_RAM = 10
DEFAULT_RESOURCES = {"CPU": DEFAULT_CPU, "RAM": DEFAULT_RAM}
DEFAULT_DEPTH_VISIBILITY = 1
MAX_NEIGHBORS = 5


class UserStates:

    def __init__(self, self_name: str | None = None):

        self.self_name = self_name

        self.user_names: List[str] = []
        self.nb_connection: List[int] = []
        self.adjacent_list: List[List[int]] = []
        self.resources: List[Dict[str, Any]] = []
        self._depth_visibility: List[int] = []

    def get_neighbors(self, user_name: str | None = None) -> List[str]:
        """Renvoie les voisins d'un utilisateur, ainsi que leur ressources, ou de lui-même si None."""
        if not user_name:
            user_name = self.self_name
        if user_name in self.user_names:
            user_index = self.user_names.index(user_name)
            neighbor_indices = self.adjacent_list[user_index]
            return [self.user_names[i] for i in neighbor_indices]
        else:
            return []

    def get_ressources(self, user_name: str | None = None) -> Dict[str, Any]:
        """Renvoie les ressources d'un utilisateur, ou de lui-même si None."""
        if not user_name:
            user_name = self.self_name
        if user_name in self.user_names:
            user_index = self.user_names.index(user_name)
            return self.resources[user_index]
        else:
            return {}

    def get_resources(self, user_name: str | None = None) -> Dict[str, Any]:
        """Alias anglais de get_ressources pour compatibilité avec le reste du code."""
        return self.get_ressources(user_name)

    def get_all_data_depth(
        self, user_name: str, depth: int = 1
    ) -> Dict[str, Dict[str, Any]]:

        if user_name not in self.user_names:
            return {}

        return_value = {}
        stack = [(None, 0, user_name)]

        while len(stack) > 0:

            origin, curr_depth, curr_name = stack.pop()
            curr_neighbors = self.get_neighbors(curr_name)

            if curr_name not in return_value:

                return_value[curr_name] = {
                    "neighbors": (curr_neighbors if curr_depth < depth else [origin]),
                    "resources": self.get_resources(curr_name),
                }

            else:

                to_add = curr_neighbors if curr_depth < depth else [origin]

                for t_name in return_value[curr_name]["neighbors"]:
                    if t_name in to_add:
                        to_add.remove(t_name)

                return_value[curr_name]["neighbors"] = (
                    return_value[curr_name]["neighbors"] + to_add
                )

            if curr_depth < depth:

                for t_name in curr_neighbors:
                    stack.append((curr_name, curr_depth + 1, t_name))

        return return_value

    def get_adjacent_matrix(self) -> List[List[int]]:
        size = len(self.user_names)
        matrix = [[0] * size for _ in range(size)]
        for i, adjacents in enumerate(self.adjacent_list):
            for j in adjacents:
                matrix[i][j] = 1
        return matrix

    def _get_visibility_depth(self, user_name: str):
        return (
            self._depth_visibility[self.user_names.index(user_name)]
            if len(self._depth_visibility) > 0
            else DEFAULT_DEPTH_VISIBILITY
        )

    def get_visible_to(self, user_name: str, without: str | None = None) -> List[str]:
        """Donne la liste des noeuds visibles pour un noeud.
        without définit un noeud qui ne sera pas pris en compte dans le calcule de visibilité.
        """

        visible = []
        to_visit = [
            (name, 1) for name in self.get_neighbors(user_name) if name != without
        ]

        while len(to_visit) > 0:

            curr_name, curr_depth = to_visit.pop(0)
            visible.append(curr_name)

            if curr_depth < self._get_visibility_depth(curr_name):

                for curr_neighbor in self.get_neighbors(curr_name):

                    if curr_neighbor != without:
                        to_visit.append((curr_neighbor, curr_depth + 1))

        return visible

    def get_disponible_neighbors_index(self) -> List[int]:

        return [
            index
            for index, value in enumerate(self.nb_connection)
            if value < MAX_NEIGHBORS
        ]

    def add_user(
        self,
        user_name: str,
        neighbors: List[str],
        resources: Dict[str, Any],
        depth_visibility: int | None = None,
    ):
        """Rajoute un utilisateur au réseau."""
        user_index = len(self.user_names)
        self.user_names.append(user_name)
        self.adjacent_list.append([self.user_names.index(n) for n in neighbors])
        for index in range(len(self.user_names) - 1):
            if self.user_names[index] in neighbors:
                self.adjacent_list[index].append(user_index)
                self.nb_connection[index] += 1
        self.resources.append(resources)
        self.nb_connection.append(len(neighbors))
        self._depth_visibility.append(depth_visibility)

    def add_multiple_users(
        self,
        user_names: List[str],
        neighbors: List[List[str]],
        resources: List[Dict[str, Any]],
    ):
        base_index = len(self.user_names)
        self.user_names.extend(user_names)
        self.resources.extend(resources)
        self.adjacent_list.extend([[] for _ in range(len(user_names))])

        for index, user_neighbors in enumerate(neighbors):
            user_index = base_index + index
            resolved_neighbors = []
            for neighbor_name in user_neighbors:
                if neighbor_name in self.user_names:
                    resolved_neighbors.append(self.user_names.index(neighbor_name))
            self.adjacent_list[user_index] = resolved_neighbors

            for neighbor_name in user_neighbors:
                if neighbor_name in self.user_names:
                    neighbor_index = self.user_names.index(neighbor_name)
                    if user_index not in self.adjacent_list[neighbor_index]:
                        self.adjacent_list[neighbor_index].append(user_index)

    def update_user(
        self, user_name: str, neighbors: List[str], resources: Dict[str, Any]
    ):
        """Met à jour un utilisateur du réseau."""
        user_index = self.user_names.index(user_name)
        self.adjacent_list[user_index] = [self.user_names.index(n) for n in neighbors]
        for index in range(len(self.user_names)):
            if index != user_index:
                if self.user_names[index] in neighbors:
                    if user_index not in self.adjacent_list[index]:
                        self.adjacent_list[index].append(user_index)
                elif user_index in self.adjacent_list[index]:
                    self.adjacent_list[index].remove(user_index)
        self.resources[user_index] = resources

    def remove_user(self, user_name: str):
        """Supprime un utilisateur du réseau."""
        if user_name in self.user_names:
            user_index = self.user_names.index(user_name)
            for index in self.adjacent_list[user_index]:
                if user_index in self.adjacent_list[index]:
                    self.adjacent_list[index].remove(user_index)
                    self.nb_connection[index] -= 1

            self.user_names.pop(user_index)
            self.adjacent_list.pop(user_index)
            self.nb_connection.pop(user_index)
            self.resources.pop(user_index)

            for adjacents in self.adjacent_list:
                for idx, neighbor in enumerate(adjacents):
                    if neighbor > user_index:
                        adjacents[idx] = neighbor - 1

    def display_matrix(self):
        """Affiche la matrice d'adjacence avec les noms des utilisateurs."""
        matrix = self.get_adjacent_matrix()
        n = len(self.user_names)

        print("\nAdjacency Matrix:")

        if n == 0:
            print("(empty list)")
            return

        col_width = max(len(name) for name in self.user_names)
        row_label_width = col_width

        header = " " * (row_label_width + 3)
        header += "  ".join(name.center(col_width) for name in self.user_names)
        print(header)

        separator = " " * (row_label_width + 3) + "-" * (col_width * n + 2 * (n - 1))
        print(separator)

        for i, row in enumerate(matrix):
            label = self.user_names[i].ljust(row_label_width)
            values = "  ".join(str(v).center(col_width) for v in row)
            print(f"{label} | {values}")


def generate_connexion(user_state: UserStates, new_user_name: str):
    random.seed(42)
    possible = user_state.get_disponible_neighbors_index()
    nb_connections = min(random.randint(2, 3), len(possible))
    neighbors_index = random.sample(possible, nb_connections)
    user_state.add_user(
        new_user_name,
        [user_state.user_names[index] for index in neighbors_index],
        {"CPU": DEFAULT_CPU, "RAM": DEFAULT_RAM},
        2,
    )


class GameLogic:

    def __init__(
        self,
        self_name: str = None,
    ):

        self.user_states: UserStates = None
        self.self_name = self_name

        self.send: Callable[[str, Dict[str, Any]], None] = None
        self.broadcast: Callable[[Dict[str, Any]], None] = None

        self.logs: List[Dict[str, Any]] = []
        self._bots: List[str] = []

    def initialize(
        self,
        send_fn: Callable[[str, Dict[str, Any]], None],
        broadcast_fn: Callable[[Dict[str, Any]], None],
        nb_bots: int = 0,
    ):

        self.send = send_fn
        self.broadcast = broadcast_fn
        self.user_states = UserStates(self.self_name)

        for _ in range(nb_bots):
            new_bot_name = f"User {len(self.user_states.user_names)}"
            self._on_connect({"name": new_bot_name})
            self._bots.append(new_bot_name)

    def _on_connect(self, data: dict) -> dict:
        """Gère la connexion d'un nouvel utilisateur au serveur.

        Variables locales utilisées :
        - response : sous-graphe (jusqu'à self.visibility_depth) renvoyé après
          l'ajout de l'utilisateur au graphe.
        - name : nom du joueur venant de se connecter.
        """
        new_user_name = data.get("name", "?")
        generate_connexion(self.user_states, new_user_name)
        response = {"type": "handshake"}

        print(
            f"[Game] '{new_user_name}' joined — neighbors: {self.user_states.get_neighbors(new_user_name)}"
        )

        new_user_resources = self.user_states.get_resources(new_user_name)

        # print(pprint.pformat(list(distances_to_new_user.items())))

        for curr_name in self.user_states.user_names:

            if curr_name != new_user_name:

                curr_visible_before = self.user_states.get_visible_to(
                    curr_name, new_user_name
                )
                curr_visible_after = self.user_states.get_visible_to(curr_name)

                curr_to_add = list(set(curr_visible_after) - set(curr_visible_before))
                curr_to_add.sort(key=lambda x: self.user_states.user_names.index(x))

                for curr_add in curr_to_add:
                    # print(curr_add, curr_name)

                    to_send = curr_name
                    info = {
                        "type": "new_user",
                        "name": curr_add,
                        "neighbors": [
                            t_name
                            for t_name in self.user_states.get_neighbors(curr_add)
                            if t_name in curr_visible_after and t_name != new_user_name
                        ],
                        "resources": new_user_resources,
                    }

                    self.send(to_send, info)

        return response

    def _on_disconnect(self, name: str):
        """Gère la déconnexion d'un joueur et annonce son départ aux autres clients.

        Paramètre utilisé :
        - name : nom du joueur qui vient de quitter.
        """
        print(f"[Game] '{name}' left the game")
        self.user_states.remove_user(name)

        info = {
            "type": "player_left",
            "name": name,
        }

        self.broadcast(info)

    def _build_player_state(self, name: str) -> dict:
        """Construit l'état complet envoyé à un joueur donné.

        Variables locales utilisées :
        - names : liste des joueurs connus du serveur.
        - visible : sous-graphe visible pour ce joueur, jusqu'à
          self.visibility_depth (voisins directs, voisins de voisins, etc.).
        - neighbors : voisins directs réels du joueur (arêtes du graphe).
        - all_resources : ressources de tous les nœuds visibles autour du joueur.
        """
        names = self.user_states.user_names
        if name not in names:
            return {
                "type": "state",
                "neighbors": [],
                "resources": {},
                "all_resources": {},
            }

        return {
            "type": "state",
            "users": self.user_states.get_all_data_depth(
                name, self.user_states._get_visibility_depth(name)
            ),
        }

    def _handle_message(self, sender: str, data: dict):
        """Traite les messages envoyés par un client et répond en conséquence.

        Variables locales utilisées :
        - msg_type : type de message reçu pour choisir le traitement.
        - target : cible visée par une requête ou une attaque.
        - response : réponse générée pour un ordre d'attaque.
        - timestamp, latency : données de ping/pong.
        """
        msg_type = data.get("type")

        if msg_type == "get_state":
            response = self._build_player_state(sender)
            self.send(sender, response)

        elif msg_type == "get_node_resources":
            target = data.get("target")
            res = self.user_states.get_resources(target) if target else {}
            response = {
                "type": "node_resources",
                "name": target,
                "resources": res,
            }
            self.send(sender, response)

        elif msg_type == "ping":
            response = {"type": "pong"}
            self.send(sender, response)

        elif msg_type == "pong":
            response = {}
            timestamp = data.get("timestamp")
            if isinstance(timestamp, (int, float)):
                latency = (time.time() - timestamp) * 1000
                print(f"[Server] Received pong from {sender} — RTT ≈ {latency:.1f} ms")
            else:
                print(f"[Server] Received pong from {sender}")

        elif msg_type == "close":
            response = {}
            self._on_disconnect(sender)

        else:
            response = {"type": "echo", "received": data}
            self.send(sender, response)

        self.logs.append(
            {
                "sender": sender,
                "time": int(time.time()),
                "data": data,
                "response": response,
            }
        )
