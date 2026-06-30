import threading
import socket
import random
import time
from typing import List, Dict, Any

import pygame

from network import ServerNetwork
from server_utils import AdjacentList
from interface import Interface

random.seed(42)


class Server:
    """Serveur de jeu."""

    def __init__(
        self,
        host: str,
        port: int,
        visual: "Visual",
    ):
        self.adjacent_list = AdjacentList()
        self.adjacent_list._generate_random_users(5)

        self.visual = visual

        self.running = True

        self.server = ServerNetwork(
            host,
            port,
            on_guest_connect=self._on_connect,
            on_guest_disconnect=self._on_disconnect,
        )
        self._server_thread = threading.Thread(target=self._run, daemon=True)

    # ------------------------------------------------------------------
    # Callbacks réseau
    # ------------------------------------------------------------------

    def _on_connect(self, data: dict) -> dict:
        response = self.adjacent_list.add_user(data)
        name = data.get("name", "?")
        print(f"[Game] '{name}' joined — neighbors: {response.get('neighbors', [])}")

        for neighbor_name in response.get("neighbors", []):
            self.server.send_to(
                neighbor_name,
                {
                    "type": "new_neighbor",
                    "name": name,
                },
            )

        return response

    def _on_disconnect(self, name: str):
        print(f"[Game] '{name}' left the game")
        self.adjacent_list.remove_user(name)

        self.server.broadcast(
            {
                "type": "player_left",
                "name": name,
            }
        )

    # ------------------------------------------------------------------
    # Boucle de jeu
    # ------------------------------------------------------------------

    def _handle_message(self, sender: str, data: dict):
        msg_type = data.get("type")

        if msg_type == "attack":
            target = data.get("target")
            response = self._resolve_attack(sender, target)
            self.server.send_to(sender, response)

        elif msg_type == "get_state":
            self.server.send_to(sender, self._build_player_state(sender))

        elif msg_type == "get_node_resources":
            target = data.get("target")
            res = self.adjacent_list.get_resources(target) if target else {}
            self.server.send_to(
                sender,
                {
                    "type": "node_resources",
                    "name": target,
                    "resources": res,
                },
            )

        elif msg_type == "ping":
            self.server.send_to(sender, {"type": "pong"})

        elif msg_type == "pong":
            timestamp = data.get("timestamp")
            if isinstance(timestamp, (int, float)):
                latency = (time.time() - timestamp) * 1000
                print(f"[Server] Received pong from {sender} — RTT ≈ {latency:.1f} ms")
            else:
                print(f"[Server] Received pong from {sender}")

        else:
            self.server.send_to(sender, {"type": "echo", "received": data})

    def _resolve_attack(self, attacker: str, target: str) -> dict:
        names = self.adjacent_list.user_name
        if target not in names:
            return {
                "type": "attack_result",
                "success": False,
                "reason": "unknown_target",
            }

        attacker_idx = names.index(attacker) if attacker in names else -1
        target_idx = names.index(target)

        are_neighbors = (
            attacker_idx >= 0
            and target_idx in self.adjacent_list.adjacent_list[attacker_idx]
        )

        result = {"type": "attack_result", "target": target, "success": are_neighbors}

        if are_neighbors:
            self.server.send_to(target, {"type": "under_attack", "from": attacker})

        return result

    def _build_player_state(self, name: str) -> dict:
        names = self.adjacent_list.user_name
        if name not in names:
            return {"type": "state", "neighbors": [], "all_players": []}

        idx = names.index(name)
        neighbors = [names[i] for i in self.adjacent_list.adjacent_list[idx]]

        # ← NEW : on inclut les ressources de TOUS les joueurs connus
        all_resources = {n: self.adjacent_list.get_resources(n) for n in names}

        return {
            "type": "state",
            "neighbors": neighbors,
            "all_players": list(names),
            "connected": self.server.connected_names(),
            "all_resources": all_resources,  # ← NEW
            "resources": self.adjacent_list.get_resources(name),
        }

    def _run(self):
        while self.running:
            try:
                sender, data = self.server.incoming_queue.get(timeout=0.05)
                self._handle_message(sender, data)
            except Exception:
                pass

    def close(self):

        self.running = False
        self.server.close()

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------

    def start(self):
        self.server.start()
        self._server_thread.start()
        self._input_loop()

    def _input_loop(self):

        def _handle_close(command: List[str]):
            if command[0] == "close":
                try:
                    answer = input("\nAre you sure? (y/n): ")
                except EOFError:
                    self.running = False
                except KeyboardInterrupt:
                    self.running = False

                if answer in ("y", "yes"):
                    self.close()
                    self.running = False
                print("Closing cancelled.")

        def _handle_get(command: List[str]):
            if command[0] == "get":
                if len(command) > 1:
                    if command[1] == "graph":
                        self.adjacent_list.display_matrix()
                    elif command[1] == "connected":
                        print(f"\nConnected: {self.server.connected_names()}")
                    else:
                        print("\nUsage: get graph | connected")
                else:
                    print("\nUsage: get graph | connected")

        def _handle_help(command: List[str]):
            if command[0] == "help":
                print("\nCommands: 'get', 'connected', 'exit'")

        def _handle_ping(command: List[str]):
            if command[0] == "ping":
                if len(command) > 1:
                    payload = {"type": "ping", "timestamp": time.time()}
                    if command[1] in self.server.connected_names():
                        self.server.send_to(command[1], payload)
                        print(f"\nPing sent to {command[1]}")
                    elif command[1] == "all":
                        self.server.broadcast(payload)
                        print("\nPing sent to all connected clients")
                    else:
                        print(f"\n'{command[1]}' is not a connected client")
                else:
                    print("Usage: ping <player_name> | all")

        def _handle_visual(command: List[str]):
            if command[0] == "visual":
                if self.visual.running:
                    print("\nVisual interface already running.")
                else:
                    self.visual.trigger()
                    print("\nLaunched visual mode.")

        def _handle_exit(command: List[str]):
            if command[0] == "exit":
                if not self.visual.running:
                    print("\nNo visual interface already running.")
                else:
                    self.visual.end()

        def _handle_unkown(command: List[str]):
            if command[0] not in ["close", "get", "help", "ping", "visual", "exit"]:
                print("Unknown command. Try 'help'.")

        while self.running:
            try:
                command = input().strip().split(" ")
            except EOFError:
                self.running = False
            except KeyboardInterrupt:
                self.running = False

            _handle_close(command)
            _handle_get(command)
            _handle_help(command)
            _handle_ping(command)
            _handle_visual(command)
            _handle_exit(command)
            _handle_unkown(command)


