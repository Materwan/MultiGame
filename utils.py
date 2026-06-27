import os
import sys
from typing import List, Tuple, Dict
from abc import ABC, abstractmethod

import pygame
from pygame._sdl2.video import Window

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

FULLSCREEN_SIZE = pygame.display.Info().current_w, pygame.display.Info().current_h
DEFAULTSCREENSIZE = FULLSCREEN_SIZE[0] // 2, FULLSCREEN_SIZE[1] // 2

DEFAULTSCREEN = pygame.display.set_mode(DEFAULTSCREENSIZE, pygame.RESIZABLE)

WINDOW = Window.from_display_module()


class BaseManager:

    def __init__(self, screen: pygame.Surface):

        self.screen = screen
        self.running = True

    def resize_screen(
        self, new_size: Tuple[int, int] | List[int] | None = FULLSCREEN_SIZE
    ):
        pass

    def run(self):
        pass


class DefaultState(ABC):
    screen: pygame.Surface

    def __init__(self, screen: pygame.Surface, manager: BaseManager):

        super().__init__()

        self.screen = screen
        self.manager = manager

    def event(self, events: List[pygame.event.Event]):
        """Gére les évenements : interactions du joueur avec l'interface."""

        for event in events:

            if event.type == pygame.QUIT:
                self.manager.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.manager.resize_screen()

            if event.type == pygame.VIDEORESIZE:
                self.manager.resize_screen(event.size)

    def update(self):
        """Met à jour les éléments de l'interface."""

    def display(self):
        """Affiche les éléments correspondant à l'interface."""

        self.screen.fill(BLACK)

        pygame.display.flip()
