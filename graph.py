"""
graph.py — Affichage interactif style Obsidian pour le réseau de joueurs.

Fonctionnalités :
- Force-directed layout (répulsion + attraction)
- Drag & drop des nœuds
- Zoom (molette) + Pan (clic droit / clic milieu)
- Nœud joueur mis en valeur
- Arêtes avec lueur
"""

import math
import random
from typing import Dict, List, Optional, Tuple

import pygame

# ─── Palette cyberpunk / terminal ─────────────────────────────────────────────

C_BG           = (10, 12, 18)
C_GRID         = (20, 26, 38)
C_EDGE         = (0, 180, 80)
C_EDGE_GLOW    = (0, 80, 30)
C_NODE_SELF    = (0, 255, 110)
C_NODE_OTHER   = (0, 160, 220)
C_NODE_HOVER   = (255, 220, 60)
C_NODE_DRAG    = (255, 100, 50)
C_LABEL_SELF   = (180, 255, 200)
C_LABEL_OTHER  = (140, 200, 255)
C_OUTLINE_SELF = (0, 255, 110)
C_OUTLINE_OTH  = (0, 100, 180)

FONT_NAME = "Consolas"

# ─── Physique ──────────────────────────────────────────────────────────────────

K_REPULSE  = 18_000.0   # force de répulsion entre nœuds
K_ATTRACT  = 0.04       # raideur du ressort (arête)
REST_LEN   = 180.0      # longueur de repos d'une arête
DAMPING    = 0.82       # amortissement de la vélocité
MAX_SPEED  = 12.0       # vitesse max par tick
SETTLE_THR = 0.3        # seuil de convergence (px/tick moyen)


class Node:
    RADIUS_SELF  = 14
    RADIUS_OTHER = 10

    def __init__(self, node_id: str, is_self: bool = False):
        self.id       = node_id
        self.is_self  = is_self
        self.x        = random.uniform(-200, 200)
        self.y        = random.uniform(-200, 200)
        self.vx       = 0.0
        self.vy       = 0.0
        self.dragging = False
        self.radius   = self.RADIUS_SELF if is_self else self.RADIUS_OTHER

    @property
    def pos(self) -> Tuple[float, float]:
        return self.x, self.y

    def screen_pos(self, offset: Tuple[float, float], zoom: float) -> Tuple[int, int]:
        sx = self.x * zoom + offset[0]
        sy = self.y * zoom + offset[1]
        return int(sx), int(sy)

    def contains(self, sx: float, sy: float, offset: Tuple[float, float], zoom: float) -> bool:
        cx, cy = self.screen_pos(offset, zoom)
        r = self.radius * zoom
        return (sx - cx) ** 2 + (sy - cy) ** 2 <= r * r


