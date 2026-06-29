from typing import Any, Dict, List
import random

DEFAULT_CPU = 10
DEFAULT_RAM = 10


class AdjacentList:

    def __init__(self):
        self.user_name: List[str] = []
        self.adjacent_list: List[List[int]] = []
        self.resources: List[Dict[str, int]] = []  # ← NEW : CPU / RAM par joueur

    def get_neighbors(self, user_name: str) -> List[str]:
        try:
            user_index = self.user_name.index(user_name)
            neighbor_indices = self.adjacent_list[user_index]
            return [self.user_name[i] for i in neighbor_indices]
        except ValueError:
            return []

    def get_resources(self, user_name: str) -> Dict[str, int]:
        """Retourne les ressources d'un joueur, ou un dict vide si inconnu."""
        try:
            idx = self.user_name.index(user_name)
            return dict(self.resources[idx])
        except ValueError:
            return {}

    def add_user(self, new_user_data: Dict[str, Any]):
        new_user_name = new_user_data.get("name", f"User {len(self.user_name)}")
        self.user_name.append(new_user_name)
        self.adjacent_list.append([])
        # Ressources initiales : 10 CPU, 10 RAM
        self.resources.append({"cpu": DEFAULT_CPU, "ram": DEFAULT_RAM})
        new_index = len(self.user_name) - 1

        existing_indices = list(range(new_index))
        if existing_indices:
            nb_connections = min(random.randint(2, 4), len(existing_indices))
            chosen = random.sample(existing_indices, nb_connections)
            for i in chosen:
                self.adjacent_list[new_index].append(i)
                self.adjacent_list[i].append(new_index)

        return {
            "type": "handshake",
            "neighbors": self.get_neighbors(new_user_name),
            "resources": self.get_resources(new_user_name),  # ← NEW
        }

    def remove_user(self, user_name: str):
        try:
            user_index = self.user_name.index(user_name)
            self.user_name.pop(user_index)
            self.adjacent_list.pop(user_index)
            self.resources.pop(user_index)  # ← NEW
            for i in range(len(self.adjacent_list)):
                self.adjacent_list[i] = [
                    x for x in self.adjacent_list[i] if x != user_index
                ]
                self.adjacent_list[i] = [
                    x - 1 if x > user_index else x for x in self.adjacent_list[i]
                ]
        except ValueError:
            return

    def get_adjacent_matrix(self) -> List[List[int]]:
        size = len(self.user_name)
        matrix = [[0] * size for _ in range(size)]
        for i, adjacents in enumerate(self.adjacent_list):
            for j in adjacents:
                matrix[i][j] = 1
        return matrix

    def display_matrix(self):
        """Affiche la matrice d'adjacence avec les noms des utilisateurs."""
        matrix = self.get_adjacent_matrix()
        n = len(self.user_name)

        print("\nAdjacency Matrix:")

        if n == 0:
            print("(empty list)")
            return

        col_width = max(len(name) for name in self.user_name)
        row_label_width = col_width

        header = " " * (row_label_width + 3)
        header += "  ".join(name.center(col_width) for name in self.user_name)
        print(header)

        separator = " " * (row_label_width + 3) + "-" * (col_width * n + 2 * (n - 1))
        print(separator)

        for i, row in enumerate(matrix):
            label = self.user_name[i].ljust(row_label_width)
            values = "  ".join(str(v).center(col_width) for v in row)
            print(f"{label} | {values}")

    def _generate_random_users(self, num_users: int):
        for _ in range(num_users):
            new_user_name = f"User {_}"
            self.add_user({"name": new_user_name})


if __name__ == "__main__":

    random.seed(42)

    adjacent_list = AdjacentList()
    adjacent_list._generate_random_users(5)
    adjacent_list.display_matrix()

    adjacent_matrix = adjacent_list.get_adjacent_matrix()

    for i in range(len(adjacent_matrix)):
        assert (
            adjacent_matrix[i][i] == 0
        ), f"Erreur : l'utilisateur {adjacent_list.user_name[i]} est connecté à lui-même."
