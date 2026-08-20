"""Main menu of the arcade: browse every game and launch it."""
import pygame

try:
    from .engine import Game, WIDTH, HEIGHT, draw_text, clamp
    from . import GAME_CLASSES
except ImportError:  # allow direct run: python games/launcher.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, WIDTH, HEIGHT, draw_text, clamp
    from games import GAME_CLASSES

COLS = 3
CARD_W, CARD_H, GAP = 286, 70, 12
MARGIN = 18


def card_rects():
    rects = []
    for i in range(len(GAME_CLASSES)):
        col = i % COLS
        row = i // COLS
        x = MARGIN + col * (CARD_W + GAP)
        y = 76 + row * (CARD_H + GAP)
        rects.append(pygame.Rect(x, y, CARD_W, CARD_H))
    return rects


class Launcher(Game):
    name = "Freebuff Arcade"
    emoji = "🕹️"
    tagline = "21 Python games in one app"
    controls = "↑↓←→ select · Enter play · Esc quit"

    def __init__(self, app):
        super().__init__(app)
        self.selected = 0
        self.t = 0.0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            n = len(GAME_CLASSES)
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - COLS) % n
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + COLS) % n
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected = (self.selected - 1) % n
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected = (self.selected + 1) % n
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.app.set_game(GAME_CLASSES[self.selected](self.app))
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < n:
                    self.selected = idx
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(card_rects()):
                if rect.collidepoint(event.pos):
                    self.selected = i
                    self.app.set_game(GAME_CLASSES[i](self.app))

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        surf.fill((14, 16, 32))
        draw_text(surf, "FREEBBUF ARCADE", 34, (255, 208, 74),
                  (WIDTH // 2, 22), align="center", bold=True, outline=2)
        draw_text(surf, f"{len(GAME_CLASSES)} games · all pure Python + pygame",
                  15, (150, 158, 190), (WIDTH // 2, 52), align="center")
        for i, cls in enumerate(GAME_CLASSES):
            rect = card_rects()[i]
            selected = i == self.selected
            pygame.draw.rect(surf, (34, 40, 68) if not selected else (52, 62, 106),
                             rect, border_radius=10)
            pygame.draw.rect(surf, (255, 208, 74) if selected else (80, 90, 130),
                             rect, 3 if selected else 1, border_radius=10)
            draw_text(surf, f"{i + 1:02d}", 14, (120, 128, 160), (rect.x + 12, rect.y + 8))
            draw_text(surf, f"{cls.emoji}  {cls.name}", 21, (245, 246, 252),
                      (rect.x + 14, rect.y + rect.h // 2), align="midleft")
        sel = GAME_CLASSES[self.selected]
        pygame.draw.rect(surf, (24, 28, 52), (0, HEIGHT - 66, WIDTH, 66))
        pygame.draw.rect(surf, (255, 208, 74), (0, HEIGHT - 66, WIDTH, 2))
        draw_text(surf, f"{sel.emoji} {sel.name}", 20, (255, 208, 74),
                  (MARGIN, HEIGHT - 58), bold=True)
        draw_text(surf, sel.tagline, 17, (210, 214, 232), (MARGIN, HEIGHT - 34))
        draw_text(surf, sel.controls, 15, (150, 158, 190), (WIDTH - MARGIN, HEIGHT - 36),
                  align="topright")
        hint = "Arrows/WASD select · Enter/Space play · 1-9 quick pick · Esc quit"
        draw_text(surf, hint, 13, (120, 128, 160), (WIDTH - MARGIN, HEIGHT - 14),
                  align="topright")


if __name__ == "__main__":
    # Allow running this file directly: python games/launcher.py
    from games.engine import App
    App(Launcher).run()
