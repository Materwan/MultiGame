import math
import random
from typing import Dict, List, Optional, Tuple, Any

import pygame
from utils import *

# ===== Colors =====

# -- Node --

SELF_NODE_COLOR = (0, 255, 110)
OTHER_NODE_COLOR = (0, 160, 220)
HOVER_NODE_COLOR = (255, 220, 60)
DRAG_NODE_COLOR = (255, 100, 50)

# -- Other --

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
GRID_COLOR = (40, 40, 40)

# -- Label Color --

LABEL_SELF_COLOR = (180, 255, 200)
LABEL_OTHER_COLOR = (140, 200, 255)

# -- Edge --

EDGE_COLOR = WHITE
EDGE_HOVER_COLOR = (255, 220, 60)

FONT_NAME = "Consolas"


def world_to_screen(
    pos: pygame.Vector2, offset: pygame.Vector2, zoom: float
) -> pygame.Vector2:
    """Convertit des coordonnées monde en coordonnées écran."""
    return pygame.Vector2(pos.x * zoom + offset.x, pos.y * zoom + offset.y)


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


class Node:
    """Représente un nœud du graphe interactif affiché à l'écran."""

    RADIUS_SELF = 14
    RADIUS_OTHER = 10

    def __init__(self, screen: pygame.Surface, name: str, is_self: bool):
        """Initialise un nœud avec son nom, sa position et ses états d'interaction."""

        self.screen = screen

        # -- General --
        self.name = name
        self.is_self = is_self

        # -- Node --
        self.x = random.uniform(-250, 250)
        self.y = random.uniform(-250, 250)

        self.rect = pygame.Rect(self.x - 10, self.y - 10, 20, 20)
        self.pos = pygame.Vector2(self.x, self.y)

        self.radius = self.RADIUS_SELF if self.is_self else self.RADIUS_OTHER

        # -- Label --
        self._font_label = pygame.font.SysFont(FONT_NAME, 13, bold=True)
        self._font_title = pygame.font.SysFont(FONT_NAME, 15, bold=True)

        # -- Event --
        self.dragging = False
        self.hover = False
        self._drag_start_mouse = pygame.Vector2(0, 0)
        self._drag_start_pos = pygame.Vector2(self.x, self.y)
        self._click_pending = False
        self.on_click = None

        # -- Physics --
        self.vel = pygame.Vector2(0, 0)
        self.force = pygame.Vector2(0, 0)

    def _handle_event(
        self, events: List[pygame.event.Event], offset: pygame.Vector2, zoom: float
    ):
        """Traite les événements de souris liés à ce nœud."""

        mouse_pos = pygame.Vector2(pygame.mouse.get_pos())
        screen_rect = world_to_screen_rect(self.rect, offset, zoom)
        self.hover = screen_rect.collidepoint(mouse_pos)

        for event in events:
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.hover
            ):
                self.dragging = True
                self._click_pending = True
                self._drag_start_mouse = pygame.Vector2(event.pos)
                self._drag_start_pos = pygame.Vector2(self.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                # Clic simple : bouton relâché sans mouvement significatif
                if self._click_pending and self.hover and self.on_click:
                    self.on_click(self)
                self.dragging = False
                self._click_pending = False

            elif event.type == pygame.MOUSEMOTION and self.dragging:
                current_mouse = pygame.Vector2(event.pos)
                delta = current_mouse - self._drag_start_mouse
                # Annule le clic si le nœud a été déplacé
                if delta.length() > 4:
                    self._click_pending = False
                self.pos = self._drag_start_pos + pygame.Vector2(
                    delta.x / zoom, delta.y / zoom
                )
                self.rect.center = (self.pos.x, self.pos.y)

    def update(self):
        """Met à jour la physique du nœud et son positionnement."""
        if self.dragging:
            self.vel = pygame.Vector2(0, 0)
            return

        DAMPING = 0.85
        MAX_SPEED = 8.0

        self.vel += self.force
        self.vel *= DAMPING
        speed = self.vel.length()
        if speed > MAX_SPEED:
            self.vel.scale_to_length(MAX_SPEED)

        self.pos += self.vel
        self.rect.center = (self.pos.x, self.pos.y)
        self.force = pygame.Vector2(0, 0)

    def draw(self, offset: pygame.Vector2, zoom: float):
        """Dessine le nœud, son halo et son libellé à l'écran."""

        screen_pos = world_to_screen(self.pos, offset, zoom)
        radius = max(4, int(self.radius * zoom))

        if self.dragging:
            color = DRAG_NODE_COLOR
        elif self.hover:
            color = HOVER_NODE_COLOR
        elif self.is_self:
            color = SELF_NODE_COLOR
        else:
            color = OTHER_NODE_COLOR

        # Display Halo
        halo = pygame.Surface((4 * radius, 4 * radius), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*color, 30), (2 * radius, 2 * radius), 2 * radius)
        self.screen.blit(halo, screen_pos + pygame.Vector2(-2 * radius, -2 * radius))

        pygame.draw.circle(self.screen, (10, 12, 18), screen_pos, radius)

        thickness = max(1, int((3 if self.is_self else 2) * zoom))
        pygame.draw.circle(self.screen, color, screen_pos, radius, thickness)

        pygame.draw.circle(self.screen, color, screen_pos, max(2, radius // 3))

        label_col = LABEL_SELF_COLOR if self.is_self else LABEL_OTHER_COLOR
        label = (
            self._font_title.render(self.name, True, label_col)
            if self.is_self
            else self._font_label.render(self.name, True, label_col)
        )
        lx = screen_pos.x - label.get_width() // 2
        ly = screen_pos.y + radius + max(4, int(6 * zoom))
        pad = 3
        bg = pygame.Surface(
            (label.get_width() + pad * 2, label.get_height() + pad * 2), pygame.SRCALPHA
        )
        bg.fill((10, 12, 18, 180))
        self.screen.blit(bg, (lx - pad, ly - pad))
        self.screen.blit(label, (lx, ly))


class Graph:
    """Représente le graphe complet et gère ses nœuds et ses liens."""

    BASE_REPULSION = 10000.0  # répulsion nœud-nœud
    BASE_SPRING_K = 0.02  # raideur du ressort (liens)
    BASE_SPRING_LEN = 200.0  # longueur à vide du ressort
    BASE_GRAVITY = 0.01  # attraction centrale
    BASE_NODE_COUNT = 5  # nombre de nœuds pour lequel ces valeurs sont "justes"

    MIN_DIST = 1.0  # évite division par zéro

    EDGE_HIDE_ZOOM_THRESHOLD = (
        0.7  # en dessous de ce zoom, les liens non survolés sont masqués
    )

    def __init__(
        self,
        screen: pygame.Surface,
        user_states: UserStates,
        self_name: str | None = None,
    ):

        self.screen = screen
        self.self_name = self_name

        self.user_states = user_states
        self.users = user_states.user_names
        self.adjacent_list = user_states.get_adjacent_matrix()

        self.nodes: List[Node] = []
        for name in self.users:
            self.nodes.append(Node(self.screen, name, name == self.self_name))

    @property
    def is_dragging(self):
        """Indique si au moins un nœud du graphe est en cours de déplacement."""
        if any([node.dragging for node in self.nodes]):
            return True
        return False

    def sync(self):
        """Met à jour le graphe en place à partir d'un nouvel état des joueurs.

        Contrairement à une reconstruction complète, cette méthode conserve les
        instances de `Node` existantes (position, vitesse, drag, hover, fenêtre
        associée...) pour les joueurs toujours présents. Seuls les nouveaux
        joueurs entraînent la création d'un `Node`, et seuls les joueurs partis
        sont retirés.

        Paramètres :
        - user_states : état courant des joueurs (source de vérité pour les
          noms et la matrice d'adjacence).
        - self_name : nom du joueur local, utilisé pour marquer son nœud.
        - on_click : callback à attacher aux nœuds nouvellement créés (les
          nœuds déjà existants conservent leur callback actuel).

        Retourne la liste des noms de joueurs qui ont été retirés du graphe,
        afin que l'appelant puisse par exemple fermer leurs fenêtres d'info.
        """

        self.adjacent_list = self.user_states.get_adjacent_matrix()

        self.nodes: List[Node] = []
        for name in self.users:
            self.nodes.append(Node(self.screen, name, name == self.self_name))

    def _handle_events(
        self, events: List[pygame.event.Event], offset: pygame.Vector2, zoom: float
    ):
        """Transmet les événements de souris à chaque nœud du graphe."""
        for node in self.nodes:
            node._handle_event(events, offset, zoom)

    def _effective_params(self) -> Tuple[float, float, float, float]:
        """Calcule des paramètres physiques adaptés au nombre de nœuds actuel.

        Plus il y a de nœuds, plus il faut :
        - de répulsion et une plus grande longueur de ressort pour éviter
          l'entassement au centre,
        - une gravité plus faible pour laisser le graphe s'étaler,
        - une raideur de ressort légèrement réduite pour éviter les
          oscillations quand beaucoup de liens tirent en même temps.
        """
        n = max(len(self.nodes), 1)
        ratio = n / self.BASE_NODE_COUNT

        # La répulsion et la longueur de ressort croissent avec sqrt(n)
        # (approx. la façon dont l'aire nécessaire croît avec le nombre de nœuds).
        scale = math.sqrt(ratio)

        repulsion = self.BASE_REPULSION * scale
        spring_len = self.BASE_SPRING_LEN * scale
        gravity = self.BASE_GRAVITY / scale
        spring_k = self.BASE_SPRING_K / math.sqrt(scale)

        return repulsion, spring_k, spring_len, gravity

    def update(self, offset: pygame.Vector2, zoom: float):
        """Met à jour la position des nœuds selon les forces de répulsion et d'attraction."""

        n = len(self.nodes)
        repulsion, spring_k, spring_len, gravity = self._effective_params()

        for i in range(n):
            ni = self.nodes[i]

            # --- Force centrale (gravité vers l'origine) ---
            ni.force -= ni.pos * gravity

            for j in range(i + 1, n):
                nj = self.nodes[j]
                delta = ni.pos - nj.pos
                dist = max(delta.length(), self.MIN_DIST)

                # --- Répulsion nœud-nœud (Coulomb) ---
                rep_mag = repulsion / (dist * dist)
                rep = delta.normalize() * rep_mag
                ni.force += rep
                nj.force -= rep

                # --- Attraction par lien (Hooke) ---
                connected = (
                    (self.adjacent_list[i][j] or self.adjacent_list[j][i])
                    if i < len(self.adjacent_list) and j < len(self.adjacent_list[i])
                    else False
                )

                if connected:
                    stretch = dist - spring_len
                    spring_mag = spring_k * stretch
                    spring = delta.normalize() * spring_mag
                    ni.force -= spring
                    nj.force += spring

        for node in self.nodes:
            node.update()

    def draw(self, offset: pygame.Vector2, zoom: float):
        """Dessine les liens et les nœuds du graphe."""

        show_all_edges = zoom >= self.EDGE_HIDE_ZOOM_THRESHOLD

        for id, row in enumerate(self.adjacent_list):

            for neighbor, connected in enumerate(row):
                if connected and id != neighbor:
                    node_a = self.nodes[id]
                    node_b = self.nodes[neighbor]

                    is_highlighted = (
                        node_a.hover
                        or node_b.hover
                        or node_a.dragging
                        or node_b.dragging
                    )

                    if not show_all_edges and not is_highlighted:
                        continue

                    start = world_to_screen(node_a.pos, offset, zoom)
                    end = world_to_screen(node_b.pos, offset, zoom)

                    color = EDGE_HOVER_COLOR if is_highlighted else EDGE_COLOR
                    width = int(5 * zoom) if is_highlighted else int(1.5 * zoom)

                    pygame.draw.line(self.screen, color, start, end, width)

        for node in self.nodes:

            node.draw(offset, zoom)


class Window:
    """Représente une fenêtre d'interface déplaçable et redimensionnable dans le monde."""

    TITLE_BAR_HEIGHT = 22
    TITLE_BAR_COLOR = (30, 34, 48)
    TITLE_BAR_BORDER_COLOR = (70, 80, 110)
    BODY_COLOR = (16, 18, 28)
    BODY_BORDER_COLOR = (50, 58, 90)
    TITLE_COLOR = (180, 190, 220)
    CLOSE_BUTTON_COLOR = (180, 60, 60)
    CLOSE_BUTTON_HOVER_COLOR = (220, 80, 80)

    def __init__(
        self,
        screen: pygame.Surface,
        position: List[int] | Tuple[int, int],
        size: List[int] | Tuple[int, int],
        title: str = "Window",
    ):
        """Initialise la fenêtre avec sa position, sa taille et son titre."""

        self.screen = screen

        # -- Window (world coordinates) --
        self.position = pygame.Vector2(position)
        self.size = size
        self.title = title

        self._base_font_size = 12

        # -- Dragging state --
        self._dragging = False
        self._drag_start_mouse = pygame.Vector2(0, 0)
        self._drag_start_pos = pygame.Vector2(self.position)

        # -- Close button hover state --
        self._close_hover = False

    def _get_screen_rects(
        self, offset: pygame.Vector2, zoom: float
    ) -> Tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """Retourne les rectangles écran de la fenêtre, de sa barre de titre et du bouton fermer."""

        world_rect = pygame.Rect(
            self.position.x,
            self.position.y,
            self.size[0],
            self.size[1],
        )
        screen_rect = world_to_screen_rect(world_rect, offset, zoom)

        title_bar_h = max(14, int(self.TITLE_BAR_HEIGHT * zoom))
        title_rect = pygame.Rect(
            screen_rect.x, screen_rect.y, screen_rect.width, title_bar_h
        )

        btn_r = max(5, int(7 * zoom))
        close_rect = pygame.Rect(
            screen_rect.right - btn_r * 2 - max(4, int(6 * zoom)),
            screen_rect.y + title_bar_h // 2 - btn_r,
            btn_r * 2,
            btn_r * 2,
        )

        return screen_rect, title_rect, close_rect

    def _handle_events(
        self, events: List[pygame.event.Event], offset: pygame.Vector2, zoom: float
    ):
        """Gère les interactions de souris pour le déplacement et l'état du bouton fermer."""

        mouse_pos = pygame.Vector2(pygame.mouse.get_pos())
        _, title_rect, close_rect = self._get_screen_rects(offset, zoom)

        self._close_hover = close_rect.collidepoint(mouse_pos)

        for event in events:

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if title_rect.collidepoint(event.pos) and not self._close_hover:
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

    def draw(self, offset: pygame.Vector2, zoom: float):
        """Dessine la fenêtre complète avec sa barre de titre et son bouton de fermeture."""

        screen_rect, title_rect, close_rect = self._get_screen_rects(offset, zoom)

        # -- Corps de la fenêtre --
        body_rect = pygame.Rect(
            screen_rect.x,
            title_rect.bottom,
            screen_rect.width,
            screen_rect.height - title_rect.height,
        )
        pygame.draw.rect(self.screen, self.BODY_COLOR, body_rect)
        pygame.draw.rect(self.screen, self.BODY_BORDER_COLOR, body_rect, 1)

        # -- Barre de titre --
        pygame.draw.rect(self.screen, self.TITLE_BAR_COLOR, title_rect)
        pygame.draw.rect(self.screen, self.TITLE_BAR_BORDER_COLOR, title_rect, 1)

        # -- Titre --
        font_size = max(8, int(self._base_font_size * zoom))
        _font_title = pygame.font.SysFont(FONT_NAME, font_size, bold=True)
        label = _font_title.render(self.title, True, self.TITLE_COLOR)
        lx = title_rect.x + max(6, int(8 * zoom))
        ly = title_rect.y + (title_rect.height - label.get_height()) // 2
        self.screen.blit(label, (lx, ly))

        # -- Bouton fermer --
        btn_color = (
            self.CLOSE_BUTTON_HOVER_COLOR
            if self._close_hover
            else self.CLOSE_BUTTON_COLOR
        )
        pygame.draw.ellipse(self.screen, btn_color, close_rect)

        # Croix sur le bouton
        cx, cy = close_rect.center
        arm = max(2, close_rect.width // 4)
        pygame.draw.line(
            self.screen,
            WHITE,
            (cx - arm, cy - arm),
            (cx + arm, cy + arm),
            max(1, int(1.5 * zoom)),
        )
        pygame.draw.line(
            self.screen,
            WHITE,
            (cx + arm, cy - arm),
            (cx - arm, cy + arm),
            max(1, int(1.5 * zoom)),
        )


class NodeInfoWindow(Window):
    """Fenêtre d'information affichant des données associées à un nœud."""

    MARGIN = 5

    def __init__(self, screen, position, data: Dict[str, Any], title="None"):
        """Initialise la fenêtre avec les informations à afficher."""
        super().__init__(screen, position, (200, 200), title)

        self.data = data

        self._base_data_font_size = 10

    def _handle_events(self, events, offset, zoom):
        """Propagates the window event handling to the base implementation."""
        super()._handle_events(events, offset, zoom)

    def draw(self, offset, zoom):
        """Dessine la fenêtre puis affiche les données textuelles du nœud."""
        super().draw(offset, zoom)

        screen_rect, title_rect, close_rect = self._get_screen_rects(offset, zoom)

        # -- Data --
        font_size = max(6, int(self._base_data_font_size * zoom))
        _data_font = pygame.font.SysFont(FONT_NAME, font_size)
        margin = max(3, int(self.MARGIN * zoom))
        top = screen_rect.top + title_rect.height + margin
        left = screen_rect.left + margin

        self.screen.blit(
            _data_font.render(f"CPU : {self.data['CPU']}", False, WHITE),
            (left, top),
        )
        top += _data_font.get_linesize()

        self.screen.blit(
            _data_font.render(f"RAM : {self.data['RAM']}", False, WHITE),
            (left, top),
        )


class WindowManager:
    """Gère l'ensemble des fenêtres d'interface ouvertes dans la scène."""

    def __init__(self, screen: pygame.Surface):
        """Initialise le gestionnaire avec la surface d'affichage associée."""

        self.screen = screen

        self.windows: List[Window] = []

    def add_window(
        self,
        position: List[int] | Tuple[int, int],
        size: List[int] | Tuple[int, int],
        title: str = "Window",
    ):
        """Ajoute une fenêtre standard au gestionnaire."""

        self.windows.append(Window(self.screen, position, size, title))

    def add_node_info_window(
        self,
        screen: pygame.Surface,
        position: List[int] | Tuple[int, int],
        data: Dict[str, Any],
        title: str = "Node",
    ):
        """Ajoute une fenêtre d'information spécifique à un nœud."""
        for window in self.windows:
            if isinstance(window, NodeInfoWindow) and window.title == title:
                if window.position.distance_to(position) < 10:
                    self.windows.remove(window)
                else:
                    window.position = pygame.Vector2(position)
                return
        self.windows.append(NodeInfoWindow(screen, position, data, title))

    @property
    def is_dragging(self):
        """Indique si une fenêtre est actuellement en train d'être déplacée."""
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

    def _handle_events(
        self, events: List[pygame.event.Event], offset: pygame.Vector2, zoom: float
    ):
        """Transmet les événements aux fenêtres et gère la fermeture via le bouton close."""

        for window in self.windows:
            window._handle_events(events, offset, zoom)

        for event in events:
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == pygame.BUTTON_LEFT
            ):
                for window in self.windows:
                    if window._close_hover:
                        self.windows.remove(window)
                        break

    def draw(self, offset: pygame.Vector2, zoom: float):
        """Dessine toutes les fenêtres actuellement ouvertes."""

        for window in self.windows:
            window.draw(offset, zoom)


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

        self.graph._handle_events(events, self.offset, self.zoom)
        self.windows_manager._handle_events(events, self.offset, self.zoom)

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
                    self.screen, GRID_COLOR, (screen_x, 0), (screen_x, height)
                )

        for y in range(min_y, max_y + spacing, spacing):
            screen_y = world_to_screen(pygame.Vector2(0, y), self.offset, self.zoom).y
            if 0 <= screen_y <= height:
                pygame.draw.line(
                    self.screen, GRID_COLOR, (0, screen_y), (width, screen_y)
                )

    def draw(self):
        """Dessine la grille, le graphe et les fenêtres ouvertes."""

        self._draw_grid()
        self.graph.draw(self.offset, self.zoom)
        self.windows_manager.draw(self.offset, self.zoom)


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

            self.screen.fill(BLACK)

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
