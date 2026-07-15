import pygame
from typing import List, Tuple, Dict, Any
import random
import numpy as np

from UI.ui_utils import *
from UI.button import *


class Window(DefaultUIElt):
    """Class for a draggable and resizable interface window in the world.

    Variables:
        - screen (Surface): the surface on which draw the window.
        - position (Vector2): the world position of the window.
        - size (Tuple[int, int]): the size of the window.
        - title (str): the title displayed in the title bar.
        - _dragging (bool): indicate if the window is currently being dragged.
        - _close_hover (bool): indicate if the close button is hovered.

    Methodes:
        - _get_screen_rects(Vector2, float): calculate the rendered rectangles for the window and its elements.
        - _get_borders(): compute the outer and inner border points of the window.
        - _get_window_elt(Vector2, float): convert border points to screen coordinates.
        - corner_handle_event(List[Event], Vector2, float): manage drag interactions and close button hover state.
        - blit(Vector2, float): draw the full window with its title bar and close button.
    """

    BORDER_CORNER = 10
    BORDER_GAP = 10
    TITLE_BAR_HEIGHT = BORDER_CORNER + BORDER_GAP
    TITLE_BAR_COLOR = (30, 34, 48)
    TITLE_BAR_BORDER_COLOR = (70, 80, 110)
    BODY_COLOR = (16, 18, 28)
    BODY_BORDER_COLOR = (50, 58, 90)
    TITLE_COLOR = (180, 190, 220)
    CLOSE_BUTTON_COLOR = (180, 60, 60)
    CLOSE_BUTTON_HOVER_COLOR = (220, 80, 80)
    TOP_BAR_COLOR = (0, 100, 0)
    BASE_TITLE_FONT_SIZE = 14
    BASE_FONT_SIZE = 10

    def __init__(
        self,
        screen: pygame.Surface,
        position: List[int] | Tuple[int, int],
        size: List[int] | Tuple[int, int],
        close_fn: Callable = None,
        window_title: str = "Window",
        title: str = "Empty",
    ):
        """Initialise la fenêtre avec sa position, sa taille et son titre."""

        self.screen = screen
        self.close_fn = close_fn

        # -- Window (world coordinates) --
        self.position = pygame.Vector2(position)
        self.size = to_vect(size)

        # -- Titles --
        self.window_title = window_title
        self.title = title
        self._base_font_size = 12

        # -- Dragging state --
        self._dragging = False
        self._drag_start_mouse = pygame.Vector2(0, 0)
        self._drag_start_pos = pygame.Vector2(self.position)
        self.hover = False

        # -- Buttons --
        self._button_offsets: List[pygame.Vector2] = [
            pygame.Vector2(self.size[0] - 20, 10),
        ]
        self.buttons: List[DefaultButton] = [
            CloseButton(
                self.screen,
                self.position + self._button_offsets[0],
                8,
                click_fn=self.close_fn,
                click_args=(self,),
            ),
        ]

    @property
    def hover_button(self):
        return any([button.hover for button in self.buttons])

    def _get_world_borders(self, corner=BORDER_CORNER, gap=BORDER_GAP):

        world_outer_border = [
            (corner, 0),
            (self.size[0] * 0.5, 0),
            (
                self.size[0] * 0.5 + corner // 2,
                corner // 2,
            ),
            (
                self.size[0] * 0.75 - corner // 2,
                corner // 2,
            ),
            (self.size[0] * 0.75, 0),
            (self.size[0] - corner, 0),
            (self.size[0], corner),
            (self.size[0], self.size[1] - corner),
            (self.size[0] - corner, self.size[1]),
            (corner, self.size[1]),
            (0, self.size[1] - corner),
            (0, corner),
        ]

        world_inner_border = [
            (corner + gap, gap * 2),
            (self.size[0] * 0.5, gap * 2),
            (
                self.size[0] * 0.5 + corner // 2,
                gap * 2 - corner // 2,
            ),
            (
                self.size[0] * 0.75 - corner // 2,
                gap * 2 - corner // 2,
            ),
            (self.size[0] * 0.75, gap * 2),
            (self.size[0] - corner - gap, gap * 2),
            (self.size[0] - gap, corner + gap * 2),
            (self.size[0] - gap, self.size[1] - corner - gap),
            (self.size[0] - corner - gap, self.size[1] - gap),
            (corner + gap, self.size[1] - gap),
            (gap, self.size[1] - corner - gap),
            (gap, corner + gap * 2),
        ]

        return np.array(world_outer_border) + np.array(self.position), np.array(
            world_inner_border
        ) + np.array(self.position)

    def _get_world_title_bar_border(self, corner=BORDER_CORNER, gap=BORDER_GAP):

        border = [
            (corner, 0),
            (self.size[0] * 0.5, 0),
            (
                self.size[0] * 0.5 + corner // 2,
                corner // 2,
            ),
            (
                self.size[0] * 0.75 - corner // 2,
                corner // 2,
            ),
            (self.size[0] * 0.75, 0),
            (self.size[0] - corner, 0),
            (self.size[0], corner),
            (self.size[0], gap * 2),
            (self.size[0] * 0.75, gap * 2),
            (
                self.size[0] * 0.75 - corner // 2,
                gap * 2 - corner // 2,
            ),
            (
                self.size[0] * 0.5 + corner // 2,
                gap * 2 - corner // 2,
            ),
            (self.size[0] * 0.5, gap * 2),
            (0, gap * 2),
            (0, corner),
        ]

        return np.array(border) + np.array(self.position)

    def _get_world_window_title_pos(self, corner=BORDER_CORNER, gap=BORDER_GAP):

        pos = (corner // 2, corner // 2)

        return np.array(pos) + np.array(self.position)

    def _get_world_title_pos(self, corner=BORDER_CORNER, gap=BORDER_GAP):

        pos = (int(corner * 1.5), int(corner + gap * 2))

        return np.array(pos) + np.array(self.position)

    def _get_world_text_pos(self, corner=BORDER_CORNER, gap=BORDER_GAP):

        pos = (
            int(corner * 1.5),
            int(corner + gap * 2 + self.BASE_TITLE_FONT_SIZE + 1),
        )

        return np.array(pos) + np.array(self.position)

    def _sync_buttons(self):
        """Recalcule la position absolue des boutons à partir de la position de la fenêtre."""
        for index in range(len(self.buttons)):
            self.buttons[index].pos = self.position + self._button_offsets[index]

    def _handle_event(
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = pygame.Vector2(0, 0),
        zoom: Optional[float] = 1,
    ):
        """Gère les interactions de souris pour le déplacement et l'état du bouton fermer."""

        ms_pos = pygame.Vector2(pygame.mouse.get_pos())

        self._sync_buttons()

        world_outer_border, _ = self._get_world_borders()
        outer_border = world_to_screen_polygon(world_outer_border, offset, zoom)
        world_title_bar_border = self._get_world_title_bar_border()
        title_bar_border = world_to_screen_polygon(world_title_bar_border, offset, zoom)

        if self._dragging or point_in_polygon(ms_pos, outer_border):
            self.hover = True
            for event in events:

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if (
                        point_in_polygon(ms_pos, title_bar_border)
                        and not self.hover_button
                    ):
                        self._dragging = True
                        self._drag_start_mouse = pygame.Vector2(event.pos)
                        self._drag_start_pos = pygame.Vector2(self.position)

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._dragging = False

                elif event.type == pygame.MOUSEMOTION and self._dragging:
                    current_mouse = pygame.Vector2(event.pos)
                    delta = current_mouse - self._drag_start_mouse
                    self.position = self._drag_start_pos + pygame.Vector2(
                        delta.x / zoom, delta.y / zoom
                    )

            for button in self.buttons:
                button._handle_event(events, ms_pos, offset, zoom)

        else:
            self.hover = False

            for button in self.buttons:
                button.hover = False

    def draw(self, offset: pygame.Vector2, zoom: float):
        """Dessine la fenêtre complète avec sa barre de titre et son bouton de fermeture."""
        self._sync_buttons()

        # -- Border --
        world_outer_border, world_inner_border = self._get_world_borders()
        outer_border = world_to_screen_polygon(world_outer_border, offset, zoom)
        inner_border = world_to_screen_polygon(world_inner_border, offset, zoom)

        pygame.draw.polygon(self.screen, UITheme.BLACK, outer_border)
        pygame.draw.lines(self.screen, UITheme.GREEN, True, outer_border)
        pygame.draw.lines(self.screen, self.TOP_BAR_COLOR, True, inner_border)

        # -- Buttons --
        for button in self.buttons:
            button.draw(offset, zoom)

        # -- Titles --
        world_window_title_pos = self._get_world_window_title_pos()
        world_title_pos = self._get_world_title_pos()
        window_title_pos = world_to_screen(world_window_title_pos, offset, zoom)
        title_pos = world_to_screen(world_title_pos, offset, zoom)

        _title_font_size = max(5, int(self.BASE_TITLE_FONT_SIZE * zoom))
        _title_font = pygame.font.SysFont(UITheme.FONT_NAME, _title_font_size, True)

        self.screen.blit(
            _title_font.render(self.window_title, False, UITheme.GREEN),
            window_title_pos,
        )

        self.screen.blit(
            _title_font.render(self.title, False, UITheme.GREEN),
            title_pos,
        )


class NodeInfoWindow(Window):
    """Class for a window displaying information related to a graph node.

    Variables:
        - screen (Surface): the surface on which draw the window.
        - position (Vector2): the world position of the window.
        - data (Dict[str, Any]): the data to display inside the window.
        - title (str): the title displayed in the title bar.

    Methodes:
        - draw(Vector2, float): draw the full window with the data.
    """

    def __init__(
        self,
        screen,
        position,
        data: Dict[str, Any],
        close_fn: Callable,
        attack_fn: Callable,
        title: str = "Empty",
    ):
        """Initialise la fenêtre avec les informations à afficher."""
        super().__init__(
            screen,
            position,
            (200, 300),
            close_fn,
            "> User Info",
            title,
        )

        self.data = data

        self._button_offsets.append(pygame.Vector2(int(self.BORDER_GAP * 1.5), 100))
        self.buttons.append(
            SimpleSquareButton(
                self.screen,
                self._button_offsets[-1],
                (
                    self.size.x - self.BORDER_GAP * 3,
                    self.BORDER_GAP * 2,
                ),
                "Test",
                12,
                click_fn=attack_fn,
                click_args=(self.position + pygame.Vector2(20, 20), title),
            )
        )

    def draw(self, offset, zoom):
        """Dessine la fenêtre puis affiche les données textuelles du nœud."""
        super().draw(offset, zoom)

        world_text_pos = self._get_world_text_pos()
        text_pos = world_to_screen(world_text_pos, offset, zoom)

        # -- Data --
        font_size = int(self.BASE_FONT_SIZE * zoom)
        _data_font = pygame.font.SysFont(UITheme.FONT_NAME, font_size)

        # -- Text --
        self.screen.blit(
            _data_font.render(f"CPU : {self.data['CPU']}", False, UITheme.GREEN),
            text_pos,
        )
        text_pos = (text_pos[0], text_pos[1] + _data_font.get_linesize())
        self.screen.blit(
            _data_font.render(f"RAM : {self.data['RAM']}", False, UITheme.GREEN),
            text_pos,
        )


class AttackWindow(Window):

    def __init__(self, screen, position, size, close_fn, title="Window"):
        super().__init__(screen, position, size, close_fn, "> Attack", title)

    def draw(self, offset, zoom):
        """Dessine la fenêtre puis affiche les données textuelles du nœud."""
        super().draw(offset, zoom)

        # -- Text --
        world_text_pos = self._get_world_text_pos()
        text_pos = world_to_screen(world_text_pos, offset, zoom)

        font_size = int(self.BASE_FONT_SIZE * zoom)
        _data_font = pygame.font.SysFont(UITheme.FONT_NAME, font_size)

        self.screen.blit(
            _data_font.render("Test", False, UITheme.GREEN),
            text_pos,
        )


class WindowManager(DefaultUIElt):
    """Class for managing multiple interface windows in the scene.

    Variables:
        - screen (Surface): the surface on which draw the windows.
        - windows (List[Window]): the list of currently open windows.
        - is_hover: indicate if any window is currently hover.
        - is_dragging (bool): indicate if any window is currently being dragged.

    Methodes:
        - close_window(Window): delete a window from the manager.
        - _handle_event(List[Event]): handle event from all windows.
        - add_window(Coordinate, Coordinate, str): add a standard window to the manager.
        - add_node_info_window(Coordinate, Dict, str): add a node info window to the manager.
        - remove_windows_for(List[str]): close windows associated with the given names.
        - draw(offset, zoom): draw all currently open windows."""

    def __init__(self, screen: pygame.Surface):
        """Initialise le gestionnaire avec la surface d'affichage associée."""

        self.screen = screen

        self.windows: List[Window] = []

    def close_window(self, window: Window):
        """Close one specific window."""
        if window in self.windows:
            self.windows.remove(window)

    def _handle_event(
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = pygame.Vector2(0, 0),
        zoom: Optional[float] = 1,
    ):

        for window in self.windows:
            window._handle_event(events, ms_pos, offset, zoom)

    def add_window(
        self,
        position: List[int] | Tuple[int, int],
        size: List[int] | Tuple[int, int],
        title: str = "Window",
    ):
        """Add standard window to the manager."""

        self.windows.append(
            Window(self.screen, position, size, self.close_window, title)
        )

    def add_node_info_window(
        self,
        screen: pygame.Surface,
        position: List[int] | Tuple[int, int],
        data: Dict[str, Any],
        title: str = "Node",
    ):
        """Add a node infomation window to the manager."""
        for window in self.windows:
            if isinstance(window, NodeInfoWindow) and window.title == title:
                if window.position.distance_to(position) < 10:
                    self.windows.remove(window)
                else:
                    window.position = pygame.Vector2(position)
                return
        self.windows.append(
            NodeInfoWindow(
                screen, position, data, self.close_window, self.add_attack_window, title
            )
        )

    def add_attack_window(
        self,
        position: List[int] | Tuple[int, int],
        title: str = "Node",
    ):
        for window in self.windows:
            if isinstance(window, AttackWindow) and window.title == title:
                if window.position.distance_to(position) < 10:
                    self.windows.remove(window)
                else:
                    window.position = pygame.Vector2(position)
                return
        self.windows.append(
            AttackWindow(
                self.screen, position, (200, 200), self.close_window, title=title
            )
        )

    @property
    def is_hover(self):
        """Specify if any window is hover."""
        return any([window.hover for window in self.windows])

    @property
    def is_dragging(self):
        """Specify if any window is being dragged."""
        return any([window._dragging for window in self.windows])

    def remove_windows_for(self, names: List[str]):
        """Ferme les fenêtres associées aux noms donnés (ex: joueurs qui ont quitté).

        Les `NodeInfoWindow` sont indexées par titre (= nom du nœud), donc on
        filtre simplement les fenêtres dont le titre correspond à un nom fourni.
        """
        if not names:
            return
        names_set = set(names)
        self.windows = [
            window for window in self.windows if window.title not in names_set
        ]

    def draw(self, offset: pygame.Vector2, zoom: float):
        """Draw all open windows."""

        for window in self.windows:
            window.draw(offset, zoom)


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()

    wm = WindowManager(screen)
    wm.add_window((100, 100), (300, 200), "Test Window")
    wm.add_node_info_window(
        screen, (400, 300), {"CPU": 50, "RAM": 75}, title="Node Info"
    )

    running = True

    while running:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

        mouse_pos = pygame.mouse.get_pos()
        wm._handle_event(events, mouse_pos)
        screen.fill((20, 20, 20))
        wm.draw(pygame.Vector2(0, 0), 1.0)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
