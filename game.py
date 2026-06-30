import socket
import threading
import time
from typing import List, Dict, Any

import pygame

from client_utils import *
from network import ClientNetwork
from graph import GraphView


class Game(DefaultState):
    """Gère l'état de jeu principal et la communication avec le serveur."""

    def __init__(
        self,
        screen: pygame.Surface,
        manager: BaseManager,
        host: str = socket.gethostbyname(socket.gethostname()),
        port: int = 5555,
        name: str = "Materwan",
    ):
        """Initialise la vue de jeu, la connexion réseau et les données de graphe."""
        super().__init__(screen, manager)

        self.host = host
        self.port = port
        self.name = name

        self.client = ClientNetwork(self.host, self.port, self.name)
        self._game_thread = threading.Thread(target=self._run, daemon=True)

        self.neighbors: List[str] = []
        self.all_players: List[str] = []
        self.connected_players: List[str] = []
        self.resources: Dict[str, int] = {"cpu": 10, "ram": 10}  # ← NEW
        self.all_resources: Dict[str, Dict[str, int]] = {}  # ← NEW

        self.graph_view: GraphView | None = None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(self):
        """Démarre la connexion au serveur et lance la boucle de jeu."""
        self.client.start()

        deadline = time.time() + 3.0
        while not self.client.connected and time.time() < deadline:
            time.sleep(0.05)

        if self.client.connected:
            self._apply_initial_state(self.client.initial_state)
            self._game_thread.start()
            self.client.send({"type": "get_state"})
        else:
            print("[Game] Failed to connect to server")

    def close_connexion(self):
        """Ferme proprement la connexion réseau active."""
        self.client.close()

    # ------------------------------------------------------------------
    # Boucle de traitement des messages entrants
    # ------------------------------------------------------------------

    def _run(self):
        """Lit en continu les messages entrants et les transmet au gestionnaire."""
        while self.client.connected or not self.client.incoming_queue.empty():
            try:
                data = self.client.incoming_queue.get(timeout=0.05)
                self._handle_message(data)
            except Exception:
                pass

    def _handle_message(self, data: Dict[str, Any]):
        """Traite un message réseau reçu et met à jour l'état local."""
        msg_type = data.get("type")

        if msg_type == "state":
            self.neighbors = data.get("neighbors", self.neighbors)
            self.all_players = data.get("all_players", self.all_players)
            self.connected_players = data.get("connected", self.connected_players)
            self.resources = data.get("resources", self.resources)
            new_all_res = data.get("all_resources", {})
            if new_all_res:
                self.all_resources.update(new_all_res)
                if self.graph_view:
                    self.graph_view.set_all_resources(self.all_resources)
            self._sync_graph_view()

        elif msg_type == "node_resources":
            node_name = data.get("name")
            res = data.get("resources", {})
            if node_name and res:
                self.all_resources[node_name] = res
                if self.graph_view:
                    self.graph_view.set_all_resources({node_name: res})

        elif msg_type == "new_neighbor":
            new_name = data.get("name")
            if new_name and new_name not in self.neighbors:
                self.neighbors.append(new_name)
                self._sync_graph_view()
                print(f"[Game] New neighbor: {new_name}")

        elif msg_type == "player_left":
            left_name = data.get("name")
            if left_name in self.neighbors:
                self.neighbors.remove(left_name)
            if left_name in self.all_players:
                self.all_players.remove(left_name)
            self._sync_graph_view()
            print(f"[Game] Player left: {left_name}")

        elif msg_type == "under_attack":
            attacker = data.get("from")
            print(f"[Game] Under attack from: {attacker}")

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
            self.send({"type": "pong", "timestamp": time.time()})

        else:
            print(f"[Game] Unknown message type '{msg_type}': {data}")

    def _sync_graph_view(self):
        """Met à jour la vue graphique du graphe avec les nœuds et liens courants."""
        if not self.graph_view:
            return
        nodes = (
            self.all_players or self.connected_players or self.neighbors or [self.name]
        )
        edges = [
            (self.name, neighbor)
            for neighbor in self.neighbors
            if neighbor != self.name
        ]
        self.graph_view.update_graph(self.name, nodes, edges)

    def _apply_initial_state(self, state: Dict[str, Any]):
        """Applique l'état initial fourni par le serveur à l'instance locale."""
        self.neighbors = state.get("neighbors", [])
        self.all_players = state.get("all_players", self.all_players)
        self.connected_players = state.get("connected", self.connected_players)
        self.resources = state.get("resources", {"cpu": 10, "ram": 10})  # ← NEW
        self.graph_view = GraphView(
            self.screen,
            self.name,
            self.all_players or self.connected_players or self.neighbors or [self.name],
            [
                (self.name, neighbor)
                for neighbor in self.neighbors
                if neighbor != self.name
            ],
        )
        # Pré-charge les ressources connues dès le handshake
        if self.resources:
            self.all_resources[self.name] = self.resources
            self.graph_view.set_all_resources(self.all_resources)
        self._sync_graph_view()
        print(f"[Game] Initial neighbors: {self.neighbors}")
        print(f"[Game] Initial resources: {self.resources}")

    # ------------------------------------------------------------------
    # Envoi vers le serveur
    # ------------------------------------------------------------------

    def send(self, data: Dict[str, Any]):
        """Envoie un payload au serveur via le client réseau."""
        self.client.send(data)

    def attack(self, target: str):
        """Demande l'attaque d'une cible donnée."""
        self.send({"type": "attack", "target": target})

    def request_state(self):
        """Demande une mise à jour complète de l'état au serveur."""
        self.send({"type": "get_state"})

    def ping(self):
        """Envoie un message de ping pour tester la latence réseau."""
        self.send({"type": "ping"})

    # ------------------------------------------------------------------
    # Boucle PyGame
    # ------------------------------------------------------------------

    def event(self, events: List[pygame.event.Event]):
        """Traite les événements PyGame et les routes vers les composants concernés."""
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
        """Met à jour l'état courant du jeu."""
        super().update()

    def display(self):
        """Rafraîchit l'affichage du jeu et de la vue graphique."""
        self.screen.fill(BLACK)
        if self.graph_view is not None:
            self.graph_view.draw()
        else:
            font = pygame.font.SysFont("Consolas", 18, bold=True)
            msg = font.render("Connecting to server...", True, (0, 180, 80))
            w, h = self.screen.get_size()
            self.screen.blit(msg, (w // 2 - msg.get_width() // 2, h // 2))

        super().display()
