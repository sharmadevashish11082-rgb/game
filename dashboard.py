"""Arcade Dashboard — the home screen: filter, browse, and launch games.

Replaces the plain grid as the main menu: category tabs up top, a scrollable
card grid in the middle, and a details + PLAY panel at the bottom.
"""
import pygame

try:
    from .engine import Game, draw_text, Button, WIDTH, HEIGHT, clamp
    from . import (GAME_CLASSES, pacman, rpg, turn_rpg, tower_defense, bullet_hell,
                   galaga, topdown_racing, lane_racer, zombie_survival,
                   platform_shooter, fighting, beatemup, dungeon, sokoban, chess,
                   card_battle, civ, rts, tycoon, farming, survival)
except ImportError:  # allow direct run: python games/dashboard.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, Button, WIDTH, HEIGHT, clamp
    from games import (GAME_CLASSES, pacman, rpg, turn_rpg, tower_defense,
                       bullet_hell, galaga, topdown_racing, lane_racer,
                       zombie_survival, platform_shooter, fighting, beatemup,
                       dungeon, sokoban, chess, card_battle, civ, rts, tycoon,
                       farming, survival)

CATEGORIES = ["All", "Arcade", "Action", "RPG", "Strategy", "Racing",
              "Puzzle", "Sim"]
CATEGORY_OF = {
    pacman.Game: "Arcade",
    bullet_hell.Game: "Arcade",
    galaga.Game: "Arcade",
    topdown_racing.Game: "Racing",
    lane_racer.Game: "Racing",
    zombie_survival.Game: "Action",
    platform_shooter.Game: "Action",
    fighting.Game: "Action",
    beatemup.Game: "Action",
    rpg.Game: "RPG",
    turn_rpg.Game: "RPG",
    dungeon.Game: "RPG",
    tower_defense.Game: "Strategy",
    chess.Game: "Strategy",
    card_battle.Game: "Strategy",
    civ.Game: "Strategy",
    rts.Game: "Strategy",
    sokoban.Game: "Puzzle",
    tycoon.Game: "Sim",
    farming.Game: "Sim",
    survival.Game: "Sim",
}

COLS = 3
CARD_W, CARD_H, GAP = 292, 66, 10
GRID_X, GRID_Y = 14, 74
ROWS_VISIBLE = 5
PANEL_H = 112


