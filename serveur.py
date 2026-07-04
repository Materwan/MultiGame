import threading
import socket
import random
import time
import traceback
from queue import Empty, Queue
from typing import List, Dict, Any, Callable

import pygame

from network import ServerNetwork
from server_utils import *
from interface import Interface

random.seed(42)


class Server:
    """Gère le serveur de jeu, la logique réseau et la synchronisation de l'état du graphe.

    Variables d'instance principales :
    - user_states : structure de graphe utilisée pour stocker les utilisateurs et leurs voisins.
    - visual : interface visuelle optionnelle liée au serveur.
    - running : indique si le serveur doit continuer à tourner.
    - server : instance de ServerNetwork utilisée pour la communication avec les clients.
    - _server_thread : thread de fond qui exécute la boucle de traitement des messages.

    Méthodes principales :
    - _on_connect, _on_disconnect : gestion des événements de connexion/déconnexion.
    - _handle_message : traitement des messages reçus par les clients.
    - _resolve_attack : résolution logique d'une attaque.
    - _build_player_state : construction de l'état envoyé à un joueur.
    - _run : boucle principale de réception des messages.
    - close, start : gestion du cycle de vie du serveur.
    """

    def __init__(
        self,
        host: str,
        port: int,
        visual: "Visual",
        visibility_depth: int = 1,
    ):
        """Initialise le serveur, la structure du graphe et la communication réseau.

        Variables d'instance créées :
        - user_states : graphe initialisé avec quelques utilisateurs de test.
        - visual : référence à l'interface visuelle passée en paramètre.
        - running : état de fonctionnement du serveur.
        - server : serveur réseau prêt à accepter des connexions.
        - _server_thread : thread chargé de traiter les messages entrants.
        - visibility_depth : profondeur du graphe (nombre de sauts depuis un
          joueur) que le serveur accepte de révéler à ce joueur. 1 = voisins
          directs uniquement (comportement historique).
        """
        self.user_states = UserStates()

        self.visual = visual
        self.visibility_depth = visibility_depth

        self.running = True

        self.server = ServerNetwork(
            host,
            port,
            on_guest_connect=self._on_connect,
            on_guest_disconnect=self._on_disconnect,
        )
        self._server_thread = threading.Thread(target=self._run, daemon=True)
        self._stdin_thread = threading.Thread(target=self._read_stdin, daemon=True)

        self._stdin_queue: Queue[str] = Queue()

        self.logs: List[Dict[str, Any]] = []

        self._stdin_thread.start()

    # ------------------------------------------------------------------
    # Callbacks réseau
    # ------------------------------------------------------------------

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

        new_user_neighbors = self.user_states.get_neighbors(new_user_name)
        distances_to_new_user = self.user_states.get_distances(new_user_name)
        new_user_resources = self.user_states.get_resources(new_user_name)

        # print(distances_to_new_user)

        for curr_name, distance in distances_to_new_user.items():

            curr_visibility = self.user_states._get_visibility_depth(curr_name)

            if distance < curr_visibility:

                self.server.send_to(
                    curr_name,
                    {
                        "type": "new_user",
                        "name": new_user_name,
                        "neighbors": new_user_neighbors,
                        "resources": new_user_resources,
                    },
                )

            elif distance == curr_visibility:

                self.server.send_to(
                    curr_name,
                    {
                        "type": "new_user",
                        "name": new_user_name,
                        "neighbors": [
                            t_name
                            for t_name in self.user_states.get_neighbors(curr_name)
                            if self.user_states.get_distance(new_user_name, t_name)
                            < curr_visibility
                        ],
                        "resources": new_user_resources,
                    },
                )

        return response

    def _on_disconnect(self, name: str):
        """Gère la déconnexion d'un joueur et annonce son départ aux autres clients.

        Paramètre utilisé :
        - name : nom du joueur qui vient de quitter.
        """
        print(f"[Game] '{name}' left the game")
        self.user_states.remove_user(name)

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
        """Traite les messages envoyés par un client et répond en conséquence.

        Variables locales utilisées :
        - msg_type : type de message reçu pour choisir le traitement.
        - target : cible visée par une requête ou une attaque.
        - response : réponse générée pour un ordre d'attaque.
        - timestamp, latency : données de ping/pong.
        """
        msg_type = data.get("type")

        if msg_type == "attack":
            target = data.get("target")
            response = self._resolve_attack(sender, target)
            self.server.send_to(sender, response)

        elif msg_type == "get_state":
            response = self._build_player_state(sender)
            self.server.send_to(sender, response)

        elif msg_type == "get_node_resources":
            target = data.get("target")
            res = self.user_states.get_resources(target) if target else {}
            response = {
                "type": "node_resources",
                "name": target,
                "resources": res,
            }
            self.server.send_to(
                sender,
                response,
            )

        elif msg_type == "ping":
            response = {"type": "pong"}
            self.server.send_to(sender, response)

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
            self.server.send_to(sender, response)

        self.logs.append(
            {
                "sender": sender,
                "time": int(time.time()),
                "data": data,
                "response": response,
            }
        )

    def _resolve_attack(self, attacker: str, target: str) -> dict:
        """Vérifie si une attaque est valide et prépare la réponse associée.

        Variables locales utilisées :
        - names : liste des noms d'utilisateurs connus.
        - attacker_idx, target_idx : indices des joueurs dans la liste.
        - are_neighbors : indique si l'attaquant et la cible sont voisins.
        - result : réponse envoyée au client attaquant.
        """
        names = self.user_states.user_names
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
            and target_idx in self.user_states.adjacent_list[attacker_idx]
        )

        result = {"type": "attack_result", "target": target, "success": are_neighbors}

        if are_neighbors:
            self.server.send_to(target, {"type": "under_attack", "from": attacker})

        return result

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

    def _run(self):
        """Boucle principale de réception des messages réseau entrants.

        Variables locales utilisées :
        - sender, data : expéditeur et contenu du message lu depuis la file d'attente.
        """
        while self.running:
            try:
                sender, data = self.server.incoming_queue.get(timeout=0.05)
                self._handle_message(sender, data)
            except Exception:
                pass

    def close(self):
        """Arrête proprement le serveur et ferme la connexion réseau.

        Aucune variable locale majeure n'est utilisée.
        """
        self.running = False
        self.server.close()

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------

    def start(self):
        """Démarre le service réseau et lance la boucle interactive de commandes.

        Aucune variable locale majeure n'est utilisée.
        """
        self.server.start()
        self._server_thread.start()

        for _ in range(5):
            self._on_connect({"name": f"User {len(self.user_states.user_names)}"})

        self._input_loop()

    def _read_stdin(self):
        """Tourne dans un thread daemon dédié : peut rester bloqué sur input()
        sans jamais empêcher le programme de se terminer."""
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                self._stdin_queue.put(None)  # signal de fin
                return
            self._stdin_queue.put(line)

    def _input_loop(self):
        """Boucle interactive de commandes permettant d'administrer le serveur.

        Fonctions internes utilisées :
        - _handle_close : gestion de la fermeture du serveur.
        - _handle_get : affichage du graphe ou des clients connectés.
        - _handle_help : aide en console.
        - _handle_ping : envoi de ping à un joueur ou à tous.
        - _handle_visual : lancement du mode visuel.
        - _handle_exit : arrêt du mode visuel.
        - _handle_unkown : gestion des commandes inconnues.
        """

        awaiting_close_confirm = False

        def _handle_close(command: List[str]):
            nonlocal awaiting_close_confirm
            print("\nAre you sure? (y/n): ", end="", flush=True)
            awaiting_close_confirm = True

        def _handle_get(command: List[str]):
            if len(command) > 1:
                if command[1] == "graph":
                    self.user_states.display_matrix()
                elif command[1] == "connected":
                    print(f"\nConnected: {self.server.connected_names()}")
                else:
                    print("\nUsage: get graph | connected")
            else:
                print("\nUsage: get graph | connected")

        def _handle_help(command: List[str]):
            print(
                "\nCommands: 'get', 'connected', 'ping', 'visual', 'exit', 'log', "
                "'generate', 'depth <n>', 'close'"
            )

        def _handle_ping(command: List[str]):
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
            if self.visual.running:
                print("\nVisual interface already running.")
            else:
                self.visual.trigger(self.user_states)

        def _handle_exit(command: List[str]):
            if not self.visual.running:
                print("\nNo visual interface already running.")
            else:
                self.visual.close()

        def _handle_log(command: List[str]):
            number = 0
            tag = ""
            for arg in command[1:]:
                if arg.isdigit():
                    number = int(arg)
                else:
                    tag = arg
            if number != 0:
                print()
                for message in self.logs[-int(number) :]:
                    print(format_log(message, tag))
            else:
                print("\nUsage: log [option] [n] (n >= 1)")

        def _handle_generate(command: List[str]):
            self._on_connect({"name": f"User_{len(self.user_states.user_names)}"})

        def _handle_depth(command: List[str]):
            if len(command) > 1 and command[1].isdigit() and int(command[1]) >= 1:
                self.visibility_depth = int(command[1])
                print(f"\nVisibility depth set to {self.visibility_depth}.")
            else:
                print(f"\nCurrent visibility depth: {self.visibility_depth}")
                print("Usage: depth <n> (n >= 1)")

        def _handle_exec(command: List[str]):
            if len(command) > 1:
                code_str = " ".join(command[1:])
                try:
                    # Contexte local avec accès à `self`
                    local_vars = {"self": self}
                    print()
                    exec(code_str, {"__builtins__": __builtins__}, local_vars)
                except Exception as e:
                    print(f"\n[Error] {type(e).__name__}: {e}")
                    print("\n[Traceback]")
                    traceback.print_exc()
            else:
                print("\nUsage: exec <python code>")

        commands: Dict[str, Callable[[List[str]], None]] = {
            "close": _handle_close,
            "get": _handle_get,
            "help": _handle_help,
            "ping": _handle_ping,
            "visual": _handle_visual,
            "exit": _handle_exit,
            "log": _handle_log,
            "generate": _handle_generate,
            "depth": _handle_depth,
            "exec": _handle_exec,
        }

        while self.running:

            try:
                line = self._stdin_queue.get(timeout=0.1)
            except Empty:
                continue

            if line:
                if awaiting_close_confirm:
                    awaiting_close_confirm = False
                    if line.lower() in ("y", "yes"):
                        self.close()
                        self.running = False
                    else:
                        print("Closing cancelled.")
                    continue
                ask = line.strip().split(" ")
                used = False
                for command in commands:
                    if ask[0] == command:
                        used = True
                        commands[command](ask)
                        break
                if not used:
                    print("Unknown command. Try 'help'.")


