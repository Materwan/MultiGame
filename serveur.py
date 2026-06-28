import threading
import socket
import random
import time

from network import ServerNetwork
from server_utils import AdjacentList

random.seed(42)


class Server:
    """Serveur de jeu.

    Responsabilités
    ---------------
    - Maintenir l'état partagé du jeu (adjacent_list, ressources, etc.)
    - Consommer incoming_queue pour traiter chaque message avec son émetteur
    - Répondre via server.send_to() ou server.broadcast()

    ServerNetwork n'est qu'un transport : il ne connaît pas la logique métier.
    """

    def __init__(self, host: str, port: int):
        self.adjacent_list = AdjacentList()
        self.adjacent_list._generate_random_users(5)

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
        """Appelé à la connexion d'un nouveau client — retourne le handshake."""
        response = self.adjacent_list.add_user(data)
        name = data.get("name", "?")
        print(f"[Game] '{name}' joined — neighbors: {response.get('neighbors', [])}")

        # Notifie les voisins existants qu'un nouveau joueur est apparu
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
        """Appelé à la déconnexion d'un client."""
        print(f"[Game] '{name}' left the game")
        self.adjacent_list.remove_user(name)

        # Notifie les autres joueurs connectés
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
        """Traite un message entrant et répond au client concerné.

        C'est ici que toute la logique métier prend place : la fonction a
        accès à `self.adjacent_list`, `self.server.send_to()`, etc.
        """
        msg_type = data.get("type")

        if msg_type == "attack":
            target = data.get("target")
            response = self._resolve_attack(sender, target)
            self.server.send_to(sender, response)

        elif msg_type == "get_state":
            # Envoie l'état personnalisé du joueur (ses voisins, ses ressources…)
            self.server.send_to(sender, self._build_player_state(sender))

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
            # Echo par défaut — utile pendant le développement
            self.server.send_to(sender, {"type": "echo", "received": data})

    def _resolve_attack(self, attacker: str, target: str) -> dict:
        """Exemple de logique métier avec accès à adjacent_list."""
        names = self.adjacent_list.user_name
        if target not in names:
            return {
                "type": "attack_result",
                "success": False,
                "reason": "unknown_target",
            }

        attacker_idx = names.index(attacker) if attacker in names else -1
        target_idx = names.index(target)

        # Vérifie que attacker et target sont voisins dans le graphe
        are_neighbors = (
            attacker_idx >= 0
            and target_idx in self.adjacent_list.adjacent_list[attacker_idx]
        )

        result = {"type": "attack_result", "target": target, "success": are_neighbors}

        if are_neighbors:
            # Notifie la cible qu'elle est attaquée
            self.server.send_to(target, {"type": "under_attack", "from": attacker})

        return result

    def _build_player_state(self, name: str) -> dict:
        """Construit l'état personnalisé d'un joueur depuis adjacent_list."""
        names = self.adjacent_list.user_name
        if name not in names:
            return {"type": "state", "neighbors": [], "all_players": []}

        idx = names.index(name)
        neighbors = [names[i] for i in self.adjacent_list.adjacent_list[idx]]

        return {
            "type": "state",
            "neighbors": neighbors,
            "all_players": list(names),
            "connected": self.server.connected_names(),
        }

    def _run(self):
        """Boucle principale : consomme la queue de messages entrants."""
        while True:
            try:
                # Bloque 50 ms au maximum pour rester réactif à un éventuel arrêt
                sender, data = self.server.incoming_queue.get(timeout=0.05)
                self._handle_message(sender, data)
            except Exception:
                pass  # Queue vide ou timeout — on reboucle

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------

    def start(self):
        self.server.start()
        self._server_thread.start()
        self._input_loop()

    def _input_loop(self):
        while True:
            command = input().strip().split(" ")
            if command[0] == "exit":
                answer = input("\nAre you sure? (y/n): ")
                if answer in ("y", "yes"):
                    self.server.close()
                    break
                print("Exit cancelled.")
            elif command[0] == "get":
                if len(command) > 1:
                    if command[1] == "graph":
                        self.adjacent_list.display_matrix()
                    elif command[1] == "connected":
                        print(f"\nConnected: {self.server.connected_names()}")
                else:
                    print("Usage: get graph | connected")
            elif command[0] == "connected":
                print(f"\nConnected: {self.server.connected_names()}")
            elif command[0] == "help":
                print("\nCommands: 'get users', 'connected', 'exit'")
            elif command[0] == "ping":
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
            else:
                print("Unknown command. Try 'help'.")


if __name__ == "__main__":
    host = socket.gethostbyname(socket.gethostname())
    port = 5555

    try:
        Server(host, port).start()
    except KeyboardInterrupt:
        print("\n[Host] Server shutdown...")
    else:
        print("\n[Host] Server shutdown...")
