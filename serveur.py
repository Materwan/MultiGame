import threading
import socket
import time
import traceback
from queue import Empty, Queue
from typing import List, Tuple, Dict, Any, Callable

import pygame

from network import ServerNetwork
from server_utils import *
from UI.interface import Interface

from pygame._sdl2.video import Window


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
        self.game_logic = GameLogic()

        self.visual = visual

        self.running = True

        self.server = ServerNetwork(
            host,
            port,
            on_guest_connect=self.game_logic._on_connect,
            on_guest_disconnect=self.game_logic._on_disconnect,
        )
        self._server_thread = threading.Thread(target=self._run, daemon=True)
        self._stdin_thread = threading.Thread(target=self._read_stdin, daemon=True)

        self._stdin_queue: Queue[str] = Queue()

        self._stdin_thread.start()

    def _run(self):
        """Boucle principale de réception des messages réseau entrants.

        Variables locales utilisées :
        - sender, data : expéditeur et contenu du message lu depuis la file d'attente.
        """
        while self.running:
            try:
                sender, data = self.server.incoming_queue.get(timeout=0.05)
                self.game_logic._handle_message(sender, data)
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

        self.game_logic.initialize(self.server.send_to, self.server.broadcast, 5)

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
                    self.game_logic.user_states.display_matrix()
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
                    self.game_logic.send(command[1], payload)
                    print(f"\nPing sent to {command[1]}")
                elif command[1] == "all":
                    self.game_logic.broadcast(payload)
                    print("\nPing sent to all connected clients")
                else:
                    print(f"\n'{command[1]}' is not a connected client")
            else:
                print("Usage: ping <player_name> | all")

        def _handle_visual(command: List[str]):
            if self.visual.running:
                print("\nVisual interface already running.")
            else:
                self.visual.trigger(self.game_logic.user_states)

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
                for message in self.game_logic.logs[-int(number) :]:
                    print(format_log(message, tag))
            else:
                print("\nUsage: log [option] [n] (n >= 1)")

        def _handle_generate(command: List[str]):
            number = 1
            if len(command) > 1:
                if command[1].isdigit():
                    number = int(command[1])
            for _ in range(number):
                new_bot_name = f"User {len(self.game_logic.user_states.user_names)}"
                self.game_logic._on_connect({"name": new_bot_name})
                self.game_logic._bots.append(new_bot_name)

        def _handle_exec(command: List[str]):
            if len(command) > 1:
                code_str = " ".join(command[1:])
                try:
                    # Contexte local avec accès à `self`
                    local_vars = {
                        "self": self,
                        "user_states": self.game_logic.user_states,
                    }
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

        self.FULLSCREEN_SIZE: Tuple[int, int] = None
        self.DEFAULTSCREENSIZE: Tuple[int, int] = None
        self.WINDOW: Window = None

        self.screen_size: Tuple[int, int] = None
        self.last_screen_size: Tuple[int, int] = None
        self.last_screen_pos: Tuple[int, int] = None

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
                self.interface.graph.adjacent_list = (
                    self.user_stats.get_adjacent_matrix()
                )

        self.interface.user_data = {
            name: {"CPU": 10, "RAM": 10} for name in self.user_stats.user_names
        }

    def resize_screen(self, new_size: Tuple[int, int] | List[int] | None = None):

        if new_size is None:
            new_size = self.FULLSCREEN_SIZE

        def change_screen(new_size: Tuple[int, int] | List[int]):
            self.screen = pygame.display.set_mode(
                new_size,
                (
                    pygame.NOFRAME | pygame.RESIZABLE
                    if new_size == self.FULLSCREEN_SIZE
                    else pygame.RESIZABLE
                ),
            )

        last_screen_size = self.screen.get_size()
        last_screen_pos = self.WINDOW.position

        if new_size == self.FULLSCREEN_SIZE:

            if self.screen_size != self.FULLSCREEN_SIZE:
                change_screen(self.FULLSCREEN_SIZE)
                self.WINDOW.position = (0, 0)
                self.screen_size = self.FULLSCREEN_SIZE
            else:
                change_screen(self.last_screen_size)
                self.WINDOW.position = self.last_screen_pos
                self.screen_size = self.DEFAULTSCREENSIZE

        else:
            # window_y = WINDOW.position[1]
            # size = new_size

            if new_size[0] < self.DEFAULTSCREENSIZE[0]:
                new_size = (self.DEFAULTSCREENSIZE[0], new_size[1])
            if new_size[1] < self.DEFAULTSCREENSIZE[1]:
                new_size = (new_size[0], self.DEFAULTSCREENSIZE[1])

            change_screen(new_size)
            # WINDOW.position = (WINDOW.position[0], window_y + size[1] - new_size[1])
            self.screen_size = new_size

        self.last_screen_size = last_screen_size
        self.last_screen_pos = last_screen_pos

    def event(self):
        """Gére les évenements : interactions du joueur avec l'interface."""

        events = pygame.event.get()

        for event in events:

            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.resize_screen()

            if event.type == pygame.VIDEORESIZE:
                self.resize_screen(event.size)

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

        self.FULLSCREEN_SIZE = (
            pygame.display.Info().current_w,
            pygame.display.Info().current_h,
        )
        self.DEFAULTSCREENSIZE = (
            self.FULLSCREEN_SIZE[0] // 2,
            self.FULLSCREEN_SIZE[1] // 2,
        )

        self.screen = pygame.display.set_mode(
            self.DEFAULTSCREENSIZE, flags=pygame.RESIZABLE
        )

        self.screen_size = self.DEFAULTSCREENSIZE
        self.last_screen_size = self.DEFAULTSCREENSIZE
        self.last_screen_pos = (
            (self.FULLSCREEN_SIZE[0] - self.DEFAULTSCREENSIZE[0]) // 2,
            (self.FULLSCREEN_SIZE[1] - self.DEFAULTSCREENSIZE[1]) // 2,
        )

        self.WINDOW = Window.from_display_module()

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
    except Exception as e:
        print(f"\n[Server] Crash :{e}")
        traceback.print_exc()
        server.close()
        while server.server._tcp_thread.is_alive():
            time.sleep(0.05)
        print("\n[Server] Server shutdown...")
    else:
        print("\n[Server] Server shutdown...")