class Visual:

    def __init__(self):

        self.start_visual_event = threading.Event()

        self.running: bool | None = None
        self.clock: pygame.time.Clock | None = None
        self.user_stats: UserStates | None = None
        self.interface: Interface | None = None

    def trigger(self, user_stats: UserStates):

        self.running = False
        self.user_stats = user_stats
        self.start_visual_event.set()

    def close(self):

        self.running = False

    def _sync_interface(self):
        """Initialise ou met à jour l'interface visuelle avec l'état courant du graphe."""
        if (
            not hasattr(self, "screen")
            or self.screen is None
            or self.user_stats is None
        ):
            return

        if self.interface is None:
            self.interface = Interface(self.screen, self.user_stats)
        else:
            current_names = [node.name for node in self.interface.graph.nodes]
            desired_names = self.user_stats.user_names
            if current_names != desired_names:
                self.interface._build_graph(self.user_stats)
            else:
                self.interface.graph.user_states = self.user_stats
                self.interface.graph.users = self.user_stats.user_names
                self.interface.graph.user_states = self.user_stats.get_adjacent_matrix()

        self.interface.user_data = {
            name: {"CPU": 10, "RAM": 10} for name in self.user_stats.user_names
        }

    def event(self):
        """Gére les évenements : interactions du joueur avec l'interface."""

        events = pygame.event.get()

        for event in events:

            if event.type == pygame.QUIT:
                self.running = False

        if self.interface is not None:
            self.interface.event(events)

    def update(self):
        """Met à jour les éléments de l'interface."""
        self._sync_interface()
        if self.interface is not None:
            self.interface.update()

    def display(self):
        """Affiche les éléments correspondant à l'interface."""

        self.screen.fill((0, 0, 0))

        if self.interface is not None:
            self.interface.draw()

        pygame.display.flip()

    def _start(self):

        print("\nLaunched visual mode.")
        self.start_visual_event.clear()
        self.running = True

        pygame.init()
        pygame.display.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode((920, 580))

        self.interface = Interface(self.screen, self.user_stats)

        self.clock = pygame.time.Clock()

    def _end(self):

        pygame.display.quit()
        pygame.quit()

        print("\nVisual mode closed.")

    def run(self, server_thread: threading.Thread):

        while server_thread.is_alive():

            if self.start_visual_event.is_set():

                self._start()

                while self.running and server_thread.is_alive():

                    self.event()
                    self.update()
                    self.display()

                    self.clock.tick(30)

                self._end()

            time.sleep(0.1)


if __name__ == "__main__":
    host = socket.gethostbyname(socket.gethostname())
    port = 5555

    visual = Visual()

    server = Server(host, port, visual, 2)

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
