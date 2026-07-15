import socket
import threading
import time
import traceback
from typing import List, Dict, Any, Callable
from queue import Empty, Queue

import pygame

from client_utils import *
from network import ClientNetwork
from UI.interface import Interface


class DefaultGame(DefaultState):

    def __init__(self, screen, manager, name: str = "Materwan"):
        super().__init__(screen, manager)

        self.name = name

        self.user_state = UserStates(self.name)
        self.neighbors: List[str] = []
        self.all_players: List[str] = []
        self.connected_players: List[str] = []
        self.resources: Dict[str, Any] = {}
        self.all_resources: Dict[str, Dict[str, Any]] = {}

        self._pending_messages: Queue[Dict[str, Any]] = Queue()

        self.logs: List[Dict[str, Any]] = []

        self.interface: Interface = Interface(self.screen, self.user_state, self.name)

    # ------------------------------------------------------------------
    # Boucle de traitement des messages client
    # ------------------------------------------------------------------

    def _handle_message(self, data: Dict[str, Any]):
        """Traite un message réseau reçu et met à jour l'état local.

        Variables locales utilisées :
        - msg_type : type du message pour choisir la branche de traitement.
        - node_name, res : données d'un message de ressources d'un nœud.
        - new_name, left_name, attacker, target, success : informations extraites des messages spécifiques.
        - ping_ts, rtt : données de latence pour les messages ping/pong.
        """
        # print("[Guest] Message recieved. : ", data)
        response = {}
        msg_type = data.get("type")

        if msg_type == "state":
            self._apply_user_states(data)

        elif msg_type == "node_resources":
            node_name = data.get("name")
            res = data.get("resources", {})
            if node_name and res:
                self.all_resources[node_name] = res
                self._update_interface_resources({node_name: res})

        elif msg_type == "new_user":
            """print("New user name : ", data.get("name"))
            print("Neighbors : ", data.get("neighbors"))
            print(
                "Resources : ",
                data.get("resources"),
            )"""
            self.user_state.add_user(
                data.get("name"),
                data.get("neighbors"),
                data.get("resources"),
            )
            self._sync_interface()
            # self.user_state.display_matrix()

        elif msg_type == "player_left":
            left_name = data.get("name")
            if left_name in self.neighbors:
                self.neighbors.remove(left_name)
            if left_name in self.all_players:
                self.all_players.remove(left_name)
            self._sync_interface()
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
            response = {"type": "pong", "timestamp": time.time()}
            self.send(response)

        else:
            print(f"[Game] Unknown message type '{msg_type}': {data}")

        self.logs.append(
            {
                "time": int(time.time()),
                "data": data,
                "response": response,
            }
        )

    def _apply_user_states(self, data: Dict[str, Dict[str, Any]]):
        user_data = data.get("users", {})
        for user in user_data.keys():
            self.user_state.add_user(user, [], DEFAULT_RESOURCES)

        for user, data in user_data.items():
            self.user_state.update_user(
                user,
                data.get("neighbors", []),
                data.get("resources", DEFAULT_RESOURCES),
            )

        self.interface.sync()

    def _build_adjacent_matrix(self, users: List[str]) -> List[List[int]]:
        """Construit une matrice d'adjacence à partir des voisins connus du joueur.

        Seuls les liens entre soi-même et ses voisins directs sont connus côté
        client ; le reste de la matrice est donc rempli de zéros.

        Variables locales utilisées :
        - size : taille de la matrice selon le nombre d'utilisateurs.
        - matrix : matrice d'adjacence à remplir.
        - self_idx : index du joueur courant dans la liste d'utilisateurs.
        """
        size = len(users)
        matrix = [[0] * size for _ in range(size)]
        if self.name not in users:
            return matrix
        self_idx = users.index(self.name)
        for neighbor in self.neighbors:
            if neighbor == self.name or neighbor not in users:
                continue
            n_idx = users.index(neighbor)
            matrix[self_idx][n_idx] = 1
            matrix[n_idx][self_idx] = 1
        return matrix

    def _build_user_data(self) -> Dict[str, Dict[str, int]]:
        """Construit le dictionnaire de données utilisateur attendu par l'interface.

        Variables locales utilisées :
        - user_data : dictionnaire regroupant les ressources de chaque joueur.
        - name, res : nom et ressources de chaque entrée connue.
        """
        user_data: Dict[str, Dict[str, int]] = {}
        for name, res in self.all_resources.items():
            user_data[name] = {
                "CPU": res.get("CPU", res.get("cpu", 10)),
                "RAM": res.get("RAM", res.get("ram", 10)),
            }
        if self.name not in user_data:
            user_data[self.name] = {
                "CPU": self.resources.get("CPU", self.resources.get("cpu", 10)),
                "RAM": self.resources.get("RAM", self.resources.get("ram", 10)),
            }
        return user_data

    def _update_interface_resources(self, new_resources: Dict[str, Dict[str, int]]):
        """Met à jour les données affichées par les fenêtres d'info ouvertes.

        Variables locales utilisées :
        - name, res : nom du nœud et ressources associées à mettre à jour.
        """
        if not self.interface:
            return
        for name, res in new_resources.items():
            self.interface.user_data[name] = {
                "CPU": res.get("CPU", res.get("cpu", 10)),
                "RAM": res.get("RAM", res.get("ram", 10)),
            }

    def _sync_interface(self):
        """Met à jour l'interface graphique avec les nœuds et liens courants.

        La toute première fois, l'interface est créée. Ensuite, on ne fait
        plus jamais que la mettre à jour "en place" via `Interface.sync`, qui
        conserve les nœuds déjà présents (position, drag, hover, fenêtre
        d'info ouverte...) et ne crée/supprime que ce qui a réellement changé
        (joueurs arrivés/partis, matrice d'adjacence).
        """
        if self.interface is None:
            self.interface = Interface(
                self.screen,
                self.user_state,
                self.name,
            )
            self.interface.user_data = self._build_user_data()
            return

        self.interface.sync()
        self.interface.user_data = self._build_user_data()

    # ------------------------------------------------------------------
    # Boucle PyGame
    # ------------------------------------------------------------------

    def event(self, events: List[pygame.event.Event]):
        """Traite les événements PyGame et les routes vers les composants concernés.

        Paramètre utilisé :
        - events : liste des événements pygame à analyser.
        """
        super().event(events)
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    self.ping()
                if event.key == pygame.K_r:
                    self.request_state()

        if self.interface:
            self.interface.event(events)

    def update(self):
        """Met à jour l'état courant du jeu.

        Aucune variable locale majeure n'est utilisée.
        """
        super().update()
        while not self._pending_messages.empty():
            data = self._pending_messages.get()
            self._handle_message(data)
        if self.interface:
            self.interface.update()

        if self.__class__.__name__ == "MultiGame" and not self.client.connected:
            self.manager.change_state("Principal_Menu")

    def display(self):
        """Rafraîchit l'affichage du jeu et de la vue graphique.

        Variables locales utilisées :
        - font, msg, w, h : éléments nécessaires au rendu du message de connexion en attente.
        """
        self.screen.fill(BLACK)
        if self.interface is not None:
            self.interface.draw(self.manager.clock)
        else:
            font = pygame.font.SysFont("Consolas", 18, bold=True)
            msg = font.render("Connecting to server...", True, (0, 180, 80))
            w, h = self.screen.get_size()
            self.screen.blit(msg, (w // 2 - msg.get_width() // 2, h // 2))

        super().display()


class MultiGame(DefaultGame):
    """Gère l'état de jeu principal, la communication réseau et la synchronisation avec l'interface.

    Variables d'instance principales :
    - host, port, name : paramètres de connexion du client.
    - client : instance de ClientNetwork utilisée pour envoyer et recevoir les messages.
    - _game_thread : thread de fond qui traite les messages entrants.
    - neighbors, all_players, connected_players : listes des joueurs visibles et connectés.
    - resources, all_resources : ressources du joueur courant et des autres nœuds connus.
    - interface : référence vers l'interface graphique associée au jeu.

    Méthodes principales :
    - start, close_connexion : gestion du cycle de vie réseau.
    - _run, _handle_message : traitement des messages entrants.
    - _build_adjacent_matrix, _build_user_data : construction des données utilisées par le graphe.
    - _update_interface_resources, _sync_interface, _apply_initial_state : synchronisation avec l'interface.
    - send, attack, request_state, ping : envoi de commandes au serveur.
    - event, update, display : intégration avec la boucle PyGame.
    """

    def __init__(
        self,
        screen: pygame.Surface,
        manager: BaseManager,
        host: str = socket.gethostbyname(socket.gethostname()),
        port: int = 5555,
        name: str = "Materwan",
    ):
        """Initialise la vue de jeu, la connexion réseau et les structures internes.

        Variables d'instance créées :
        - host, port, name : paramètres de connexion du joueur.
        - client : client réseau prêt à se connecter au serveur.
        - _game_thread : thread de fond dédié au traitement des messages.
        - neighbors, all_players, connected_players : listes d'information réseau.
        - resources, all_resources : état des ressources du joueur et des autres nœuds.
        - interface : interface graphique encore non initialisée.
        """
        super().__init__(screen, manager, name)

        self.host = host
        self.port = port

        self.client: ClientNetwork = None
        self._game_thread: threading.Thread = None
        self._input_thread: threading.Thread = None
        self._stdin_thread = threading.Thread(target=self._read_stdin, daemon=True)

        self._stdin_queue: Queue[str] = Queue()

        self.logs: List[Dict[str, Any]] = []

        self._stdin_thread.start()

    def _initialize(self):
        self.client = ClientNetwork(self.host, self.port, self.name)
        self._game_thread = threading.Thread(target=self._run, daemon=True)
        self._input_thread = threading.Thread(target=self._input_loop, daemon=True)

        self._stdin_queue: Queue[str] = Queue()
        self.user_state = UserStates(self.name)

        self.interface: Interface = Interface(self.screen, self.user_state, self.name)

        self.logs: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(self):
        """Démarre la connexion au serveur et lance la boucle de jeu.

        Variables locales utilisées :
        - deadline : temporisation de 3 secondes pour attendre la connexion.
        """
        self._initialize()
        self.client.start()

        deadline = time.time() + 3.0
        while not self.client.connected and time.time() < deadline:
            time.sleep(0.05)

        if self.client.connected:
            # self._apply_initial_state(self.client.initial_state)
            if not self._game_thread.is_alive():
                self._game_thread.start()
            if not self._input_thread.is_alive():
                self._input_thread.start()
            self.client.send({"type": "get_state"})
        else:
            print("[Game] Failed to connect to server")

    def close_connexion(self):
        """Ferme proprement la connexion réseau active.

        Aucune variable locale majeure n'est utilisée.
        """
        if self.client:
            self.client.close()

    def _run(self):
        """Lit en continu les messages entrants et les transmet au gestionnaire.

        Variables locales utilisées :
        - data : message réseau extrait de la file d'attente.
        """
        while self.client.connected or not self.client.incoming_queue.empty():
            try:
                data = self.client.incoming_queue.get(timeout=0.05)
                self._pending_messages.put(data)
            except Empty:
                pass

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
        """Boucle console pour saisir des commandes de jeu pendant l'exécution.

        Commandes prises en charge :
        - help : affiche l'aide.
        - ping : envoie un ping au serveur.
        - state : demande une mise à jour de l'état.
        - attack <cible> : attaque un joueur.
        - get neighbors|players|connected|resources : affiche les données locales.
        - quit|exit|close : ferme la connexion et arrête le jeu.
        """

        def _handle_help(command: List[str]):
            print(
                "\nCommands: help | ping | state | attack <target> | get <neighbors|players|connected|resources> | quit"
            )

        def _handle_ping(command: List[str]):
            self.ping()
            print("\nPing sent to server.")

        def _handle_state(command: List[str]):
            self.request_state()
            print("\nState request sent.")

        def _handle_attack(command: List[str]):
            if len(command) > 1:
                target = command[1]
                self.attack(target)
                print(f"\nAttack request sent to '{target}'.")
            else:
                print("\nUsage: attack <target>")

        def _handle_get(command: List[str]):
            if len(command) > 1:
                option = command[1]
                if option == "neighbors":
                    print(f"\nNeighbors: {self.neighbors}")
                elif option in ("players", "all_players"):
                    print(f"\nAll players: {self.all_players}")
                elif option == "connected":
                    print(f"\nConnected players: {self.connected_players}")
                elif option == "resources":
                    print(f"\nMy resources: {self.resources}")
                    print(f"All resources: {self.all_resources}")
                elif option == "graph":
                    self.user_state.display_matrix()
                else:
                    print("\nUsage: get neighbors | players | connected | resources")
            else:
                print("\nUsage: get neighbors | players | connected | resources")

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

        def _handle_exec(command: List[str]):
            if len(command) > 1:
                code_str = " ".join(command[1:])
                try:
                    # Contexte local avec accès à `self`
                    local_vars = {"self": self}
                    print()
                    exec(code_str, globals(), local_vars)
                except Exception as e:
                    print(f"\n[Error] {type(e).__name__}: {e}")
                    print("\n[Traceback]")
                    traceback.print_exc()
            else:
                print("\nUsage: exec <python code>")

        def _handle_quit(command: List[str]):
            self.close_connexion()
            self.manager.running = False
            print("\nClosing game.")

        commands: Dict[str, Callable[[List[str]], None]] = {
            "help": _handle_help,
            "ping": _handle_ping,
            "state": _handle_state,
            "attack": _handle_attack,
            "get": _handle_get,
            "log": _handle_log,
            "exec": _handle_exec,
            "quit": _handle_quit,
        }

        while self.manager.running and self.client.connected:

            try:
                line = self._stdin_queue.get(timeout=0.1)
            except Empty:
                continue

            if line:
                ask = line.strip().split(" ")
                used = False
                for command in commands:
                    if ask[0] == command:
                        used = True
                        commands[command](ask)
                        break
                if not used:
                    print("Unknown command. Try 'help'.")

    def _apply_initial_state(self, state: Dict[str, Any]):
        """Applique l'état initial fourni par le serveur à l'instance locale.

        Variables locales utilisées :
        - state : dictionnaire contenant les données initiales reçues du serveur.
        """

        user_names = list(state.keys())
        neighbors = state[self.name]["neighbors"]
        resources = state[self.name]["resources"]

        self.user_state.add_multiple_users(user_names, neighbors, resources)

        self._sync_interface()
        print(f"[Game] Initial neighbors: {self.user_state.get_neighbors(self.name)}")
        print(f"[Game] Initial resources: {self.user_state.get_ressources(self.name)}")

    # ------------------------------------------------------------------
    # Envoi vers le serveur
    # ------------------------------------------------------------------

    def send(self, data: Dict[str, Any]):
        """Envoie un payload au serveur via le client réseau.

        Paramètre utilisé :
        - data : message à transmettre au serveur.
        """
        self.client.send(data)

    def attack(self, target: str):
        """Demande l'attaque d'une cible donnée.

        Paramètre utilisé :
        - target : nom du joueur ou du nœud visé par l'attaque.
        """
        self.send({"type": "attack", "target": target})

    def request_state(self):
        """Demande une mise à jour complète de l'état au serveur.

        Aucune variable locale majeure n'est utilisée.
        """
        self.send({"type": "get_state"})

    def ping(self):
        """Envoie un message de ping pour tester la latence réseau.

        Aucune variable locale majeure n'est utilisée.
        """
        self.send({"type": "ping"})


class SoloGame(DefaultGame):
    """Rejoue localement, sans réseau, exactement le pipeline de `Server`.

    Le joueur local et les bots sont gérés par la même `GameLogic` que celle
    utilisée par `Server`. Deux circuits distincts remplacent le réseau :
    - `send` (hérité de `DefaultGame`, appelé par `attack`/`ping`/`request_state`
      et par `_handle_message`) : messages du joueur -> `GameLogic`, déposés
      dans `_pending_messages_game` et consommés par `_run` (équivalent de
      `Server._run` lisant `server.incoming_queue`).
    - `_game_send` / `_game_broadcast` (passés à `GameLogic.initialize`,
      équivalents de `server.send_to`/`server.broadcast`) : messages de
      `GameLogic` -> joueur, déposés dans `_pending_messages` et consommés par
      `DefaultGame.update()` via `_handle_message` (mise à jour de l'UI).
    """

    def __init__(self, screen, manager, name="Materwan"):
        super().__init__(screen, manager, name)

        self.running = True

        self.game_logic = GameLogic(self.name)
        self._game_thread: threading.Thread = None

        self._pending_messages_game: Queue[Dict[str, Any]] = Queue()

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(self):
        """Initialise la logique de jeu, connecte le joueur local, puis
        démarre la boucle de traitement, exactement comme `Server.start`."""

        self.game_logic.initialize(self._game_send, self._game_broadcast, 5)

        self._game_thread = threading.Thread(target=self._run, daemon=True)
        self._game_thread.start()

        # Équivalent local de la connexion réseau d'un client au serveur.
        self.game_logic._on_connect({"name": self.name})

        # Équivalent de `self.client.send({"type": "get_state"})` dans MultiGame.
        self.send({"type": "get_state"})
        # self.request_state()

    def close(self):

        self.running = False

    def close_connexion(self):
        """Pas de connexion réseau à fermer en solo : simple alias de `close`."""
        self.close()

    def _run(self):
        """Boucle principale de traitement des messages du joueur local.

        Variables locales utilisées :
        - sender, data : expéditeur et contenu du message lu depuis la file d'attente.
        """
        while self.running:
            try:
                sender, data = self._pending_messages_game.get(timeout=0.05)
                self.game_logic._handle_message(sender, data)
            except Empty:
                pass
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Envoi entre logique de jeu et affichage
    # ------------------------------------------------------------------

    def send(self, data: Dict[str, Any]):
        """Envoie un message du joueur local vers la logique de jeu.

        Remplace l'envoi réseau (`ClientNetwork.send`) : le message est
        simplement déposé dans la file traitée par `_run`, qui appelle
        `GameLogic._handle_message`, exactement comme le ferait le serveur
        en recevant un message d'un vrai client.
        """
        self._pending_messages_game.put((self.name, data))

    def _game_send(self, user_name: str, data: Dict[str, Any]):
        """Callback fourni à `GameLogic` (équivalent de `server.send_to`).

        Seul le joueur local dispose d'une file d'entrée ; les messages
        destinés aux bots sont ignorés, comme ils le seraient de toute façon
        côté serveur (aucun client réseau ne les reçoit).
        """
        if user_name == self.name:
            self._pending_messages.put(data)

    def _game_broadcast(self, data: Dict[str, Any]):
        """Callback fourni à `GameLogic` (équivalent de `server.broadcast`).

        Seul le joueur local est un client réel : il reçoit tous les
        messages diffusés.
        """
        self._pending_messages.put(data)
