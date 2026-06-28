"""Module réseau : Server et Client.

Ce module fournit une implémentation de réseau hybride combinant:
    - Un serveur TCP pour la connexion durable au client
    - Une diffusion UDP pour la découverte automatique du client sur le réseau local

Il utilise un registre de clients (name -> writer) côté serveur, ce qui permet
d'envoyer des données ciblées à un client spécifique via send_to(), ou à tous
via broadcast(). Les messages entrants sont placés dans une queue de tuples
(sender_name, data) que Server consomme dans sa boucle de jeu.

"""

import asyncio
import queue
import socket
import threading
import json
import time
from typing import Callable, Dict, Any, Optional, Tuple


def dict_to_bytes(data: Dict) -> bytes:
    """Transforme un dictionnaire en octets pour l'envoi."""
    return bytes(json.dumps(data) + "\n", "utf-8")


def bytes_to_dict(data: bytes) -> Optional[Dict]:
    """Décode les octets reçus en dictionnaire."""
    if not data:
        return None
    return json.loads(data.decode().strip())


class RttTracker:
    """Suit le round-trip time moyen sur une fenêtre glissante."""

    def __init__(self, window: int = 20):
        self._samples: list = []
        self._window = window
        self._t0: Optional[float] = None
        self.average_ms: float = 0.0
        self.last_ms: Optional[float] = None

    def start(self) -> float:
        self._t0 = time.perf_counter()
        return self._t0

    def stop(self):
        if self._t0 is None:
            return
        elapsed = (time.perf_counter() - self._t0) * 1000
        self.last_ms = elapsed
        self._samples.append(elapsed)
        if len(self._samples) > self._window:
            self._samples.pop(0)
        self.average_ms = sum(self._samples) / len(self._samples)
        self._t0 = None


