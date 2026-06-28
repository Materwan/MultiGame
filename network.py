"""Module réseau : Server et Client.

Ce module fournit une implémentation de réseau hybride combinant:
    - Un serveur TCP pour la connexion durable au client
    - Une diffusion UDP pour la découverte automatique du client sur le réseau local

Il utilise un système de double tampon (back/front) avec détection de saleté
(`dirty`) pour synchroniser les états entre les boucles de jeu et le réseau,
tout en maintenant des performances O(1) lors des mises à jour.

"""

import asyncio
import socket
import threading
import json
import time
from typing import Dict, Any, Optional


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
        import time

        self._time = time
        self._samples: list = []
        self._window = window
        self._t0: Optional[float] = None
        self.average_ms: float = 0.0

    def start(self) -> float:
        self._t0 = self._time.perf_counter()
        return self._t0

    def stop(self):
        if self._t0 is None:
            return
        elapsed = (self._time.perf_counter() - self._t0) * 1000
        self._samples.append(elapsed)
        if len(self._samples) > self._window:
            self._samples.pop(0)
        self.average_ms = sum(self._samples) / len(self._samples)
        self._t0 = None


class ServerNetwork:
    """Classe représentant un serveur TCP pour la communication avec les clients."""

    def __init__(
        self, host: str, port: int, on_guest_connect: Optional[callable] = None
    ):
        self.host = host
        self.port = port
        self.on_guest_connect = on_guest_connect

        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._outgoing_back: Dict[str, Any] = {}
        self._outgoing_front: Dict[str, Any] = {}
        self._outgoing_dirty = False

        self._incoming_back: Dict[str, Any] = {}
        self._incoming_front: Dict[str, Any] = {}
        self._incoming_dirty = False

        # Attributs d'état correctement initialisés
        self._guest_rtt_ms: Optional[float] = None
        self._guest_ready: bool = False
        self._guest_disconnected: bool = False
        self._pending_reset: Optional[Dict[str, Any]] = None
        self._server: Optional[asyncio.AbstractServer] = None

        self._tcp_thread = threading.Thread(target=self._run_tcp, daemon=True)

    def close(self):
        """Signale l'arrêt propre des threads réseau."""
        self._stop_event.set()

    def update(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """Appelé par le game loop à 60 FPS — O(1), juste un swap de référence."""
        with self._lock:
            self._outgoing_back = game_state
            self._outgoing_dirty = True

            if self._incoming_dirty:
                self._incoming_front, self._incoming_back = (
                    self._incoming_back,
                    self._incoming_front,
                )
                self._incoming_dirty = False

                rtt = self._incoming_front.get("rtt_ms")
                if rtt is not None:
                    self._guest_rtt_ms = rtt

                return self._incoming_front

            return {}

    def _get_outgoing(self) -> Dict[str, Any]:
        with self._lock:
            if self._pending_reset is not None:
                packet = self._pending_reset
                self._pending_reset = None
                return packet

            if self._outgoing_dirty:
                self._outgoing_front, self._outgoing_back = (
                    self._outgoing_back,
                    self._outgoing_front,
                )
                self._outgoing_dirty = False
            return self._outgoing_front

    def _set_incoming(self, data: Dict[str, Any]):
        """CORRECTION : méthode dupliquée fusionnée en une seule."""
        with self._lock:
            self._incoming_back = data
            self._incoming_dirty = True

            if data.get("ready"):
                self._guest_ready = True

    def start(self):
        """Démarre le serveur et accepte les connexions des clients."""
        self._tcp_thread.start()

    def stop(self):
        """Arrête proprement le serveur."""
        self._stop_event.set()

    def _run_tcp(self):
        print("[Server] Starting TCP server...")
        asyncio.run(self._tcp_server())

    async def _tcp_server(self):
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
        print(
            f"\n[Server] New client trying to connect from {writer.get_extra_info('peername')}"
        )

        raw = await asyncio.wait_for(reader.readline(), timeout=100.0)
        if not raw:
            print(f"\n[Server] New client disconnected")
            self._guest_disconnected = True
            writer.close()
            await writer.wait_closed()
            return

        data = bytes_to_dict(raw)
        player_name = data.get("name", "No name")

        if self.on_guest_connect is not None:
            initial_state = self.on_guest_connect(data)
        else:
            initial_state = self._get_outgoing()

        writer.write(dict_to_bytes(initial_state))
        await writer.drain()

        print(
            f"[Server] Client {player_name} connected from {writer.get_extra_info('peername')}"
        )

        try:
            while not self._stop_event.is_set():
                raw = await asyncio.wait_for(reader.readline(), timeout=100.0)
                if not raw:
                    print(f"\n[Server] Client {player_name} disconnected")
                    self._guest_disconnected = True
                    break

                data = bytes_to_dict(raw)
                if data is None or data.get("close"):
                    print(f"\n[Server] Client {player_name} closed the connection")
                    self._guest_disconnected = True
                    break

                self._set_incoming(data)

                writer.write(dict_to_bytes(self._get_outgoing()))
                await writer.drain()

        except asyncio.TimeoutError:
            print(f"\n[Server] Timeout — client {player_name} unreachable")
            self._guest_disconnected = True
        except ConnectionResetError:
            print(f"\n[Server] Connection reset by client {player_name}")
            self._guest_disconnected = True
        finally:
            writer.close()
            await writer.wait_closed()  # CORRECTION : attendre la fermeture propre
            print(f"[Server] Connection closed with client {player_name}")
            # CORRECTION : on ne ferme plus self._server ici pour permettre
            # à d'autres clients de se connecter après déconnexion


class ClientNetwork:
    """Classe représentant un client TCP pour la communication avec le serveur."""

    def __init__(self, host: str, port: int, name: str):
        self.host = host
        self.port = port
        self.name = name

        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._outgoing_back: Dict[str, Any] = {}
        self._outgoing_front: Dict[str, Any] = {}
        self._outgoing_dirty = False

        self._incoming_back: Dict[str, Any] = {}
        self._incoming_front: Dict[str, Any] = {}
        self._incoming_dirty = False

        self._initial_state: Dict[str, Any] = {}

        # Attributs d'état correctement initialisés
        self._connected: bool = False
        self._loaded: bool = False
        self._is_ready: bool = False
        self._map_data: Optional[Dict[str, Any]] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._close_sent = threading.Event()

        self.rtt_tracker = RttTracker()  # CORRECTION : initialisé ici

        self._tcp_thread = threading.Thread(target=self._run, daemon=True)

    def close(self):
        """Signale l'arrêt propre du thread réseau."""
        self._stop_event.set()

    def update(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """Appelé par le game loop à 60 FPS — O(1), juste un swap de référence."""
        with self._lock:
            game_state["rtt_ms"] = self.rtt_tracker.average_ms

            self._outgoing_back = game_state
            self._outgoing_dirty = True

            if self._incoming_dirty:
                self._incoming_front, self._incoming_back = (
                    self._incoming_back,
                    self._incoming_front,
                )
                self._incoming_dirty = False
                return self._incoming_front

            return {}

    def _get_outgoing(self) -> Dict[str, Any]:
        """CORRECTION : méthode dupliquée fusionnée en une seule."""
        with self._lock:
            if self._outgoing_dirty:
                self._outgoing_front, self._outgoing_back = (
                    self._outgoing_back,
                    self._outgoing_front,
                )
                self._outgoing_dirty = False

            if self._is_ready:
                packet = dict(self._outgoing_front)
                packet["ready"] = True
                self._is_ready = False
                return packet

            return self._outgoing_front

    def _set_incoming(self, data: Dict[str, Any]):
        with self._lock:
            self._incoming_back = data
            self._incoming_dirty = True

    def _set_initial_state(self, data: Dict[str, Any]):
        """Définit l'état initial reçu du serveur."""
        with self._lock:
            self._initial_state = data

    def get_initial_state(self) -> Dict[str, Any]:
        """Retourne l'état initial reçu du serveur."""
        with self._lock:
            return self._initial_state

    def start(self):
        """Démarre le client et se connecte au serveur."""
        self._tcp_thread.start()

    def stop(self):
        """Arrête proprement le client."""
        self._stop_event.set()

    def _run(self):
        print(f"[Guest] Attempting connection to {self.host}:{self.port}...")
        asyncio.run(self._initialize())

    async def _initialize(self):
        """CORRECTION : appelle _connect avant _handle_host."""
        if not self._stop_event.is_set():
            await self._connect()
        if self._connected and not self._stop_event.is_set():
            await self._handle_host()

    async def _connect(self):
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port
            )

            self._writer.write(
                dict_to_bytes({"close": False, "type": "handshake", "name": self.name})
            )
            await self._writer.drain()

            # Réception du premier paquet (contient la map + état initial)
            raw = await self._reader.readline()
            data = bytes_to_dict(raw)
            if data is None or data.get("close"):
                self._stop_event.set()
                return

            self._set_initial_state(data)

            self._connected = True
            print(f"[Guest] Connected to {self.host}:{self.port}")

        except ConnectionRefusedError:
            print(f"[Guest] Connection refused — {self.host}:{self.port}")
            self._stop_event.set()
        except OSError as e:
            print(f"[Guest] Network error: {e}")
            self._stop_event.set()
        finally:
            self._loaded = True

    async def _handle_host(self):
        try:
            while not self._stop_event.is_set():
                snapshot = self._get_outgoing()
                self._writer.write(dict_to_bytes(snapshot))
                await self._writer.drain()
                if snapshot.get("close"):
                    self._close_sent.set()

                self.rtt_tracker.start()  # CORRECTION : horodatage avant attente

                raw = await asyncio.wait_for(self._reader.readline(), timeout=100.0)
                if not raw:
                    print("[Guest] Host closed the connection")
                    self._stop_event.set()
                    break

                self.rtt_tracker.stop()  # CORRECTION : calcul du RTT après réponse

                data = bytes_to_dict(raw)
                if data is None or data.get("close"):
                    print("[Guest] Host closed the connection")
                    self._stop_event.set()
                    break

                if data.get("reset"):
                    with self._lock:
                        self._map_data = data.get("map")

                self._set_incoming(data)

        except asyncio.TimeoutError:
            print("[Guest] Timeout — host unreachable")
            self._stop_event.set()
        except ConnectionResetError:
            print("[Guest] Connection reset by host")
            self._stop_event.set()
        finally:
            self._writer.close()
            await self._writer.wait_closed()  # CORRECTION : fermeture propre
            self._connected = False
            print("[Guest] Connexion fermée")
