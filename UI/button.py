import pygame
from typing import Tuple, List, Callable
from abc import ABC, abstractmethod

from UI.ui_utils import *


class DefaultButton(DefaultUIElt):
    """Default button class.

    Variables:
        - screen (Surface): the surface on which draw the element."""

    def __init__(
        self,
        screen: pygame.Surface,
        position: Tuple[int, int] | List[int] | pygame.Vector2,
        hover_fn: Callable = None,
        hover_args: Tuple = (),
        click_fn: Callable = None,
        click_args: Tuple = (),
    ):

        self.screen = screen

        self.pos = to_vect(position)

        self.hover = False
        self.press = False

        self.hover_fn = hover_fn if hover_fn else lambda: 0
        self.click_fn = click_fn if click_fn else lambda: 0

        self.hover_fn_args = hover_args
        self.click_fn_args = click_args


class DefaultSquareButton(DefaultButton):
    """Default class for square button.
    Include hover and click detection.

    Variables:
        - screen (Surface): the surface on which draw the button.
        - position (Coordinate): the topleft position of the button.
        - size (Coordinate): the size of the button.
        - hover_fn (Methode): the methode to execute when the button is hover.
        - click_fn (Methode): the methode to execute when the button is click.
        - x (int): the left position of the button.
        - y (int): the top position of the button.
        - width (int): the width of the button.
        - height (int): the height of the button.

    Methodes:
        - _handle_event(List[Event], Coordinate): manage default event (hover and click).
        - draw(): draw the button on the screen."""

    def __init__(
        self,
        screen: pygame.Surface,
        position: Tuple[int, int] | List[int] | pygame.Vector2,
        size: Tuple[int, int] | List[int] | pygame.Vector2,
        hover_fn: Callable = None,
        hover_args: Tuple = (),
        click_fn: Callable = None,
        click_args: Tuple = (),
    ):
        super().__init__(screen, position, hover_fn, hover_args, click_fn, click_args)

        self.size = to_vect(size)

    @property
    def x(self):
        return self.pos.x

    @property
    def y(self):
        return self.pos.y

    @property
    def width(self):
        return self.size.x

    @property
    def height(self):
        return self.size.y

    def _handle_event(
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = pygame.Vector2(0, 0),
        zoom: Optional[float] = 1,
    ):

        ms_x, ms_y = ms_pos
        coll_rect = world_to_screen_rect(
            pygame.Rect(self.x, self.y, self.width, self.height), offset, zoom
        )

        self.hover = coll_rect.collidepoint(ms_x, ms_y)

        if self.hover and self.hover_fn:
            self.hover_fn(*self.hover_fn_args)

        for event in events:

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == pygame.BUTTON_LEFT:
                    self.press = self.hover
                    if self.press and self.click_fn:
                        self.click_fn(*self.click_fn_args)

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == pygame.BUTTON_LEFT:
                    self.press = False


class DefaultCircleButton(DefaultButton):
    """Default class for circle button.
    Include hover and click detection.

    Variables:
        - screen (Surface): the surface on which draw the button.
        - position (Coordinate): the topleft position of the button.
        - radius (int): the radius of the button.
        - hover_fn (Methode): the methode to execute when the button is hover.
        - click_fn (Methode): the methode to execute when the button is click.
        - x (int): the left position of the button.
        - y (int): the top position of the button.

    Methodes:
        - _handle_event(List[Event], Coordinate): manage default event (hover and click).
        - draw(): draw the button on the screen."""

    def __init__(
        self,
        screen: pygame.Surface,
        position: Tuple[int, int] | List[int] | pygame.Vector2,
        radius: int,
        hover_fn: Callable = None,
        hover_args: Tuple = (),
        click_fn: Callable = None,
        click_args: Tuple = (),
    ):
        super().__init__(screen, position, hover_fn, hover_args, click_fn, click_args)

        self.radius = radius

    @property
    def x(self):
        return self.pos.x

    @property
    def y(self):
        return self.pos.y

    def _handle_event(
        self,
        events: List[pygame.event.Event],
        ms_pos: Tuple[int, int] | List[int],
        offset: Optional[pygame.Vector2] = pygame.Vector2(0, 0),
        zoom: Optional[float] = 1,
    ):

        ms_x, ms_y = ms_pos

        self.hover = (
            distance(ms_pos, world_to_screen(self.pos, offset, zoom))
            <= self.radius * zoom
        )

        if self.hover and self.hover_fn:
            self.hover_fn(*self.hover_fn_args)

        for event in events:

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == pygame.BUTTON_LEFT:
                    self.press = self.hover
                    if self.press and self.click_fn:
                        self.click_fn(*self.click_fn_args)

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == pygame.BUTTON_LEFT:
                    self.press = False


