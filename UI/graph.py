import pygame
from typing import List, Tuple, Dict
import random
import math
from utils import UserStates

from UI.ui_utils import *


class Node(DefaultUIElt):
    """Class for an interactive node in the graph.

    Variables:
        - screen (Surface): the surface on which draw the node.
        - name (str): the name displayed for the node.
        - is_self (bool): indicate if the node represents the local player.
        - x (float): the x coordinate of the node in world space.
        - y (float): the y coordinate of the node in world space.
        - rect (Rect): the rectangle used for hit testing.
        - pos (Vector2): the current position of the node.
        - radius (int): the radius of the node.
        - dragging (bool): indicate if the node is currently being dragged.
        - hover (bool): indicate if the mouse is over the node.
        - on_click (Methode): the method executed when the node is clicked.
        - vel (Vector2): the current velocity of the node.
        - force (Vector2): the force applied to the node during updates.

    Methodes:
        - _handle_event(List[Event], Vector2, float): manage mouse interactions.
        - update(): update the node physics and position.
        - draw(Vector2, float): draw the node, its halo and its label."""

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
        self._font_label = pygame.font.SysFont(UITheme.FONT_NAME, 13, bold=True)
        self._font_title = pygame.font.SysFont(UITheme.FONT_NAME, 15, bold=True)

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
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = pygame.Vector2(0, 0),
        zoom: Optional[float] = 1,
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
            color = UITheme.DRAG_NODE_COLOR
        elif self.hover:
            color = UITheme.HOVER_NODE_COLOR
        elif self.is_self:
            color = UITheme.SELF_NODE_COLOR
        else:
            color = UITheme.OTHER_NODE_COLOR

        # Display Halo
        halo = pygame.Surface((4 * radius, 4 * radius), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*color, 30), (2 * radius, 2 * radius), 2 * radius)
        self.screen.blit(halo, screen_pos + pygame.Vector2(-2 * radius, -2 * radius))

        pygame.draw.circle(self.screen, (10, 12, 18), screen_pos, radius)

        thickness = max(1, int((3 if self.is_self else 2) * zoom))
        pygame.draw.circle(self.screen, color, screen_pos, radius, thickness)

        pygame.draw.circle(self.screen, color, screen_pos, max(2, radius // 3))

        label_col = (
            UITheme.LABEL_SELF_COLOR if self.is_self else UITheme.LABEL_OTHER_COLOR
        )
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


class Graph(DefaultUIElt):
    """Class for the complete graph managing nodes and edges.

    Variables:
        - screen (Surface): the surface on which draw the graph.
        - self_name (str): the name of the local player.
        - user_states (UserStates): the current state of the players.
        - users (List[str]): the list of player names.
        - adjacent_list (List[List[bool]]): the adjacency matrix describing links between nodes.
        - nodes (List[Node]): the list of node instances displayed in the graph.

    Methodes:
        - sync(): refresh the graph from the latest player state.
        - corner_handle_event(List[Event], Vector2, float): forward mouse events to each node.
        - _effective_params(): calculate physics parameters adapted to the number of nodes.
        - update(Vector2, float): update node positions according to physics rules.
        - draw(Vector2, float): draw the edges and nodes of the graph."""

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

    def _handle_event(
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = pygame.Vector2(0, 0),
        zoom: Optional[float] = 1,
    ):
        """Transmet les événements de souris à chaque nœud du graphe."""
        for node in self.nodes:
            node._handle_event(events, ms_pos, offset, zoom)

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

                    color = (
                        UITheme.EDGE_HOVER_COLOR
                        if is_highlighted
                        else UITheme.EDGE_COLOR
                    )
                    width = int(5 * zoom) if is_highlighted else int(1.5 * zoom)

                    pygame.draw.line(self.screen, color, start, end, width)

        for node in self.nodes:

            node.draw(offset, zoom)
