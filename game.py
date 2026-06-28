import socket
import threading
import time
from typing import List, Dict, Any

import pygame

from client_utils import *
from network import ClientNetwork
from graph import GraphView


class Game(DefaultState):
    """État de jeu principal.

    Symétrique à Server : possède une boucle _run() dans un thread dédié
    qui consomme client.incoming_queue et dispatche via _handle_message().
    L'envoi vers le serveur se fait via client.send().
    """

    def __init__(
        self,
        screen: pygame.Surface,
        manager: BaseManager,
        host: str = socket.gethostbyname(socket.gethostname()),
        port: int = 5555,
        name: str = "Materwan",
    ):
        super().__init__(screen, manager)

        self.host = host
        self.port = port
        self.name = name

        self.client = ClientNetwork(self.host, self.port, self.name)
        self._game_thread = threading.Thread(target=self._run, daemon=True)

        # État local du joueur, rempli au handshake et mis à jour par les messages
        self.neighbors: List[str] = []
        self.all_players: List[str] = []
        self.connected_players: List[str] = []

        self.graph_view: GraphView | None = None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(self):
        """Démarre la connexion et le thread de traitement des messages."""
        self.client.start()

        # Attendre que le handshake soit reçu (au plus 3 s)
        deadline = time.time() + 3.0
        while not self.client.connected and time.time() < deadline:
            time.sleep(0.05)

        if self.client.connected:
            self._apply_initial_state(self.client.initial_state)
            self._game_thread.start()
            self.client.send({"type": "get_state"})  # Demande l'état initial du joueur
        else:
            print("[Game] Failed to connect to server")

    def close_connexion(self):
        """Ferme proprement la connexion."""
        self.client.close()

    # ------------------------------------------------------------------
    # Boucle de traitement des messages entrants
    # ------------------------------------------------------------------

    def _run(self):
        """Consomme incoming_queue et dispatche chaque message."""
        while self.client.connected or not self.client.incoming_queue.empty():
            try:
                data = self.client.incoming_queue.get(timeout=0.05)
                self._handle_message(data)
            except Exception:
                pass  # Queue vide — on reboucle

    def _handle_message(self, data: Dict[str, Any]):
        """Traite un message reçu du serveur selon son type."""
        msg_type = data.get("type")

        if msg_type == "state":
            self.neighbors = data.get("neighbors", self.neighbors)
            self.all_players = data.get("all_players", self.all_players)
            self.connected_players = data.get("connected", self.connected_players)

        elif msg_type == "new_neighbor":
            new_name = data.get("name")
            if new_name and new_name not in self.neighbors:
                self.neighbors.append(new_name)
                print(f"[Game] New neighbor: {new_name}")

        elif msg_type == "player_left":
            left_name = data.get("name")
            if left_name in self.neighbors:
                self.neighbors.remove(left_name)
            print(f"[Game] Player left: {left_name}")

        elif msg_type == "under_attack":
            attacker = data.get("from")
            print(f"[Game] Under attack from: {attacker}")
            # TODO: déclencher une animation / réponse

        elif msg_type == "attack_result":
            success = data.get("success")
            target = data.get("target")
            print(f"[Game] Attack on '{target}': {'success' if success else 'failed'}")

        elif msg_type == "pong":
            ping_ts = data.get("timestamp")
            if isinstance(ping_ts, (int, float)):
                rtt = (time.time() - ping_ts) * 1000
                print(f"[Game] Pong! RTT ≈ {rtt:.1f} ms")
            else:
                print(f"[Game] Pong received: {data}")

        elif msg_type == "ping":
            # Réponse immédiate à un ping du serveur
            self.send({"type": "pong", "timestamp": time.time()})

        else:
            print(f"[Game] Unknown message type '{msg_type}': {data}")

    def _apply_initial_state(self, state: Dict[str, Any]):
        """Applique l'état initial reçu lors du handshake."""
        self.neighbors = state.get("neighbors", [])
        self.graph_view = GraphView(self.screen, self.name, self.neighbors)
        print(f"[Game] Initial neighbors: {self.neighbors}")

    # ------------------------------------------------------------------
    # Envoi vers le serveur
    # ------------------------------------------------------------------

    def send(self, data: Dict[str, Any]):
        """Envoie un message au serveur. Peut être appelé depuis n'importe quel thread."""
        self.client.send(data)

    def attack(self, target: str):
        """Exemple : déclenche une attaque sur un voisin."""
        self.send({"type": "attack", "target": target})

    def request_state(self):
        """Demande au serveur l'état courant du joueur."""
        self.send({"type": "get_state"})

    def ping(self):
        """Envoie un ping pour mesurer la latence."""
        self.send({"type": "ping"})

    # ------------------------------------------------------------------
    # Boucle PyGame
    # ------------------------------------------------------------------

    def event(self, events: List[pygame.event.Event]):
        super().event(events)
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    self.ping()
                if event.key == pygame.K_r:
                    self.request_state()

            if self.graph_view:
                self.graph_view.handle_event(event)

    def update(self):
        super().update()

    def display(self):
        self.screen.fill(BLACK)
        if self.graph_view is not None:
            self.graph_view.draw()
        else:
            # Écran d'attente tant que la connexion n'est pas établie
            font = pygame.font.SysFont("Consolas", 18, bold=True)
            msg = font.render("Connecting to server...", True, (0, 180, 80))
            w, h = self.screen.get_size()
            self.screen.blit(msg, (w // 2 - msg.get_width() // 2, h // 2))

        super().display()