class Visual:

    def __init__(self):

        self.start_visual_event = threading.Event()

        self.running = False
        self.clock = pygame.time.Clock()

        self._data: Dict[str, Any] = {}

    def trigger(self):

        self.running = False
        self.start_visual_event.set()

    def end(self):

        self.running = False

    def update_data(self, data: Dict[str, Any]):
        self._data = data

    def event(self):
        """Gére les évenements : interactions du joueur avec l'interface."""

        events = pygame.event.get()

        for event in events:

            if event.type == pygame.QUIT:
                self.running = False

    def update(self):
        """Met à jour les éléments de l'interface."""

    def display(self):
        """Affiche les éléments correspondant à l'interface."""

        self.screen.fill((0, 0, 0))

        pygame.display.flip()

    def run(self, server_thread: threading.Thread):

        while server_thread.is_alive():

            if self.start_visual_event.is_set():
                self.start_visual_event.clear()
                self.running = True

                pygame.init()
                pygame.display.init()

                self.screen = pygame.display.set_mode((920, 580))

                while self.running and server_thread.is_alive():

                    self.event()
                    self.update()
                    self.display()

                    self.clock.tick(30)

                pygame.display.quit()
                pygame.quit()

                print("\nVisual mode closed.")

            time.sleep(0.1)


if __name__ == "__main__":
    host = socket.gethostbyname(socket.gethostname())
    port = 5555

    visual = Visual()

    server = Server(host, port, visual)

    server_thread = threading.Thread(target=server.start)

    try:
        server_thread.start()
        visual.run(server_thread)
    except KeyboardInterrupt:
        server.close()
        while server.server._tcp_thread.is_alive():
            time.sleep(0.05)
        print("\n[Server] Server shutdown...")
    else:
        print("\n[Server] Server shutdown...")