class Dashboard(Game):
    name = "Freebuff Arcade"
    emoji = "🕹️"
    tagline = "21 Python games in one app"
    controls = "↑↓←→ select · Enter play · Esc quit"

    def __init__(self, app):
        super().__init__(app)
        self.category = "All"
        self.selected = 0
        self.scroll = 0
        self.played = 0
        self.last = ""
        self.t = 0.0
        self.play_btn = Button((WIDTH - 176, HEIGHT - 78, 150, 52),
                               "▶ PLAY", size=22, hover=(120, 255, 150))
        self.refresh()

    def refresh(self):
        if self.category == "All":
            self.filtered = list(GAME_CLASSES)
        else:
            self.filtered = [cls for cls in GAME_CLASSES
                             if CATEGORY_OF.get(cls) == self.category]
        self.selected = clamp(self.selected, 0, len(self.filtered) - 1)
        self.clamp_scroll()

    def clamp_scroll(self):
        rows = (len(self.filtered) + COLS - 1) // COLS
        self.scroll = clamp(self.scroll, 0, max(0, rows - ROWS_VISIBLE))
        row = self.selected // COLS
        if row < self.scroll:
            self.scroll = row
        elif row >= self.scroll + ROWS_VISIBLE:
            self.scroll = row - ROWS_VISIBLE + 1

    def tab_rects(self):
        n = len(CATEGORIES)
        tw = WIDTH // n
        return [pygame.Rect(i * tw, 26, tw, 30) for i in range(n)]

    def card_rect(self, i):
        row = i // COLS - self.scroll
        col = i % COLS
        return pygame.Rect(GRID_X + col * (CARD_W + GAP),
                           GRID_Y + row * (CARD_H + GAP), CARD_W, CARD_H)

    def launch(self, cls):
        self.played += 1
        self.last = cls.name
        self.app.set_game(cls(self.app))

    def handle_event(self, event):
        super().handle_event(event)
        if event.type == pygame.MOUSEWHEEL:
            self.scroll -= event.y
            self.clamp_scroll()
        if event.type == pygame.MOUSEMOTION:
            self.play_btn.handle(event)
            for i, rect in enumerate(self.tab_rects()):
                if rect.collidepoint(event.pos):
                    self.hover_tab = i
                    break
            else:
                self.hover_tab = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.tab_rects()):
                if rect.collidepoint(event.pos):
                    self.category = CATEGORIES[i]
                    self.selected = 0
                    self.refresh()
                    return
            for i in range(len(self.filtered)):
                if self.card_rect(i).collidepoint(event.pos):
                    self.selected = i
                    self.clamp_scroll()
                    return
            if self.play_btn.handle(event):
                self.launch(self.filtered[self.selected])
        if event.type == pygame.KEYDOWN:
            n = len(self.filtered)
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected = (self.selected - 1) % n
                self.clamp_scroll()
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected = (self.selected + 1) % n
                self.clamp_scroll()
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - COLS) % n
                self.clamp_scroll()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + COLS) % n
                self.clamp_scroll()
            elif event.key in (pygame.K_PAGEUP,):
                self.scroll -= 3
                self.clamp_scroll()
            elif event.key in (pygame.K_PAGEDOWN,):
                self.scroll += 3
                self.clamp_scroll()
            elif event.key in (pygame.K_TAB,):
                self.category = CATEGORIES[(CATEGORIES.index(self.category) + 1)
                                           % len(CATEGORIES)]
                self.selected = 0
                self.refresh()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.launch(self.filtered[self.selected])
            elif pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < n:
                    self.selected = idx
                    self.clamp_scroll()
                    self.launch(self.filtered[idx])

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        surf.fill((13, 15, 30))
        # subtle backdrop grid
        for gx in range(0, WIDTH, 48):
            pygame.draw.line(surf, (18, 21, 40), (gx, 0), (gx, HEIGHT))
        for gy in range(0, HEIGHT, 48):
            pygame.draw.line(surf, (18, 21, 40), (0, gy), (WIDTH, gy))

        draw_text(surf, "FREEBBUF ARCADE", 26, (255, 208, 74), (16, 4),
                  bold=True, outline=1)
        for i, cat in enumerate(CATEGORIES):
            rect = self.tab_rects()[i]
            count = len(GAME_CLASSES) if cat == "All" else \
                sum(1 for cls in GAME_CLASSES if CATEGORY_OF.get(cls) == cat)
            selected = self.category == cat
            hovered = getattr(self, "hover_tab", None) == i
            if selected:
                pygame.draw.rect(surf, (52, 62, 106), rect, border_radius=8)
                pygame.draw.rect(surf, (255, 208, 74), rect, 2, border_radius=8)
            elif hovered:
                pygame.draw.rect(surf, (36, 42, 74), rect, border_radius=8)
            draw_text(surf, f"{cat} ({count})", 13, (255, 208, 74) if selected
                      else (180, 186, 215), rect.center, align="center")

        for i in range(len(self.filtered)):
            row = i // COLS - self.scroll
            if not (0 <= row < ROWS_VISIBLE):
                continue
            cls = self.filtered[i]
            rect = self.card_rect(i)
            selected = i == self.selected
            pygame.draw.rect(surf, (32, 38, 66) if not selected else (52, 62, 106),
                             rect, border_radius=10)
            pygame.draw.rect(surf, (255, 208, 74) if selected else (76, 86, 128),
                             rect, 3 if selected else 1, border_radius=10)
            draw_text(surf, f"{cls.emoji}  {cls.name}", 19, (245, 246, 252),
                      (rect.x + 12, rect.y + 10), bold=selected)
            draw_text(surf, CATEGORY_OF.get(cls, "?"), 11,
                      (140, 148, 180), (rect.x + 12, rect.bottom - 20))
            draw_text(surf, cls.tagline, 12, (170, 176, 205),
                      (rect.x + 12, rect.y + 34), max_width=CARD_W - 24)

        # bottom panel
        panel = pygame.Rect(0, HEIGHT - PANEL_H, WIDTH, PANEL_H)
        pygame.draw.rect(surf, (22, 26, 48), panel)
        pygame.draw.rect(surf, (255, 208, 74), (0, HEIGHT - PANEL_H, WIDTH, 2))
        cls = self.filtered[self.selected]
        draw_text(surf, f"{cls.emoji}  {cls.name}", 24, (255, 208, 74),
                  (20, HEIGHT - PANEL_H + 10), bold=True)
        draw_text(surf, cls.tagline, 16, (210, 214, 232),
                  (20, HEIGHT - PANEL_H + 42))
        draw_text(surf, cls.controls, 13, (150, 158, 190),
                  (20, HEIGHT - PANEL_H + 68))
        draw_text(surf, f"Session: {self.played} played" +
                  (f" · last: {self.last}" if self.last else ""), 13,
                  (140, 148, 180), (WIDTH - 176, HEIGHT - 22),
                  align="topright")
        self.play_btn.draw(surf)
        draw_text(surf, "↑↓←→ browse · Enter/Space play · Tab category · "
                        "1-9 quick pick · Esc quit", 12, (110, 118, 150),
                  (WIDTH - 176, HEIGHT - 16), align="topright")
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/dashboard.py
    from games.engine import App
    App(Dashboard).run()
