"""
graph.py — Affichage interactif style Obsidian pour le réseau de joueurs.

Fonctionnalités :
- Force-directed layout (répulsion + attraction)
- Drag & drop des nœuds
- Zoom (molette) + Pan (clic droit / clic milieu)
- Nœud joueur mis en valeur
- Arêtes avec lueur
- InfoWindow par nœud : ressources CPU/RAM, ancrée dans le monde, fermeture manuelle
"""

import math
import random
from typing import Dict, List, Optional, Tuple

import pygame

# ─── Palette cyberpunk / terminal ─────────────────────────────────────────────

C_BG = (10, 12, 18)
C_GRID = (20, 26, 38)
C_EDGE = (0, 180, 80)
C_EDGE_GLOW = (0, 80, 30)
C_NODE_SELF = (0, 255, 110)
C_NODE_OTHER = (0, 160, 220)
C_NODE_HOVER = (255, 220, 60)
C_NODE_DRAG = (255, 100, 50)
C_LABEL_SELF = (180, 255, 200)
C_LABEL_OTHER = (140, 200, 255)
C_OUTLINE_SELF = (0, 255, 110)
C_OUTLINE_OTH = (0, 100, 180)

# ─── Palette InfoWindow ────────────────────────────────────────────────────────

C_WIN_BG = (10, 16, 24)  # fond très sombre
C_WIN_BORDER = (0, 160, 80)  # bordure verte
C_WIN_TITLE = (180, 255, 200)  # titre vert clair
C_WIN_KEY = (100, 180, 140)  # clé (CPU / RAM)
C_WIN_VAL = (220, 255, 220)  # valeur numérique
C_WIN_CLOSE = (200, 60, 60)  # croix de fermeture
C_WIN_CLOSE_HOV = (255, 100, 100)  # croix survolée
C_BAR_CPU_FG = (0, 220, 100)  # barre CPU remplie
C_BAR_RAM_FG = (0, 160, 220)  # barre RAM remplie
C_BAR_BG = (20, 35, 30)  # barre fond

FONT_NAME = "Consolas"

# ─── Physique ──────────────────────────────────────────────────────────────────

K_REPULSE = 18_000.0
K_ATTRACT = 0.04
REST_LEN = 180.0
DAMPING = 0.82
MAX_SPEED = 12.0
SETTLE_THR = 0.3

# ─── Dimensions InfoWindow (en pixels monde, zoom 1) ──────────────────────────

WIN_W = 160  # largeur de la fenêtre
WIN_H = 110  # hauteur
WIN_OFFSET = (18, -WIN_H - 18)  # décalage depuis le centre du nœud (x, y)
WIN_CLOSE_R = 7  # rayon du bouton croix
WIN_PAD = 10  # padding interne
BAR_H = 7  # hauteur des barres de progression


class Node:
    RADIUS_SELF = 14
    RADIUS_OTHER = 10

    def __init__(self, node_id: str, is_self: bool = False):
        self.id = node_id
        self.is_self = is_self
        self.x = random.uniform(-200, 200)
        self.y = random.uniform(-200, 200)
        self.vx = 0.0
        self.vy = 0.0
        self.dragging = False
        self.radius = self.RADIUS_SELF if is_self else self.RADIUS_OTHER

    @property
    def pos(self) -> Tuple[float, float]:
        return self.x, self.y

    def screen_pos(self, offset: Tuple[float, float], zoom: float) -> Tuple[int, int]:
        sx = self.x * zoom + offset[0]
        sy = self.y * zoom + offset[1]
        return int(sx), int(sy)

    def contains(
        self, sx: float, sy: float, offset: Tuple[float, float], zoom: float
    ) -> bool:
        cx, cy = self.screen_pos(offset, zoom)
        r = self.radius * zoom
        return (sx - cx) ** 2 + (sy - cy) ** 2 <= r * r