class CloseButton(DefaultCircleButton):
    """Class for close button.
    Include hover and click detection.

    Variables:
        - screen (Surface): the surface on which draw the button.
        - position (Coordinate): the topleft position of the button.
        - radius (int): the radius of the button.
        - hover_fn (Methode): the methode to execute when the button is hover.
        - click_fn (Methode): the methode to execute when the button is click.
        - x (int): the left position of the button.
        - y (int): the top position of the button.

    Methodes:
        - _handle_event(List[Event], Coordinate): manage default event (hover and click).
        - _draw_cross(): draw the cross on the button.
        - draw(): draw the button on the screen."""

    def __init__(
        self,
        screen: pygame.Surface,
        position: Tuple[int, int] | List[int] | pygame.Vector2,
        radius: int,
        hover_fn: Callable = None,
        hover_args: Tuple = (),
        click_fn: Callable = None,
        click_args: Tuple = (),
    ):

        super().__init__(
            screen, position, radius, hover_fn, hover_args, click_fn, click_args
        )

    def _draw_cross(self, offset: pygame.Vector2, zoom: float):
        color = UITheme.GREEN
        line_width = 3

        start_pos1 = ((self.x - self.radius // 2), (self.y - self.radius // 2))
        end_pos1 = ((self.x + self.radius // 2), (self.y + self.radius // 2))

        start_pos2 = ((self.x - self.radius // 2), (self.y + self.radius // 2))
        end_pos2 = ((self.x + self.radius // 2), (self.y - self.radius // 2))

        pygame.draw.line(
            self.screen,
            color,
            world_to_screen(start_pos1, offset, zoom),
            world_to_screen(end_pos1, offset, zoom),
            line_width,
        )
        pygame.draw.line(
            self.screen,
            color,
            world_to_screen(start_pos2, offset, zoom),
            world_to_screen(end_pos2, offset, zoom),
            line_width,
        )

    def draw(self, offset: pygame.Vector2, zoom: float):
        color = UITheme.HOVER_BLACK if self.hover else UITheme.BLACK
        pygame.draw.circle(
            self.screen,
            color,
            world_to_screen(self.pos, offset, zoom),
            self.radius * zoom,
        )
        self._draw_cross(offset, zoom)


class SimpleSquareButton(DefaultSquareButton):

    def __init__(
        self,
        screen: pygame.Surface,
        position: Tuple[int, int] | List[int] | pygame.Vector2,
        size: Tuple[int, int] | List[int] | pygame.Vector2,
        text: str,
        default_font_size: int,
        hover_fn: Callable = None,
        hover_args: Tuple = (),
        click_fn: Callable = None,
        click_args: Tuple = (),
    ):
        super().__init__(
            screen, position, size, hover_fn, hover_args, click_fn, click_args
        )

        self.text = text
        self.default_font_size = default_font_size

    def draw(self, offset: pygame.Vector2, zoom: float):

        _font_size = int(self.default_font_size * zoom)
        _font = pygame.font.SysFont(
            UITheme.FONT_NAME,
            _font_size,
        )
        screen_rect = world_to_screen_rect(
            pygame.Rect(self.pos.x, self.pos.y, self.size.x, self.size.y),
            offset,
            zoom,
        )
        if self.hover:
            pygame.draw.rect(
                self.screen,
                UITheme.HOVER_BLACK,
                screen_rect,
            )
        pygame.draw.rect(
            self.screen,
            UITheme.GREEN,
            screen_rect,
            1,
        )
        text_surf = _font.render(self.text, False, UITheme.GREEN)
        text_surf_size = text_surf.get_size()
        self.screen.blit(
            text_surf,
            (
                screen_rect.x + (screen_rect.width - text_surf_size[0]) // 2,
                screen_rect.y + (screen_rect.height - text_surf_size[1]) // 2,
            ),
        )


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((400, 400))
    clock = pygame.time.Clock()

    running = True

    def close():
        global running
        running = False

    button = CloseButton(screen, (200, 200), 30, clicked_fn=close)

    while running:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

        ms_pos = pygame.mouse.get_pos()
        button._handle_event(events, ms_pos)

        screen.fill((0, 0, 0))
        button.draw()
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
