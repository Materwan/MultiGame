import os
import sys
import random
import math
import socket
import time
from typing import List, Tuple, Dict, Any

import pygame

from client_utils import *
from menu import PrincipalMenu, SettingsMenu
from network import ClientNetwork


class Game(DefaultState):

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
        self.client = ClientNetwork(self.host, self.port, name)

    def start(self):
        self.client.start()

        time.sleep(0.5)  # Attendre un peu pour s'assurer que l'état initial est reçu

        self.neighbors = self.client.get_initial_state().get("neighbors", [])

    def close_connexion(self):
        self.client.close()

    def event(self, events: List[pygame.event.Event]):
        super().event(events)
        for event in events:
            pass  # Gérer les événements spécifiques au jeu ici

    def update(self):
        super().update()

    def display(self):

        self.screen.fill(BLACK)

        super().display()
