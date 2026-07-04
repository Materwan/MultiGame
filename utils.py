from typing import Any, Dict, List
import random
from datetime import datetime

DEFAULT_CPU = 10
DEFAULT_RAM = 10
DEFAULT_RESOURCES = {"CPU": DEFAULT_CPU, "RAM": DEFAULT_RAM}
DEFAULT_DEPTH_VISIBILITY = 1


class UserStates:

    def __init__(self, self_name: str | None = None):

        self.self_name = self_name

        self.user_names: List[str] = []
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

    def get_distances(self, user_name: str) -> Dict[str, int]:

        to_visit = [(name, 1) for name in self.get_neighbors(user_name)]
        return_dict = {user_name: 0}

        while len(to_visit) > 0:

            curr_name, distance = to_visit.pop(0)

            if curr_name not in return_dict:

                return_dict[curr_name] = distance
                to_add = [
                    (name, distance + 1) for name in self.get_neighbors(curr_name)
                ]

                for t_name, t_distance in to_add:

                    if t_name not in return_dict:

                        to_visit.append((t_name, t_distance))

        return return_dict

    def get_distance(self, start_user: str, end_user: str) -> int:

        if start_user == end_user:
            return 0

        to_visit = [(name, 1) for name in self.get_neighbors(start_user)]
        visited = [start_user]

        while len(to_visit) > 0:

            curr_name, distance = to_visit.pop(0)

            if curr_name == end_user:
                return distance

            to_add = [(name, distance + 1) for name in self.get_neighbors(curr_name)]

            for t_name, t_distance in to_add:

                if t_name not in visited:

                    to_visit.append((t_name, t_distance))

        return -1

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
        self.resources.append(resources)
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

            self.user_names.pop(user_index)
            self.adjacent_list.pop(user_index)
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
