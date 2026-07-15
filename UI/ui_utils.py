import pygame
from typing import Tuple, List, Optional
from abc import ABC, abstractmethod
import numpy as np

from utils import *


class DefaultUIElt(ABC):
    """Default class for UI elements.

    Variables:
        - screen (Surface): the surface on which draw the element.

    Methodes:
        - _handle_event(List[Event], Coordinate): manage events.
        - draw(): draw the element on the screen."""

    def __init__(self, screen: pygame.Surface):

        self.screen = screen

    @abstractmethod
    def _handle_event(
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = None,
        zoom: Optional[float] = None,
    ):
        """Manage default event."""

    @abstractmethod
    def draw(self, offset: pygame.Vector2, zoom: float):
        """Draw the element on the screen."""


class UITheme:

    # ===== Colors =====

    # -- Default --

    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GREEN = (0, 255, 0)

    # -- Node --

    SELF_NODE_COLOR = (0, 255, 110)
    OTHER_NODE_COLOR = (0, 160, 220)
    HOVER_NODE_COLOR = (255, 220, 60)
    DRAG_NODE_COLOR = (255, 100, 50)

    # -- Other --

    GRID_COLOR = (40, 40, 40)
    HOVERED_TASK_BAR = (10, 10, 10)

    # -- Label Color --

    LABEL_SELF_COLOR = (180, 255, 200)
    LABEL_OTHER_COLOR = (140, 200, 255)

    # -- Edge --

    EDGE_COLOR = WHITE
    EDGE_HOVER_COLOR = (255, 220, 60)

    FONT_NAME = "Consolas"

    # BLACK = (0, 0, 0)
    HOVER_BLACK = (20, 20, 20)
    # WHITE = (255, 255, 255)
    HOVER_WHITE = (200, 200, 200)
    # GREEN = (0, 255, 0)
    HOVER_GREEN = (0, 200, 0)


def to_vect(vect: Tuple[int, int] | List[int] | pygame.Vector2):
    if isinstance(vect, pygame.Vector2):
        return vect
    elif len(vect) != 2:
        raise ValueError(f"The size of the argument is not 2, argumument : {vect}.")
    else:
        return pygame.Vector2(vect)


def distance(
    p1: Tuple[int, int] | List[int] | pygame.Vector2,
    p2: Tuple[int, int] | List[int] | pygame.Vector2,
):
    p1 = to_vect(p1)
    p2 = to_vect(p2)

    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5


def world_to_screen(
    pos: pygame.Vector2 | Tuple | np.ndarray,
    offset: pygame.Vector2,
    zoom: float,
) -> pygame.Vector2 | Tuple:
    """Convertit des coordonnées monde en coordonnées écran."""
    if isinstance(pos, pygame.Vector2):
        return pygame.Vector2(pos.x * zoom + offset.x, pos.y * zoom + offset.y)
    else:
        return (pos[0] * zoom + offset.x, pos[1] * zoom + offset.y)


def world_to_screen_rect(
    rect: pygame.Rect, offset: pygame.Vector2, zoom: float
) -> pygame.Rect:
    """Convertit un rectangle du monde en rectangle écran."""
    return pygame.Rect(
        int(rect.x * zoom + offset.x),
        int(rect.y * zoom + offset.y),
        int(rect.width * zoom),
        int(rect.height * zoom),
    )


def world_to_screen_polygon(
    l_pos: pygame.Vector2 | Tuple | np.ndarray, offset: pygame.Vector2, zoom: float
) -> pygame.Vector2 | Tuple:
    if isinstance(l_pos, np.ndarray):
        return l_pos * zoom + np.array(offset)
    return [world_to_screen(pos, offset, zoom) for pos in l_pos]


def point_in_polygon(position, vertex):
    """
    Détermine si une position est à l'intérieur d'un polygone.

    :param position: tuple (x, y) représentant le point à tester
    :param sommets: liste de tuples [(x1, y1), (x2, y2), ...] représentant
                     les sommets du polygone, dans l'ordre (sens horaire
                     ou anti-horaire, peu importe)
    :return: True si le point est à l'intérieur du polygone, False sinon
    """
    x, y = position
    n = len(vertex)
    inside = False

    x1, y1 = vertex[0]
    for i in range(1, n + 1):
        x2, y2 = vertex[i % n]

        if y > min(y1, y2):
            if y <= max(y1, y2):
                if x <= max(x1, x2):
                    if y1 != y2:
                        x_intersection = (y - y1) * (x2 - x1) / (y2 - y1) + x1
                    if x1 == x2 or x <= x_intersection:
                        inside = not inside

        x1, y1 = x2, y2

    return inside
