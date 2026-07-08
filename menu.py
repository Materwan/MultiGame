import os
import sys
import random
import math

import pygame

from client_utils import *

GREEN_HEAD = (200, 255, 200)
GREEN_FULL = (0, 255, 70)
GREEN_DIM = (0, 140, 40)
GREEN_DARK = (0, 60, 20)

BTN_COLOR = (0, 255, 70)
BTN_HOVER_BG = (0, 255, 70, 40)
BTN_BORDER = (0, 200, 50)
BTN_HOVER_BORDER = (100, 255, 130)
BTN_TEXT = (0, 255, 70)
BTN_HOVER_TEXT = (200, 255, 200)


class Button:

    def __init__(
        self, label: str, center: tuple, w: int, h: int, font: pygame.font.Font
    ):
        self.label = label
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = center
        self.font = font
        self.hovered = False
        self._anim = 0.0  # 0..1 hover lerp
        self._tick = 0  # glitch timer

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)
        target = 1.0 if self.hovered else 0.0
        self._anim += (target - self._anim) * 0.15
        self._tick += 1

    def draw(self, surface: pygame.Surface):
        a = self._anim

        # Border color lerp
        border_col = (
            int(BTN_BORDER[0] + (BTN_HOVER_BORDER[0] - BTN_BORDER[0]) * a),
            int(BTN_BORDER[1] + (BTN_HOVER_BORDER[1] - BTN_BORDER[1]) * a),
            int(BTN_BORDER[2] + (BTN_HOVER_BORDER[2] - BTN_BORDER[2]) * a),
        )
        text_col = (
            int(BTN_TEXT[0] + (BTN_HOVER_TEXT[0] - BTN_TEXT[0]) * a),
            int(BTN_TEXT[1] + (BTN_HOVER_TEXT[1] - BTN_TEXT[1]) * a),
            int(BTN_TEXT[2] + (BTN_HOVER_TEXT[2] - BTN_TEXT[2]) * a),
        )

        # Semi-transparent background on hover
        if a > 0.01:
            hover_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            hover_surf.fill((0, 255, 70, int(35 * a)))
            surface.blit(hover_surf, self.rect.topleft)

        # Corner brackets  [ ]
        pad = 8
        blen = 12
        x, y, w, h = self.rect
        corners = [
            ((x + pad, y + pad + blen), (x + pad, y + pad), (x + pad + blen, y + pad)),
            (
                (x + w - pad - blen, y + pad),
                (x + w - pad, y + pad),
                (x + w - pad, y + pad + blen),
            ),
            (
                (x + pad, y + h - pad - blen),
                (x + pad, y + h - pad),
                (x + pad + blen, y + h - pad),
            ),
            (
                (x + w - pad - blen, y + h - pad),
                (x + w - pad, y + h - pad),
                (x + w - pad, y + h - pad - blen),
            ),
        ]
        for pts in corners:
            pygame.draw.lines(surface, border_col, False, pts, 2)

        # Glitch scanline on hover
        if self.hovered and self._tick % 40 < 4:
            scan_y = self.rect.centery + random.randint(-8, 8)
            scan_surf = pygame.Surface((self.rect.width - 2 * pad, 2), pygame.SRCALPHA)
            scan_surf.fill((0, 255, 70, 60))
            surface.blit(scan_surf, (x + pad, scan_y))

        # Label — glitch swap one char when hovered
        label = self.label
        if self.hovered and self._tick % 20 < 3:
            idx = random.randint(0, len(label) - 1)
            label = label[:idx] + random.choice("01_#@") + label[idx + 1 :]

        text_surf = self.font.render(label, True, text_col)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class DefaultMenu(DefaultState):

    def __init__(self, screen: pygame.Surface, manager: BaseManager):
        super().__init__(screen, manager)

        self.mono_sm = pygame.font.SysFont("Consolas", 18, bold=True)
        self.mono_btn = pygame.font.SysFont("Consolas", 22, bold=True)

        self.char_w = 18
        self.char_h = 22
        self._init_columns()
        self._init_buttons()

    def _init_columns(self):
        w, h = self.screen.get_size()
        self.cols = w // self.char_w
        self.columns = []
        for _ in range(self.cols):
            trail_len = random.randint(6, 20)
            self.columns.append(
                {
                    "y": random.randint(-500, 0),
                    "speed": random.uniform(3, 10),
                    "trail": trail_len,
                    "chars": [random.choice("01") for _ in range(trail_len)],
                }
            )

    @abstractmethod
    def _init_buttons(self):
        pass

    def event(self, events: List[pygame.event.Event]):
        super().event(events)

    def update(self):
        super().update()
        w, h = self.screen.get_size()
        new_cols = w // self.char_w
        if new_cols != len(self.columns):
            self._init_columns()
            self._init_buttons()

        for col in self.columns:
            col["y"] += col["speed"]
            col["chars"][random.randint(0, len(col["chars"]) - 1)] = random.choice("01")
            if col["y"] - col["trail"] * self.char_h > h:
                col["y"] = random.randint(-200, 0)
                col["speed"] = random.uniform(3, 10)
                col["trail"] = random.randint(6, 20)
                col["chars"] = [random.choice("01") for _ in range(col["trail"])]

        mouse_pos = pygame.mouse.get_pos()
        for btn in self.buttons.values():
            btn.update(mouse_pos)

    def display(self):
        self.screen.fill(BLACK)
        w, h = self.screen.get_size()

        # Rain
        for i, col in enumerate(self.columns):
            x = i * self.char_w
            for j in range(col["trail"]):
                y = int(col["y"]) - j * self.char_h
                if y < -self.char_h or y > h:
                    continue
                if j == 0:
                    color = GREEN_HEAD
                elif j < 3:
                    color = GREEN_FULL
                elif j < col["trail"] // 2:
                    color = GREEN_DIM
                else:
                    color = GREEN_DARK
                surface = self.mono_sm.render(col["chars"][j], True, color)
                self.screen.blit(surface, (x, y))

        # Buttons
        for btn in self.buttons.values():
            btn.draw(self.screen)


