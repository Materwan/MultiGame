import os
import sys

import pygame

pygame.init()
pygame.display.init()
pygame.mixer.init()

from client_utils import *
from menu import PrincipalMenu, SettingsMenu
from game import Game


class Manager(BaseManager):

    def __init__(self, screen: pygame.Surface):

        # -- Pygame Elt --
        self.screen = screen
        self.screen_size = DEFAULTSCREENSIZE
        self.last_screen_size = DEFAULTSCREENSIZE
        self.last_screen_pos = (
            (FULLSCREEN_SIZE[0] - DEFAULTSCREENSIZE[0]) // 2,
            (FULLSCREEN_SIZE[1] - DEFAULTSCREENSIZE[1]) // 2,
        )
        self.clock = pygame.time.Clock()

        # -- Game Etl --
        self.running = True

        # -- State Manager --
        self.states: Dict[str, DefaultState] = {
            "Principal_Menu": PrincipalMenu(self.screen, self),
            "Settings_Menu": SettingsMenu(self.screen, self),
            "Game": Game(self.screen, self),
        }
        self.state = self.states.get("Principal_Menu", PrincipalMenu(self.screen, self))

    def change_state(self, new_state_name: str):
        """Change l'état actuel du jeu."""
        if new_state_name in self.states:
            if new_state_name == "Game":
                game_state = self.states["Game"]
                if isinstance(game_state, Game):
                    game_state.start()
            self.state = self.states[new_state_name]
        else:
            raise ValueError(
                f"L'état '{new_state_name}' n'existe pas dans le gestionnaire d'états."
            )

    def resize_screen(
        self, new_size: Tuple[int, int] | List[int] | None = FULLSCREEN_SIZE
    ):

        def change_screen(new_size: Tuple[int, int] | List[int]):
            self.screen = pygame.display.set_mode(
                new_size,
                (
                    pygame.NOFRAME | pygame.RESIZABLE
                    if new_size == FULLSCREEN_SIZE
                    else pygame.RESIZABLE
                ),
            )

        last_screen_size = self.screen.get_size()
        last_screen_pos = WINDOW.position

        if new_size == FULLSCREEN_SIZE:

            if self.screen_size != FULLSCREEN_SIZE:
                change_screen(FULLSCREEN_SIZE)
                WINDOW.position = (0, 0)
                self.screen_size = FULLSCREEN_SIZE
            else:
                change_screen(self.last_screen_size)
                WINDOW.position = self.last_screen_pos
                self.screen_size = DEFAULTSCREENSIZE

        else:
            # window_y = WINDOW.position[1]
            # size = new_size

            if new_size[0] < DEFAULTSCREENSIZE[0]:
                new_size = (DEFAULTSCREENSIZE[0], new_size[1])
            if new_size[1] < DEFAULTSCREENSIZE[1]:
                new_size = (new_size[0], DEFAULTSCREENSIZE[1])

            change_screen(new_size)
            # WINDOW.position = (WINDOW.position[0], window_y + size[1] - new_size[1])
            self.screen_size = new_size

        self.last_screen_size = last_screen_size
        self.last_screen_pos = last_screen_pos

    def run(self):

        while self.running:

            self.state.event(pygame.event.get())
            self.state.update()
            self.state.display()

            self.clock.tick(30)

        self.states[
            "Game"
        ].close_connexion()  # Fermer la connexion lorsque le jeu se termine


game = Manager(DEFAULTSCREEN)


try:
    game.run()
except KeyboardInterrupt:
    pygame.quit()

pygame.quit()
