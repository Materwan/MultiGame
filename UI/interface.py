import math
import random
from typing import Dict, List, Optional, Tuple, Any
from UI.button import CloseButton

import pygame
from utils import *
from UI.ui_utils import *
from UI.window import WindowManager
from UI.graph import Graph, Node


class TaskBar:

    TASK_BAR_WIDTH = 20
    HOVER_INDICATOR_WIDTH = 10
    HOVER_INDICATOR_HEIGHTS = (50, 30)
    CLOSED_FONT_SIZE = 12
    HOVERED_FONT_SIZE = 18

    def __init__(self, screen: pygame.Surface):

        self.screen = screen

        self.hover = False

    @property
    def hovered_task_bar_points(self):
        screen_w, screen_h = self.screen.get_size()
        return [
            (0, 0),
            (self.TASK_BAR_WIDTH, 0),
            (self.TASK_BAR_WIDTH, screen_h // 2 - self.HOVER_INDICATOR_HEIGHTS[0]),
            (
                self.TASK_BAR_WIDTH + self.HOVER_INDICATOR_WIDTH,
                screen_h // 2 - self.HOVER_INDICATOR_HEIGHTS[1],
            ),
            (
                self.TASK_BAR_WIDTH + self.HOVER_INDICATOR_WIDTH,
                screen_h // 2 + self.HOVER_INDICATOR_HEIGHTS[1],
            ),
            (self.TASK_BAR_WIDTH, screen_h // 2 + self.HOVER_INDICATOR_HEIGHTS[0]),
            (self.TASK_BAR_WIDTH, screen_h),
            (0, screen_h),
        ]

    def _handle_event(self, events: List[pygame.event.Event]):

        mouse_x, mouse_y = pygame.mouse.get_pos()

        if self.hover:
            if not point_in_polygon((mouse_x, mouse_y), self.hovered_task_bar_points):
                self.hover = False
        elif mouse_x < 20 and mouse_x > 0:
            self.hover = True
        else:
            self.hover = False

    def draw(self):

        screen_w, screen_h = self.screen.get_size()

        if self.hover:

            _font = pygame.font.SysFont(UITheme.FONT_NAME, self.HOVERED_FONT_SIZE)

            points = self.hovered_task_bar_points
            pygame.draw.polygon(self.screen, UITheme.BLACK, points)
            pygame.draw.lines(self.screen, UITheme.GREEN, False, points[1:-1])
            self.screen.blit(
                _font.render("->", False, UITheme.GREEN),
                (self.HOVER_INDICATOR_WIDTH // 2, (screen_h - _font.get_height()) // 2),
            )

        else:

            _font = pygame.font.SysFont(UITheme.FONT_NAME, self.CLOSED_FONT_SIZE)

            pygame.draw.rect(
                self.screen,
                UITheme.BLACK,
                pygame.Rect(0, 0, 20, screen_h),
            )
            pygame.draw.line(self.screen, UITheme.GREEN, (20, 0), (20, screen_h))
            self.screen.blit(
                _font.render("...", False, UITheme.GREEN),
                (0, (screen_h - _font.get_height()) // 2),
            )


class Interface:
    """Point d'entrée de l'interface graphique du graphe interactif."""

    ZOOM_MIN = 0.5
    ZOOM_MAX = 5.0
    ZOOM_STEP = 0.1
    ZOOM_FACTOR = 1.1

    def __init__(
        self,
        screen: pygame.Surface,
        user_states: UserStates,
        self_name: str | None = None,
    ):

        self.screen = screen

        self.user_states = user_states
        self._build_graph(self.user_states, self_name)
        self.windows_manager = WindowManager(self.screen)
        self.task_bar = TaskBar(self.screen)

        self.zoom: float = 1.0
        self.offset_x: float = self.screen.get_size()[0] / 2
        self.offset_y: float = self.screen.get_size()[1] / 2
        self.offset = pygame.Vector2(self.offset_x, self.offset_y)

        self._dragging: bool = False
        self._drag_start_mouse: pygame.Vector2 = pygame.Vector2(0, 0)
        self._drag_start_offset: pygame.Vector2 = pygame.Vector2(0, 0)

    def _build_graph(
        self,
        user_states: UserStates,
        self_name: str | None = None,
    ):
        """Construit le graphe graphique et attache les callbacks de clic aux nœuds."""

        self.graph = Graph(self.screen, user_states, self_name)

        for node in self.graph.nodes:
            node.on_click = self._on_node_click

    def _on_node_click(self, node: "Node"):
        """Ouvre une fenêtre d'information pour le nœud cliqué."""
        try:
            data = self.get_user_info(node.name)
        except (AttributeError, KeyError):
            return

        # Position de la fenêtre légèrement décalée par rapport au nœud (coords monde)
        win_x = node.pos.x + 20
        win_y = node.pos.y + 20

        self.windows_manager.add_node_info_window(
            self.screen, (win_x, win_y), data, title=node.name
        )

    def get_user_info(self, user_name: str):
        """Retourne les informations d'un utilisateur depuis les données de l'interface."""
        return self.user_states.get_resources(user_name)

    def sync(self):
        """Met à jour l'interface existante en place, sans la reconstruire.

        Délègue la mise à jour des nœuds/liens à `Graph.sync`, qui conserve
        les nœuds déjà existants (position, drag, hover...), et ferme les
        fenêtres d'info des joueurs qui ont quitté la partie.
        """
        self.graph.sync()
        for node in self.graph.nodes:
            node.on_click = self._on_node_click
        # self.windows_manager.remove_windows_for(removed)

    def event(self, events: List[pygame.event.Event]):
        """Traite les événements de la souris, du zoom et du déplacement de la caméra."""

        ms_pos = pygame.mouse.get_pos()

        self.graph._handle_event(events, ms_pos, self.offset, self.zoom)
        self.windows_manager._handle_event(events, ms_pos, self.offset, self.zoom)
        self.task_bar._handle_event(events)

        if not self.windows_manager.is_hover:
            for event in events:

                # Zoom à la molette, centré sur la position du curseur
                if event.type == pygame.MOUSEWHEEL:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    mouse_pos = pygame.Vector2(mouse_x, mouse_y)

                    old_zoom = self.zoom
                    self.zoom *= self.ZOOM_FACTOR**event.y
                    self.zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self.zoom))

                    # Ajuste l'offset pour zoomer vers le curseur
                    scale_change = self.zoom / old_zoom
                    self.offset = mouse_pos + (self.offset - mouse_pos) * scale_change

                # Début du pan
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._dragging = True
                    self._drag_start_mouse = pygame.Vector2(pygame.mouse.get_pos())
                    self._drag_start_offset = pygame.Vector2(self.offset)

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._dragging = False

                # Déplacement pendant le pan
                elif (
                    event.type == pygame.MOUSEMOTION
                    and self._dragging
                    and not self.graph.is_dragging
                    and not self.windows_manager.is_dragging
                ):
                    current_mouse = pygame.Vector2(pygame.mouse.get_pos())
                    delta = current_mouse - self._drag_start_mouse
                    self.offset = self._drag_start_offset + delta

    def update(self):
        """Met à jour le graphe affiché."""

        self.graph.update(self.offset, self.zoom)

    def _draw_grid(self):
        """Dessine la grille de fond adaptée au niveau de zoom actuel."""
        width, height = self.screen.get_size()

        base_spacing_px = 50
        raw_spacing = base_spacing_px / max(self.zoom, 0.001)
        magnitude = 10 ** math.floor(math.log10(raw_spacing))
        normalized = raw_spacing / magnitude

        if normalized < 1.5:
            step = 1
        elif normalized < 3:
            step = 2
        elif normalized < 7:
            step = 5
        else:
            step = 10

        spacing = max(10, int(magnitude * step))

        min_x = int(math.floor((-self.offset.x) / self.zoom / spacing)) * spacing
        max_x = int(math.ceil((width - self.offset.x) / self.zoom / spacing)) * spacing
        min_y = int(math.floor((-self.offset.y) / self.zoom / spacing)) * spacing
        max_y = int(math.ceil((height - self.offset.y) / self.zoom / spacing)) * spacing

        for x in range(min_x, max_x + spacing, spacing):
            screen_x = world_to_screen(pygame.Vector2(x, 0), self.offset, self.zoom).x
            if 0 <= screen_x <= width:
                pygame.draw.line(
                    self.screen, UITheme.GRID_COLOR, (screen_x, 0), (screen_x, height)
                )

        for y in range(min_y, max_y + spacing, spacing):
            screen_y = world_to_screen(pygame.Vector2(0, y), self.offset, self.zoom).y
            if 0 <= screen_y <= height:
                pygame.draw.line(
                    self.screen, UITheme.GRID_COLOR, (0, screen_y), (width, screen_y)
                )

    def draw(self, clock: pygame.time.Clock):
        """Dessine la grille, le graphe et les fenêtres ouvertes."""

        self._draw_grid()
        self.graph.draw(self.offset, self.zoom)
        self.windows_manager.draw(self.offset, self.zoom)
        self.task_bar.draw()

        t_sr = pygame.Surface((300, 100), pygame.SRCALPHA)
        _font = pygame.font.SysFont(UITheme.FONT_NAME, 20)
        t_sr.blit(
            _font.render(
                f"FPS: {int(clock.get_fps())}, Zoom: {round(self.zoom, 1)}",
                False,
                UITheme.GREEN,
            ),
            (0, 0),
        )
        self.screen.blit(t_sr, (20, 0))


if __name__ == "__main__":

    user_states = UserStates("user_1")
    user_states.add_multiple_users(
        ["user_1", "user_2", "user_3", "user_4"],
        [
            ["user_2", "user_3", "user_4"],
            ["user_1", "user_3"],
            ["user_1", "user_2", "user_4"],
            ["user_1", "user_3"],
        ],
        [
            {"cpu": 10, "ram": 10},
            {"cpu": 8, "ram": 6},
            {"cpu": 7, "ram": 9},
            {"cpu": 6, "ram": 5},
        ],
    )

    class Game:

        def __init__(self, screen: pygame.Surface):

            self.screen = screen
            self.clock = pygame.time.Clock()
            self.running = True

            self.interface = Interface(self.screen, user_states, "user_1")
            self.interface.user_data = {
                name: {"CPU": 10, "RAM": 10} for name in user_states.user_names
            }

        def event(self):

            events = pygame.event.get()

            for event in events:

                if event.type == pygame.QUIT:
                    self.running = False

            self.interface.event(events)

        def update(self):

            self.interface.update()

        def display(self):

            self.screen.fill(UITheme.BLACK)

            self.interface.draw()

            pygame.display.flip()

        def run(self):

            while self.running:

                self.event()
                self.update()
                self.display()

                self.clock.tick(60)

    pygame.init()

    screen = pygame.display.set_mode((920, 580))

    Game(screen).run()

    pygame.quit()