class PrincipalMenu(DefaultMenu):

    def __init__(self, screen: pygame.Surface, manager: BaseManager):
        super().__init__(screen, manager)

    def _init_buttons(self):
        w, h = self.screen.get_size()
        cx = w // 2
        cy = h // 2
        gap = 70
        self.buttons = {
            "play": Button("[ PLAY ]", (cx, cy - gap), 220, 48, self.mono_btn),
            "settings": Button("[ SETTINGS ]", (cx, cy), 220, 48, self.mono_btn),
            "quit": Button("[ QUIT ]", (cx, cy + gap), 220, 48, self.mono_btn),
        }

    def event(self, events: List[pygame.event.Event]):
        super().event(events)
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.buttons["quit"].rect.collidepoint(event.pos):
                    self.manager.running = False
                if self.buttons["settings"].rect.collidepoint(event.pos):
                    self.manager.change_state("Settings_Menu")
                if self.buttons["play"].rect.collidepoint(event.pos):
                    self.manager.change_state("Play_Menu")

    def update(self):
        super().update()

    def display(self):
        super().display()

        pygame.display.flip()


class SettingsMenu(DefaultMenu):

    def __init__(self, screen: pygame.Surface, manager: BaseManager):
        super().__init__(screen, manager)

    def _init_buttons(self):
        w, h = self.screen.get_size()
        cx = w // 2
        cy = h // 2
        gap = 70
        self.buttons = {
            "return": Button("[ RETURN ]", (cx, cy + gap), 220, 48, self.mono_btn),
        }

    def event(self, events: List[pygame.event.Event]):
        super().event(events)
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.buttons["return"].rect.collidepoint(event.pos):
                    self.manager.change_state("Principal_Menu")

    def update(self):
        super().update()

    def display(self):
        super().display()

        pygame.display.flip()


class PlayMenu(DefaultMenu):

    def __init__(self, screen, manager):
        super().__init__(screen, manager)

    def _init_buttons(self):
        w, h = self.screen.get_size()
        cx = w // 2
        cy = h // 2
        gap = 70
        self.buttons = {
            "solo": Button("[ SOLO ]", (cx, cy - gap), 220, 48, self.mono_btn),
            "multi": Button("[ MULTI ]", (cx, cy), 220, 48, self.mono_btn),
            "return": Button("[ RETURN ]", (cx, cy + gap), 220, 48, self.mono_btn),
        }

    def event(self, events):
        super().event(events)
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.buttons["solo"].rect.collidepoint(event.pos):
                    self.manager.change_state("Solo_Game")
                if self.buttons["multi"].rect.collidepoint(event.pos):
                    self.manager.change_state("Multi_Game")
                if self.buttons["return"].rect.collidepoint(event.pos):
                    self.manager.change_state("Principal_Menu")

    def update(self):
        super().update()

    def display(self):
        super().display()

        pygame.display.flip()