class ServerNetwork:
    """Serveur TCP multi-clients.

    Chaque client connecté est enregistré dans `_clients` (name -> writer).
    Les messages entrants sont poussés dans `incoming_queue` sous la forme de
    tuples (sender_name, data) — la logique métier reste entièrement dans Server.

    API publique
    ------------
    send_to(name, data)   — envoie data au client `name` (thread-safe)
    broadcast(data)       — envoie data à tous les clients connectés (thread-safe)
    incoming_queue        — queue.Queue[(str, dict)] à consommer dans Server.update()
    connected_names()     — retourne la liste des noms actuellement connectés
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_guest_connect: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        on_guest_disconnect: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_guest_connect = on_guest_connect
        self.on_guest_disconnect = on_guest_disconnect

        # File de messages entrants : tuples (sender_name, data)
        self.incoming_queue: queue.Queue[Tuple[str, Dict[str, Any]]] = queue.Queue()

        # Registre des clients connectés (protégé par _lock)
        self._clients: Dict[str, asyncio.StreamWriter] = {}
        self._lock = threading.Lock()

        self._stop_event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[asyncio.AbstractServer] = None

        self._tcp_thread = threading.Thread(target=self._run_tcp, daemon=True)

    # ------------------------------------------------------------------
    # API publique — thread-safe, appelable depuis Server (thread PyGame)
    # ------------------------------------------------------------------

    def send_to(self, name: str, data: Dict[str, Any]):
        """Envoie `data` au client identifié par `name`. Thread-safe."""
        with self._lock:
            writer = self._clients.get(name)
        if writer is None or self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._async_write(writer, data), self._loop)

    def broadcast(self, data: Dict[str, Any], exclude: Optional[str] = None):
        """Envoie `data` à tous les clients connectés. Thread-safe.

        Parameters
        ----------
        exclude : str, optional
            Nom du client à exclure de la diffusion (ex: l'émetteur).
        """
        with self._lock:
            targets = {
                name: writer
                for name, writer in self._clients.items()
                if name != exclude
            }
        if self._loop is None:
            return
        for writer in targets.values():
            asyncio.run_coroutine_threadsafe(
                self._async_write(writer, data), self._loop
            )

    def connected_names(self):
        """Retourne la liste des noms de clients actuellement connectés."""
        with self._lock:
            return list(self._clients.keys())

    def start(self):
        """Démarre le serveur TCP dans son thread dédié."""
        self._tcp_thread.start()

    def close(self):
        """Signale l'arrêt propre du serveur."""
        self._stop_event.set()
        if self._loop and self._server:
            self._loop.call_soon_threadsafe(self._server.close)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _async_write(self, writer: asyncio.StreamWriter, data: Dict[str, Any]):
        """Coroutine d'écriture — s'exécute dans la boucle asyncio du serveur."""
        try:
            writer.write(dict_to_bytes(data))
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass  # Le client s'est déconnecté, _handle_client s'en chargera

    def _run_tcp(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._tcp_server())
        finally:
            self._loop.close()

    async def _tcp_server(self):
        print("[Server] Starting TCP server...")
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
            reuse_address=True,
        )
        print(f"[Server] TCP server started — {self.host}:{self.port}")
        async with self._server:
            try:
                await self._server.serve_forever()
            except asyncio.CancelledError:
                print("[Server] TCP server closed")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        peer = writer.get_extra_info("peername")
        print(f"\n[Server] New client connecting from {peer}")

        # --- Handshake initial ---
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=10.0)
        except asyncio.TimeoutError:
            print("[Server] Handshake timeout — closing connection")
            writer.close()
            return

        if not raw:
            print("[Server] Client disconnected before handshake")
            writer.close()
            return

        data = bytes_to_dict(raw)
        if data is None:
            writer.close()
            return

        player_name = data.get("name", f"Unknown_{peer}")

        # Appel du callback de connexion (ex: adjacent_list.add_user)
        if self.on_guest_connect is not None:
            initial_response = self.on_guest_connect(data)
        else:
            initial_response = {"type": "handshake"}

        # Enregistrement du client dans le registre
        with self._lock:
            self._clients[player_name] = writer

        # Envoi de la réponse initiale
        await self._async_write(writer, initial_response)
        print(f"[Server] Client '{player_name}' connected from {peer}")

        # --- Boucle de réception ---
        try:
            while not self._stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(reader.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout normal — continue la boucle pour vérifier _stop_event
                    continue

                if not raw:
                    print(f"[Server] Client '{player_name}' disconnected")
                    break

                incoming = bytes_to_dict(raw)
                if incoming is None or incoming.get("close"):
                    print(f"[Server] Client '{player_name}' closed the connection")
                    break

                if data.get("type") == "close":
                    break

                # Pousse le message dans la queue avec l'identité de l'émetteur
                self.incoming_queue.put((player_name, incoming))

        except ConnectionResetError:
            print(f"[Server] Connection reset by '{player_name}'")
        finally:
            with self._lock:
                self._clients.pop(player_name, None)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass  # Connexion déjà fermée ou erreur réseau
            print(f"[Server] Connection closed with '{player_name}'")
            if self.on_guest_disconnect is not None:
                self.on_guest_disconnect(player_name)


class ClientNetwork:
    """Client TCP symétrique à ServerNetwork.

    Les messages entrants (depuis le serveur) sont poussés dans `incoming_queue`
    sous forme de dicts bruts — Game les consomme dans sa propre boucle via
    `_handle_message`. L'envoi vers le serveur se fait via `send(data)`.

    API publique
    ------------
    send(data)          — envoie data au serveur (thread-safe)
    incoming_queue      — queue.Queue[dict] à consommer dans Game._run()
    initial_state       — dict reçu lors du handshake (voisins, etc.)
    connected           — bool, True si la connexion est établie
    rtt_tracker         — RttTracker pour mesurer la latence
    """

    def __init__(self, host: str, port: int, name: str):
        self.host = host
        self.port = port
        self.name = name

        # File de messages entrants depuis le serveur
        self.incoming_queue: queue.Queue[Dict[str, Any]] = queue.Queue()

        self.initial_state: Dict[str, Any] = {}
        self.connected: bool = False
        self.rtt_tracker = RttTracker()

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        self._tcp_thread = threading.Thread(target=self._run_tcp, daemon=True)

    # ------------------------------------------------------------------
    # API publique — thread-safe, appelable depuis Game (thread PyGame)
    # ------------------------------------------------------------------

    def send(self, data: Dict[str, Any]):
        """Envoie `data` au serveur. Thread-safe."""
        with self._lock:
            writer = self._writer
        if writer is None or self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._async_write(writer, data), self._loop)

    def start(self):
        """Démarre le thread réseau et se connecte au serveur."""
        self._tcp_thread.start()

    def close(self):
        """Signale l'arrêt propre du thread réseau."""
        self._stop_event.set()
        self.send({"type": "close"})
        # Ne pas arrêter la boucle directement — laisser _connect() se terminer naturellement

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _async_write(self, writer: asyncio.StreamWriter, data: Dict[str, Any]):
        try:
            writer.write(dict_to_bytes(data))
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def _run_tcp(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        print(f"[Guest] Attempting connection to {self.host}:{self.port}...")
        try:
            self._loop.run_until_complete(self._connect())
        except RuntimeError:
            # Event loop fermée ou interrompue proprement
            pass
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _connect(self):
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except ConnectionRefusedError:
            print(f"[Guest] Connection refused — {self.host}:{self.port}")
            return
        except OSError as e:
            print(f"[Guest] Network error: {e}")
            return

        with self._lock:
            self._writer = writer

        # Handshake
        await self._async_write(writer, {"type": "handshake", "name": self.name})

        raw = await reader.readline()
        data = bytes_to_dict(raw)
        if data is None:
            print("[Guest] Invalid handshake response")
            writer.close()
            return

        self.initial_state = data
        self.connected = True
        print(f"[Guest] Connected to {self.host}:{self.port}")
        print(f"[Guest] Initial state: {data}")

        await self._receive_loop(reader, writer)

    async def _receive_loop(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Écoute en continu les messages du serveur et les pousse dans incoming_queue."""
        try:
            while not self._stop_event.is_set():
                self.rtt_tracker.start()
                try:
                    raw = await asyncio.wait_for(reader.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout normal — continue la boucle pour vérifier _stop_event
                    continue

                if not raw:
                    print("[Guest] Server closed the connection")
                    break

                self.rtt_tracker.stop()

                data = bytes_to_dict(raw)
                if data is None or data.get("close"):
                    print("[Guest] Server closed the connection")
                    break

                if data.get("type") == "ping":
                    # Répond immédiatement au ping serveur au niveau du réseau
                    self.send(
                        {
                            "type": "pong",
                            "timestamp": data.get("timestamp", time.time()),
                        }
                    )
                    continue

                if data.get("type") == "close":
                    self.close()
                    break

                self.incoming_queue.put(data)

        except ConnectionResetError:
            print("[Guest] Connection reset by server")
        finally:
            with self._lock:
                self._writer = None
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass  # Connexion déjà fermée ou erreur réseau
            self.connected = False
            print("[Guest] Connection closed")