class GraphView:
    """Composant graphe autonome — s'intègre dans n'importe quel DefaultState."""

    def __init__(self, screen: pygame.Surface, player_name: str, neighbors: List[str]):
        self.screen = screen
        self.player_name = player_name

        self._font_label = pygame.font.SysFont(FONT_NAME, 13, bold=True)
        self._font_title = pygame.font.SysFont(FONT_NAME, 15, bold=True)

        # Caméra
        w, h = screen.get_size()
        self.offset: List[float] = [w / 2, h / 2]
        self.zoom: float = 1.0
        self._panning     = False
        self._pan_start   = (0, 0)
        self._pan_origin  = (0.0, 0.0)

        # Drag
        self._dragged_node: Optional[Node] = None
        self._hovered_node: Optional[Node] = None

        # Simulation
        self._settled    = False
        self._settle_cnt = 0

        self.build_graph(player_name, neighbors)

    # ── Construction ──────────────────────────────────────────────────────────

    def build_graph(self, player_name: str, neighbors: List[str]):
        """(Re)construit le graphe depuis les données reçues du serveur."""
        self._settled = False
        self._settle_cnt = 0

        # Nœud joueur au centre
        self_node = Node(player_name, is_self=True)
        self_node.x, self_node.y = 0.0, 0.0

        self.nodes: Dict[str, Node] = {player_name: self_node}
        self.edges: List[Tuple[str, str]] = []

        # Voisins disposés en cercle régulier pour démarrer proprement
        n = len(neighbors)
        for i, name in enumerate(neighbors):
            angle = 2 * math.pi * i / max(n, 1)
            node = Node(name, is_self=False)
            node.x = math.cos(angle) * REST_LEN * 0.9
            node.y = math.sin(angle) * REST_LEN * 0.9
            self.nodes[name] = node
            self.edges.append((player_name, name))

    def update_graph(self, player_name: str, neighbors: List[str]):
        """Met à jour le graphe en conservant les positions existantes."""
        existing = {n.id: n for n in self.nodes.values()}

        n = len(neighbors)
        for i, name in enumerate(neighbors):
            if name not in existing:
                node = Node(name, is_self=False)
                angle = 2 * math.pi * i / max(n, 1)
                node.x = math.cos(angle) * REST_LEN
                node.y = math.sin(angle) * REST_LEN
                existing[name] = node

        # Supprimer les nœuds absents (sauf le joueur)
        keep = set(neighbors) | {player_name}
        self.nodes = {k: v for k, v in existing.items() if k in keep}

        self.edges = [(player_name, name) for name in neighbors if name in self.nodes]
        self._settled = False

    # ── Simulation force-directed ─────────────────────────────────────────────

    def _simulate(self):
        if self._settled:
            return

        node_list = list(self.nodes.values())
        n = len(node_list)

        # Répulsion O(n²) — acceptable pour de petits graphes de jeu
        for i in range(n):
            a = node_list[i]
            for j in range(i + 1, n):
                b = node_list[j]
                dx = b.x - a.x
                dy = b.y - a.y
                dist2 = dx * dx + dy * dy + 0.1
                dist  = math.sqrt(dist2)
                force = K_REPULSE / dist2
                fx = force * dx / dist
                fy = force * dy / dist
                if not a.dragging:
                    a.vx -= fx
                    a.vy -= fy
                if not b.dragging:
                    b.vx += fx
                    b.vy += fy

        # Attraction sur les arêtes
        for (a_id, b_id) in self.edges:
            a = self.nodes.get(a_id)
            b = self.nodes.get(b_id)
            if a is None or b is None:
                continue
            dx   = b.x - a.x
            dy   = b.y - a.y
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

        # Intégration + amortissement
        total_speed = 0.0
        for node in node_list:
            if node.dragging:
                node.vx, node.vy = 0.0, 0.0
                continue
            node.vx *= DAMPING
            node.vy *= DAMPING
            speed = math.sqrt(node.vx ** 2 + node.vy ** 2)
            if speed > MAX_SPEED:
                node.vx = node.vx / speed * MAX_SPEED
                node.vy = node.vy / speed * MAX_SPEED
            node.x += node.vx
            node.y += node.vy
            total_speed += speed

        # Détection de convergence
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
                # Drag d'un nœud
                for node in self.nodes.values():
                    if node.contains(mx, my, self.offset, self.zoom):
                        node.dragging = True
                        self._dragged_node = node
                        self._settled = False
                        return

                # Pan au clic gauche si aucun nœud sélectionné
                self._panning   = True
                self._pan_start = (mx, my)
                self._pan_origin = (self.offset[0], self.offset[1])

            elif event.button in (2, 3):
                # Pan clic milieu / droit
                self._panning   = True
                self._pan_start = (mx, my)
                self._pan_origin = (self.offset[0], self.offset[1])

            elif event.button == 4:   # Molette haut → zoom +
                self._zoom_at(mx, my, 1.1)
            elif event.button == 5:   # Molette bas  → zoom −
                self._zoom_at(mx, my, 1 / 1.1)

        elif event.type == pygame.MOUSEBUTTONUP:
            if self._dragged_node:
                self._dragged_node.dragging = False
                self._dragged_node = None
            self._panning = False

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos

            # Déplacer le nœud dragué
            if self._dragged_node:
                self._dragged_node.x = (mx - self.offset[0]) / self.zoom
                self._dragged_node.y = (my - self.offset[1]) / self.zoom
                return

            # Pan
            if self._panning:
                self.offset[0] = self._pan_origin[0] + (mx - self._pan_start[0])
                self.offset[1] = self._pan_origin[1] + (my - self._pan_start[1])
                return

            # Hover
            self._hovered_node = None
            for node in self.nodes.values():
                if node.contains(mx, my, self.offset, self.zoom):
                    self._hovered_node = node
                    break

    def _zoom_at(self, mx: float, my: float, factor: float):
        """Zoom centré sur la position souris."""
        new_zoom = max(0.2, min(4.0, self.zoom * factor))
        scale = new_zoom / self.zoom
        self.offset[0] = mx + (self.offset[0] - mx) * scale
        self.offset[1] = my + (self.offset[1] - my) * scale
        self.zoom = new_zoom

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _draw_grid(self):
        """Grille de fond légère façon terminal."""
        w, h = self.screen.get_size()
        step = max(20, int(60 * self.zoom))
        ox   = int(self.offset[0]) % step
        oy   = int(self.offset[1]) % step
        for x in range(ox, w, step):
            pygame.draw.line(self.screen, C_GRID, (x, 0), (x, h), 1)
        for y in range(oy, h, step):
            pygame.draw.line(self.screen, C_GRID, (0, y), (w, y), 1)

    def _draw_edge(self, a: Node, b: Node):
        ax, ay = a.screen_pos(self.offset, self.zoom)
        bx, by = b.screen_pos(self.offset, self.zoom)

        # Lueur (trait large + translucide)
        glow_surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        pygame.draw.line(glow_surf, (*C_EDGE_GLOW, 80), (ax, ay), (bx, by),
                         max(1, int(6 * self.zoom)))
        self.screen.blit(glow_surf, (0, 0))

        # Trait principal
        pygame.draw.line(self.screen, C_EDGE, (ax, ay), (bx, by),
                         max(1, int(1.5 * self.zoom)))

        # Petits points de terminaison
        pygame.draw.circle(self.screen, C_EDGE, (ax, ay), max(2, int(3 * self.zoom)))
        pygame.draw.circle(self.screen, C_EDGE, (bx, by), max(2, int(3 * self.zoom)))

    def _draw_node(self, node: Node):
        sx, sy = node.screen_pos(self.offset, self.zoom)
        r  = max(4, int(node.radius * self.zoom))

        if node.dragging:
            color   = C_NODE_DRAG
            outline = C_NODE_DRAG
        elif node is self._hovered_node:
            color   = C_NODE_HOVER
            outline = C_NODE_HOVER
        elif node.is_self:
            color   = C_NODE_SELF
            outline = C_OUTLINE_SELF
        else:
            color   = C_NODE_OTHER
            outline = C_OUTLINE_OTH

        # Halo
        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*color, 30), (r * 2, r * 2), r * 2)
        self.screen.blit(halo, (sx - r * 2, sy - r * 2))

        # Fond du nœud
        pygame.draw.circle(self.screen, (10, 12, 18), (sx, sy), r)

        # Contour
        thickness = max(1, int((3 if node.is_self else 2) * self.zoom))
        pygame.draw.circle(self.screen, outline, (sx, sy), r, thickness)

        # Point central
        pygame.draw.circle(self.screen, color, (sx, sy), max(2, r // 3))

        # Label
        label_col = C_LABEL_SELF if node.is_self else C_LABEL_OTHER
        label     = self._font_title.render(node.id, True, label_col) if node.is_self \
                    else self._font_label.render(node.id, True, label_col)
        lx = sx - label.get_width() // 2
        ly = sy + r + max(4, int(6 * self.zoom))
        # Fond semi-transparent derrière le label
        pad = 3
        bg = pygame.Surface((label.get_width() + pad * 2, label.get_height() + pad * 2), pygame.SRCALPHA)
        bg.fill((10, 12, 18, 180))
        self.screen.blit(bg, (lx - pad, ly - pad))
        self.screen.blit(label, (lx, ly))

    def draw(self):
        """Appeler depuis DefaultState.display(), avant pygame.display.flip()."""
        self._simulate()

        self._draw_grid()

        # Arêtes en premier (sous les nœuds)
        for (a_id, b_id) in self.edges:
            a = self.nodes.get(a_id)
            b = self.nodes.get(b_id)
            if a and b:
                self._draw_edge(a, b)

        # Nœuds
        for node in self.nodes.values():
            self._draw_node(node)

        # HUD info
        self._draw_hud()

    def _draw_hud(self):
        """Affiche les informations contextuelles en surimpression."""
        if self._hovered_node:
            info = f"[ {self._hovered_node.id} ]"
            surf = self._font_title.render(info, True, C_NODE_HOVER)
            w, h = self.screen.get_size()
            self.screen.blit(surf, (w - surf.get_width() - 12, 10))

        zoom_txt = self._font_label.render(f"zoom {self.zoom:.2f}×", True, (50, 70, 60))
        self.screen.blit(zoom_txt, (10, 10))

        tip = self._font_label.render(
            "drag: move node  |  scroll: zoom  |  right-drag: pan", True, (40, 60, 50)
        )
        _, h = self.screen.get_size()
        self.screen.blit(tip, (10, h - tip.get_height() - 10))
