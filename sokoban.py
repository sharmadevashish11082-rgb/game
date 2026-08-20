"""Sokoban — push every box onto a goal. Mind the corners."""
import pygame

try:
    from .engine import Game, draw_text, WIDTH, HEIGHT
except ImportError:  # allow direct run: python games/sokoban.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, WIDTH, HEIGHT

TILE = 54
OX = (WIDTH - TILE * 7) // 2
OY = 60

LEVELS = [
    ["#######",
     "#     #",
     "# .$. #",
     "#  @  #",
     "# .$. #",
     "#     #",
     "#######"],
    ["########",
     "#      #",
     "# .$   #",
     "#  $.  #",
     "#   $ .#",
     "#   @  #",
     "#      #",
     "########"],
    ["########",
     "#      #",
     "#  $$  #",
     "# .. ..#",
     "#  ..  #",
     "#  @   #",
     "#      #",
     "########"],
    ["#########",
     "#   #   #",
     "# $ . . #",
     "#   #   #",
     "# @ #   #",
     "#   #   #",
     "# $ . . #",
     "#   #   #",
     "#########"],
    ["##########",
     "#   #    #",
     "# .$#.$  #",
     "#  # #   #",
     "#    #   #",
     "# $$ . . #",
     "#  @     #",
     "#        #",
     "##########"],
    ["########",
     "#  .#  #",
     "#  $#  #",
     "#      #",
     "#  . $ #",
     "#  $ . #",
     "#  @   #",
     "#  #   #",
     "########"],
]


class Game(Game):
    name = "Sokoban"
    emoji = "🧩"
    tagline = "Push the boxes onto the dots. Think ahead."
    controls = "Arrows/WASD push · U undo · R restart · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.level = 0
        self.load_level()

    def load_level(self):
        rows = LEVELS[self.level]
        self.w = max(len(r) for r in rows)
        self.h = len(rows)
        self.grid = [list(r.ljust(self.w)) for r in rows]
        self.boxes = {}
        self.goals = set()
        for y, row in enumerate(self.grid):
            for x, c in enumerate(row):
                if c == "@":
                    self.px, self.py = x, y
                    self.grid[y][x] = " "
                elif c == "+":
                    self.px, self.py = x, y
                    self.grid[y][x] = "."
                    self.goals.add((x, y))
                elif c == "$":
                    self.boxes[(x, y)] = False
                    self.grid[y][x] = " "
                elif c == "*":
                    self.boxes[(x, y)] = True
                    self.goals.add((x, y))
                    self.grid[y][x] = " "
                elif c == ".":
                    self.goals.add((x, y))
        self.moves = 0
        self.undo_stack = []
        self.won = False
        self.won_t = 0.0

    def handle_event(self, event):
        super().handle_event(event)
        if self.won:
            choice = self.menu_choice(event)
            if choice == 0:
                self.level += 1
                if self.level >= len(LEVELS):
                    self.reset()
                else:
                    self.load_level()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN:
            d = None
            if event.key in (pygame.K_LEFT, pygame.K_a):
                d = (-1, 0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                d = (1, 0)
            elif event.key in (pygame.K_UP, pygame.K_w):
                d = (0, -1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                d = (0, 1)
            elif event.key == pygame.K_u:
                self.undo()
            elif event.key == pygame.K_r:
                self.load_level()
            if d:
                self.push(d)

    def push(self, d):
        nx, ny = self.px + d[0], self.py + d[1]
        if self.grid[ny][nx] == "#":
            return
        if (nx, ny) in self.boxes:
            bx, by = nx + d[0], ny + d[1]
            if self.grid[by][bx] == "#" or (bx, by) in self.boxes:
                return
            self.undo_stack.append((self.px, self.py, (nx, ny), (bx, by),
                                    self.boxes[(nx, ny)]))
            del self.boxes[(nx, ny)]
            self.boxes[(bx, by)] = (bx, by) in self.goals
        else:
            self.undo_stack.append((self.px, self.py, None, None, None))
        self.px, self.py = nx, ny
        self.moves += 1
        if all(on for on in self.boxes.values()):
            self.won = True
            self.won_t = 1.2
            self.show_menu(f"LEVEL {self.level + 1} CLEARED!",
                           ["Next Level", "Main Menu"] if self.level + 1 < len(LEVELS)
                           else ["Play Again", "Main Menu"],
                           f"{self.moves} moves", title_color=(120, 255, 150))

    def undo(self):
        if not self.undo_stack:
            return
        px, py, box_from, box_to, was_on = self.undo_stack.pop()
        self.px, self.py = px, py
        if box_from and box_to:
            del self.boxes[box_to]
            self.boxes[box_from] = was_on
        self.moves += 1

    def update(self, dt):
        pass

    def draw(self, surf):
        surf.fill((24, 26, 40))
        draw_text(surf, f"SOKOBAN — Level {self.level + 1}/{len(LEVELS)}", 26,
                  (255, 208, 74), (WIDTH // 2, 18), align="center", bold=True, outline=1)
        for y in range(self.h):
            for x in range(self.w):
                rect = pygame.Rect(OX + x * TILE, OY + y * TILE, TILE, TILE)
                c = self.grid[y][x]
                if c == "#":
                    pygame.draw.rect(surf, (70, 74, 96), rect, border_radius=6)
                    pygame.draw.rect(surf, (96, 100, 126), rect, 2, border_radius=6)
                else:
                    pygame.draw.rect(surf, (34, 36, 56), rect, border_radius=4)
                if (x, y) in self.goals:
                    pygame.draw.circle(surf, (255, 208, 74),
                                       (rect.centerx, rect.centery), 7)
        for (x, y), on in self.boxes.items():
            rect = pygame.Rect(OX + x * TILE + 4, OY + y * TILE + 4, TILE - 8, TILE - 8)
            pygame.draw.rect(surf, (180, 130, 60) if not on else (110, 200, 110),
                             rect, border_radius=8)
            pygame.draw.rect(surf, (90, 62, 26) if not on else (50, 110, 60),
                             rect, 3, border_radius=8)
            pygame.draw.line(surf, (90, 62, 26) if not on else (50, 110, 60),
                             rect.topleft, rect.bottomright, 2)
        if not self.won:
            cx = OX + self.px * TILE + TILE // 2
            cy = OY + self.py * TILE + TILE // 2
            pygame.draw.circle(surf, (90, 160, 255), (cx, cy), 15)
            pygame.draw.circle(surf, (220, 235, 255), (cx - 5, cy - 4), 4)
            pygame.draw.circle(surf, (220, 235, 255), (cx + 5, cy - 4), 4)
        draw_text(surf, f"Moves: {self.moves}", 18, (220, 224, 240), (WIDTH // 2, 40),
                  align="center")
        draw_text(surf, "U undo · R restart", 14, (140, 146, 175), (WIDTH // 2, HEIGHT - 14),
                  align="center")
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/sokoban.py
    from games.engine import App
    App(Game).run()