class InfoWindow:
    """Fenêtre d'information déplaçable, ancrée dans l'espace monde.

    Position = nœud + (wx_off, wy_off) en coordonnées monde.
    L'utilisateur peut déplacer la fenêtre en faisant glisser sa barre de titre ;
    le décalage monde est alors mis à jour de façon à ce que la fenêtre suive
    le nœud tout en conservant la nouvelle position relative choisie.
    """

    def __init__(
        self, node: Node, font_title: pygame.font.Font, font_body: pygame.font.Font
    ):
        self.node = node
        self.font_title = font_title
        self.font_body = font_body
        self.resources: Dict[str, int] = {"cpu": 10, "ram": 10}

        # Décalage en espace monde depuis le centre du nœud
        self.wx_off: float = float(WIN_OFFSET[0])
        self.wy_off: float = float(WIN_OFFSET[1])

        # État drag interne
        self.dragging: bool = False
        self._drag_start_mouse: Tuple[int, int] = (0, 0)
        self._drag_start_off: Tuple[float, float] = (0.0, 0.0)

        self._close_hovered = False

    def update_resources(self, resources: Dict[str, int]):
        self.resources = dict(resources)

    # ── Géométrie écran ───────────────────────────────────────────────────────

    def _screen_rect(self, offset: Tuple[float, float], zoom: float) -> pygame.Rect:
        """Rect de la fenêtre en coordonnées écran."""
        nx, ny = self.node.screen_pos(offset, zoom)
        wx = nx + self.wx_off * zoom
        wy = ny + self.wy_off * zoom
        w = int(WIN_W * zoom)
        h = int(WIN_H * zoom)
        return pygame.Rect(int(wx), int(wy), w, h)

    def _titlebar_rect(self, rect: pygame.Rect, zoom: float) -> pygame.Rect:
        """Zone cliquable de la barre de titre (pour initier le drag)."""
        title_h = max(18, int(22 * zoom))
        return pygame.Rect(rect.x, rect.y, rect.width, title_h)

    def _close_btn_center(self, rect: pygame.Rect, zoom: float) -> Tuple[int, int]:
        r = max(4, int(WIN_CLOSE_R * zoom))
        pad = max(4, int(6 * zoom))
        return (rect.right - pad - r, rect.top + pad + r)

    def close_btn_radius(self, zoom: float) -> int:
        return max(4, int(WIN_CLOSE_R * zoom))

    # ── Hit-test ──────────────────────────────────────────────────────────────

    def hit_close(
        self, mx: int, my: int, offset: Tuple[float, float], zoom: float
    ) -> bool:
        rect = self._screen_rect(offset, zoom)
        cx, cy = self._close_btn_center(rect, zoom)
        r = self.close_btn_radius(zoom)
        return (mx - cx) ** 2 + (my - cy) ** 2 <= r * r

    def hit_titlebar(
        self, mx: int, my: int, offset: Tuple[float, float], zoom: float
    ) -> bool:
        """Vrai si le clic est dans la barre de titre (hors bouton croix)."""
        rect = self._screen_rect(offset, zoom)
        if not self._titlebar_rect(rect, zoom).collidepoint(mx, my):
            return False
        return not self.hit_close(mx, my, offset, zoom)

    def update_hover(self, mx: int, my: int, offset: Tuple[float, float], zoom: float):
        self._close_hovered = self.hit_close(mx, my, offset, zoom)

    def hit_window(
        self, mx: int, my: int, offset: Tuple[float, float], zoom: float
    ) -> bool:
        return self._screen_rect(offset, zoom).collidepoint(mx, my)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def start_drag(self, mx: int, my: int):
        self.dragging = True
        self._drag_start_mouse = (mx, my)
        self._drag_start_off = (self.wx_off, self.wy_off)

    def update_drag(self, mx: int, my: int, zoom: float):
        if not self.dragging:
            return
        dx = (mx - self._drag_start_mouse[0]) / zoom
        dy = (my - self._drag_start_mouse[1]) / zoom
        self.wx_off = self._drag_start_off[0] + dx
        self.wy_off = self._drag_start_off[1] + dy

    def stop_drag(self):
        self.dragging = False

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, offset: Tuple[float, float], zoom: float):
        rect = self._screen_rect(offset, zoom)
        w, h = rect.width, rect.height
        pad = max(4, int(WIN_PAD * zoom))

        # ── Fond + bordure ────────────────────────────────────────────────────
        win_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        win_surf.fill((*C_WIN_BG, 220))
        surface.blit(win_surf, rect.topleft)
        pygame.draw.rect(surface, C_WIN_BORDER, rect, max(1, int(1.5 * zoom)))

        # ── Barre de titre (fond subtil + indicateur de drag) ─────────────────
        tb = self._titlebar_rect(rect, zoom)
        tb_surf = pygame.Surface((tb.width, tb.height), pygame.SRCALPHA)
        alpha = 80 if self.dragging else 40
        tb_surf.fill((*C_WIN_BORDER, alpha))
        surface.blit(tb_surf, tb.topleft)
        # Petits points de drag (⋮⋮) au centre gauche de la barre
        dot_x = rect.x + pad
        dot_cy = tb.centery
        for dy in (-3, 0, 3):
            for dx in (0, 4):
                pygame.draw.circle(
                    surface,
                    (*C_WIN_BORDER, 160),
                    (dot_x + dx, dot_cy + int(dy * zoom)),
                    max(1, int(1.5 * zoom)),
                )

        # ── Ligne de connexion nœud → fenêtre ────────────────────────────────
        nx, ny = self.node.screen_pos(offset, zoom)
        anchor = (rect.left + w // 2, rect.bottom)
        pygame.draw.line(
            surface, (*C_WIN_BORDER, 120), (nx, ny), anchor, max(1, int(1 * zoom))
        )

        # ── Titre ────────────────────────────────────────────────────────────
        title = self.font_title.render(self.node.id, True, C_WIN_TITLE)
        title_scaled = (
            pygame.transform.smoothscale(
                title,
                (
                    min(w - pad * 2 - int(20 * zoom), title.get_width()),
                    title.get_height(),
                ),
            )
            if title.get_width() > w - pad * 2 - int(20 * zoom)
            else title
        )

        surface.blit(title_scaled, (rect.x + pad, rect.y + pad))

        # ── Séparateur ───────────────────────────────────────────────────────
        sep_y = rect.y + pad + title_scaled.get_height() + max(3, int(4 * zoom))
        pygame.draw.line(
            surface, C_WIN_BORDER, (rect.x + pad, sep_y), (rect.right - pad, sep_y), 1
        )

        # ── Ressources ───────────────────────────────────────────────────────
        y_cur = sep_y + max(4, int(5 * zoom))
        bar_w = w - pad * 2
        bar_h = max(4, int(BAR_H * zoom))

        for key, color_fg in (("cpu", C_BAR_CPU_FG), ("ram", C_BAR_RAM_FG)):
            val = self.resources.get(key, 0)
            max_val = 10
            ratio = max(0.0, min(1.0, val / max_val))

            # Libellé  "CPU : 10"
            label_str = f"{key.upper()} : {val}"
            lbl = self.font_body.render(label_str, True, C_WIN_KEY)
            lbl_h = lbl.get_height()
            surface.blit(lbl, (rect.x + pad, y_cur))

            val_surf = self.font_body.render(f"/{max_val}", True, C_WIN_VAL)
            surface.blit(val_surf, (rect.x + pad + lbl.get_width(), y_cur))

            y_cur += lbl_h + max(2, int(2 * zoom))

            # Barre de progression
            bg_rect = pygame.Rect(rect.x + pad, y_cur, bar_w, bar_h)
            fill_rect = pygame.Rect(rect.x + pad, y_cur, int(bar_w * ratio), bar_h)
            pygame.draw.rect(surface, C_BAR_BG, bg_rect, border_radius=2)
            if fill_rect.width > 0:
                pygame.draw.rect(surface, color_fg, fill_rect, border_radius=2)
            pygame.draw.rect(surface, C_WIN_BORDER, bg_rect, 1, border_radius=2)

            y_cur += bar_h + max(6, int(8 * zoom))

        # ── Bouton croix ──────────────────────────────────────────────────────
        cx, cy = self._close_btn_center(rect, zoom)
        r = self.close_btn_radius(zoom)
        close_col = C_WIN_CLOSE_HOV if self._close_hovered else C_WIN_CLOSE
        # Cercle de fond
        pygame.draw.circle(surface, (30, 10, 10), (cx, cy), r)
        pygame.draw.circle(surface, close_col, (cx, cy), r, max(1, int(1.5 * zoom)))
        # Croix
        d = max(2, int(r * 0.55))
        pygame.draw.line(
            surface,
            close_col,
            (cx - d, cy - d),
            (cx + d, cy + d),
            max(1, int(1.5 * zoom)),
        )
        pygame.draw.line(
            surface,
            close_col,
            (cx + d, cy - d),
            (cx - d, cy + d),
            max(1, int(1.5 * zoom)),
        )


class GraphView:
    """Composant graphe autonome — s'intègre dans n'importe quel DefaultState."""

    def __init__(self, screen: pygame.Surface, player_name: str, neighbors: List[str]):
        self.screen = screen
        self.player_name = player_name

        self._font_label = pygame.font.SysFont(FONT_NAME, 13, bold=True)
        self._font_title = pygame.font.SysFont(FONT_NAME, 15, bold=True)
        self._font_win_t = pygame.font.SysFont(FONT_NAME, 12, bold=True)
        self._font_win_b = pygame.font.SysFont(FONT_NAME, 11)

        # Caméra
        w, h = screen.get_size()
        self.offset: List[float] = [w / 2, h / 2]
        self.zoom: float = 1.0
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_origin = (0.0, 0.0)

        # Drag nœuds
        self._dragged_node: Optional[Node] = None
        self._hovered_node: Optional[Node] = None

        # Drag fenêtres
        self._dragged_window: Optional[InfoWindow] = None

        # Simulation
        self._settled = False
        self._settle_cnt = 0

        # InfoWindows ouvertes : node_id -> InfoWindow
        self._info_windows: Dict[str, InfoWindow] = {}

        # Ressources connues pour tous les nœuds : node_id -> {cpu, ram}
        self._all_resources: Dict[str, Dict[str, int]] = {}

        self.build_graph(player_name, neighbors)

    # ── Construction ──────────────────────────────────────────────────────────

    def build_graph(self, player_name: str, neighbors: List[str]):
        self._settled = False
        self._settle_cnt = 0

        self_node = Node(player_name, is_self=True)
        self_node.x, self_node.y = 0.0, 0.0

        self.nodes: Dict[str, Node] = {player_name: self_node}
        self.edges: List[Tuple[str, str]] = []

        n = len(neighbors)
        for i, name in enumerate(neighbors):
            angle = 2 * math.pi * i / max(n, 1)
            node = Node(name, is_self=False)
            node.x = math.cos(angle) * REST_LEN * 0.9
            node.y = math.sin(angle) * REST_LEN * 0.9
            self.nodes[name] = node
            self.edges.append((player_name, name))

        # Nettoie les fenêtres pour les nœuds disparus
        self._info_windows = {
            k: v for k, v in self._info_windows.items() if k in self.nodes
        }

    def update_graph(self, player_name: str, neighbors: List[str]):
        existing = {n.id: n for n in self.nodes.values()}

        n = len(neighbors)
        for i, name in enumerate(neighbors):
            if name not in existing:
                node = Node(name, is_self=False)
                angle = 2 * math.pi * i / max(n, 1)
                node.x = math.cos(angle) * REST_LEN
                node.y = math.sin(angle) * REST_LEN
                existing[name] = node

        keep = set(neighbors) | {player_name}
        self.nodes = {k: v for k, v in existing.items() if k in keep}
        self.edges = [(player_name, name) for name in neighbors if name in self.nodes]
        self._settled = False

        # Retire les fenêtres de nœuds supprimés
        self._info_windows = {
            k: v for k, v in self._info_windows.items() if k in self.nodes
        }

    # ── Ressources ────────────────────────────────────────────────────────────

    def set_all_resources(self, all_resources: Dict[str, Dict[str, int]]):
        """Met à jour le cache de ressources et rafraîchit les fenêtres ouvertes."""
        self._all_resources.update(all_resources)
        for node_id, win in self._info_windows.items():
            if node_id in self._all_resources:
                win.update_resources(self._all_resources[node_id])

    def _resources_for(self, node_id: str) -> Dict[str, int]:
        return self._all_resources.get(node_id, {"cpu": 10, "ram": 10})

    # ── Gestion des InfoWindows ───────────────────────────────────────────────

    def _toggle_info_window(self, node: Node):
        """Ouvre une InfoWindow si absente, ou ne fait rien (fermeture via la croix)."""
        if node.id in self._info_windows:
            return  # déjà ouverte
        win = InfoWindow(node, self._font_win_t, self._font_win_b)
        win.update_resources(self._resources_for(node.id))
        self._info_windows[node.id] = win

    def _close_info_window(self, node_id: str):
        self._info_windows.pop(node_id, None)

    # ── Simulation force-directed ─────────────────────────────────────────────

    def _simulate(self):
        if self._settled:
            return

        node_list = list(self.nodes.values())
        n = len(node_list)

        for i in range(n):
            a = node_list[i]
            for j in range(i + 1, n):
                b = node_list[j]
                dx = b.x - a.x
                dy = b.y - a.y
                dist2 = dx * dx + dy * dy + 0.1
                dist = math.sqrt(dist2)
                force = K_REPULSE / dist2
                fx = force * dx / dist
                fy = force * dy / dist
                if not a.dragging:
                    a.vx -= fx
                    a.vy -= fy
                if not b.dragging:
                    b.vx += fx
                    b.vy += fy

        for a_id, b_id in self.edges:
            a = self.nodes.get(a_id)
            b = self.nodes.get(b_id)
            if a is None or b is None:
                continue
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.1
            delta = dist - REST_LEN
            force = K_ATTRACT * delta
            fx = force * dx / dist
            fy = force * dy / dist
            if not a.dragging:
                a.vx += fx
                a.vy += fy
            if not b.dragging:
                b.vx -= fx
                b.vy -= fy

        total_speed = 0.0
        for node in node_list:
            if node.dragging:
                node.vx, node.vy = 0.0, 0.0
                continue
            node.vx *= DAMPING
            node.vy *= DAMPING
            speed = math.sqrt(node.vx**2 + node.vy**2)
            if speed > MAX_SPEED:
                node.vx = node.vx / speed * MAX_SPEED
                node.vy = node.vy / speed * MAX_SPEED
            node.x += node.vx
            node.y += node.vy
            total_speed += speed

        avg_speed = total_speed / max(n, 1)
        if avg_speed < SETTLE_THR:
            self._settle_cnt += 1
            if self._settle_cnt > 60:
                self._settled = True
        else:
            self._settle_cnt = 0

    # ── Événements ────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event):

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos

            if event.button == 1:
                # 1. Boutons de fermeture des InfoWindows (priorité max)
                for node_id, win in list(self._info_windows.items()):
                    if win.hit_close(mx, my, self.offset, self.zoom):
                        self._close_info_window(node_id)
                        return

                # 2. Barre de titre → drag de la fenêtre
                for win in self._info_windows.values():
                    if win.hit_titlebar(mx, my, self.offset, self.zoom):
                        win.start_drag(mx, my)
                        self._dragged_window = win
                        return

                # 3. Clic sur un nœud → drag du nœud ou ouverture de fenêtre
                for node in self.nodes.values():
                    if node.contains(mx, my, self.offset, self.zoom):
                        node.dragging = True
                        self._dragged_node = node
                        self._settled = False
                        return

                # 4. Reste de la fenêtre → absorbe (ne pan pas)
                for win in self._info_windows.values():
                    if win.hit_window(mx, my, self.offset, self.zoom):
                        return

                # 5. Pan
                self._panning = True
                self._pan_start = (mx, my)
                self._pan_origin = (self.offset[0], self.offset[1])

            elif event.button in (2, 3):
                self._panning = True
                self._pan_start = (mx, my)
                self._pan_origin = (self.offset[0], self.offset[1])

            elif event.button == 4:
                self._zoom_at(mx, my, 1.1)
            elif event.button == 5:
                self._zoom_at(mx, my, 1 / 1.1)

        elif event.type == pygame.MOUSEBUTTONUP:
            # Fin du drag d'une fenêtre
            if self._dragged_window:
                self._dragged_window.stop_drag()
                self._dragged_window = None
                return

            if self._dragged_node:
                # Clic simple (pas de mouvement) → toggle fenêtre
                speed = math.sqrt(self._dragged_node.vx**2 + self._dragged_node.vy**2)
                if speed < 0.5:
                    self._toggle_info_window(self._dragged_node)
                self._dragged_node.dragging = False
                self._dragged_node = None
            self._panning = False

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos

            # Drag d'une fenêtre (priorité sur tout le reste)
            if self._dragged_window:
                self._dragged_window.update_drag(mx, my, self.zoom)
                return

            if self._dragged_node:
                self._dragged_node.x = (mx - self.offset[0]) / self.zoom
                self._dragged_node.y = (my - self.offset[1]) / self.zoom
                return

            if self._panning:
                self.offset[0] = self._pan_origin[0] + (mx - self._pan_start[0])
                self.offset[1] = self._pan_origin[1] + (my - self._pan_start[1])
                return

            # Hover nœuds
            self._hovered_node = None
            for node in self.nodes.values():
                if node.contains(mx, my, self.offset, self.zoom):
                    self._hovered_node = node
                    break

            # Hover boutons croix
            for win in self._info_windows.values():
                win.update_hover(mx, my, self.offset, self.zoom)

    def _zoom_at(self, mx: float, my: float, factor: float):
        new_zoom = max(0.2, min(4.0, self.zoom * factor))
        scale = new_zoom / self.zoom
        self.offset[0] = mx + (self.offset[0] - mx) * scale
        self.offset[1] = my + (self.offset[1] - my) * scale
        self.zoom = new_zoom

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _draw_grid(self):
        w, h = self.screen.get_size()
        step = max(20, int(60 * self.zoom))
        ox = int(self.offset[0]) % step
        oy = int(self.offset[1]) % step
        for x in range(ox, w, step):
            pygame.draw.line(self.screen, C_GRID, (x, 0), (x, h), 1)
        for y in range(oy, h, step):
            pygame.draw.line(self.screen, C_GRID, (0, y), (w, y), 1)

    def _draw_edge(self, a: Node, b: Node):
        ax, ay = a.screen_pos(self.offset, self.zoom)
        bx, by = b.screen_pos(self.offset, self.zoom)

        glow_surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        pygame.draw.line(
            glow_surf,
            (*C_EDGE_GLOW, 80),
            (ax, ay),
            (bx, by),
            max(1, int(6 * self.zoom)),
        )
        self.screen.blit(glow_surf, (0, 0))

        pygame.draw.line(
            self.screen, C_EDGE, (ax, ay), (bx, by), max(1, int(1.5 * self.zoom))
        )

        pygame.draw.circle(self.screen, C_EDGE, (ax, ay), max(2, int(3 * self.zoom)))
        pygame.draw.circle(self.screen, C_EDGE, (bx, by), max(2, int(3 * self.zoom)))

    def _draw_node(self, node: Node):
        sx, sy = node.screen_pos(self.offset, self.zoom)
        r = max(4, int(node.radius * self.zoom))

        if node.dragging:
            color = C_NODE_DRAG
            outline = C_NODE_DRAG
        elif node is self._hovered_node:
            color = C_NODE_HOVER
            outline = C_NODE_HOVER
        elif node.is_self:
            color = C_NODE_SELF
            outline = C_OUTLINE_SELF
        else:
            color = C_NODE_OTHER
            outline = C_OUTLINE_OTH

        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*color, 30), (r * 2, r * 2), r * 2)
        self.screen.blit(halo, (sx - r * 2, sy - r * 2))

        pygame.draw.circle(self.screen, (10, 12, 18), (sx, sy), r)

        thickness = max(1, int((3 if node.is_self else 2) * self.zoom))
        pygame.draw.circle(self.screen, outline, (sx, sy), r, thickness)

        pygame.draw.circle(self.screen, color, (sx, sy), max(2, r // 3))

        label_col = C_LABEL_SELF if node.is_self else C_LABEL_OTHER
        label = (
            self._font_title.render(node.id, True, label_col)
            if node.is_self
            else self._font_label.render(node.id, True, label_col)
        )
        lx = sx - label.get_width() // 2
        ly = sy + r + max(4, int(6 * self.zoom))
        pad = 3
        bg = pygame.Surface(
            (label.get_width() + pad * 2, label.get_height() + pad * 2), pygame.SRCALPHA
        )
        bg.fill((10, 12, 18, 180))
        self.screen.blit(bg, (lx - pad, ly - pad))
        self.screen.blit(label, (lx, ly))

    def draw(self):
        """Appeler depuis DefaultState.display(), avant pygame.display.flip()."""
        self._simulate()

        self._draw_grid()

        for a_id, b_id in self.edges:
            a = self.nodes.get(a_id)
            b = self.nodes.get(b_id)
            if a and b:
                self._draw_edge(a, b)

        for node in self.nodes.values():
            self._draw_node(node)

        # InfoWindows — dessinées par-dessus tout
        for win in self._info_windows.values():
            win.draw(self.screen, self.offset, self.zoom)

        self._draw_hud()

    def _draw_hud(self):
        if self._hovered_node:
            info = f"[ {self._hovered_node.id} ]"
            surf = self._font_title.render(info, True, C_NODE_HOVER)
            w, h = self.screen.get_size()
            self.screen.blit(surf, (w - surf.get_width() - 12, 10))

        zoom_txt = self._font_label.render(f"zoom {self.zoom:.2f}×", True, (50, 70, 60))
        self.screen.blit(zoom_txt, (10, 10))

        tip = self._font_label.render(
            "click: info  |  drag: move  |  scroll: zoom  |  right-drag: pan",
            True,
            (40, 60, 50),
        )
        _, h = self.screen.get_size()
        self.screen.blit(tip, (10, h - tip.get_height() - 10))
