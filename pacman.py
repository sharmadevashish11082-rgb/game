"""Pac-Dash — a Pac-Man style maze chase."""
import math
import random

import pygame

try:
    from .engine import Game, draw_text, Particles, WIDTH, HEIGHT
except ImportError:  # allow direct run: python games/pacman.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, Particles, WIDTH, HEIGHT

TILE = 40
GRID_W, GRID_H = 21, 15
BAR = 42  # HUD strip at the top
TUNNEL_ROW = 7  # the side tunnels wrap around the screen edges, like the arcade

MAZE = [
    "#####################",
    "#.........#.........#",
    "#o##.###..#..###.##o#",
    "#...................#",
    "#.##.#..#####..#.##.#",
    "#....#...#.#...#....#",
    "####.#..##.##..#.####",
    "====.#...~~~...#.====",
    "####.#..##.##..#.####",
    "#....#...#.#...#....#",
    "#.##.#..#####..#.##.#",
    "#o.................o#",
    "#.###.##.###.##.###.#",
    "#...................#",
    "#####################",
]
assert all(len(r) == GRID_W for r in MAZE), "every maze row must be 21 tiles wide"
assert len(MAZE) == GRID_H

PAC_START = (10, 13)
GHOST_HOME = (10, 7)
GHOST_STARTS = [(9, 7), (10, 7), (11, 7), (12, 7)]
GHOST_COLORS = [(255, 70, 70), (255, 175, 220), (90, 235, 255), (255, 190, 90)]
# Blinky, Pinky, Inky, Clyde — each scatters to their own corner, as in the arcade.
SCATTER = [(1, 1), (19, 1), (1, 13), (19, 13)]
# The fruit appears twice per level at these dot counts, like the original:
# cherry at 70 dots, strawberry at 170.
FRUIT_POS = (10, 9)
FRUIT_SCHEDULE = {70: ("CHERRY", 100), 170: ("STRAWBERRY", 300)}


class Actor:
    def __init__(self, x, y, speed):
        self.cell = [x, y]
        self.prev = [x, y]
        self.dir = (0, 0)
        self.next_dir = (0, 0)
        self.progress = 0.0
        self.speed = speed

    def _cell_open(self, nx, ny, ghost=False):
        """Walkability of an absolute cell (no wrap)."""
        if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
            return False
        c = MAZE[ny][nx]
        if c == "#":
            return False
        if c == "~" and not ghost:      # the ghost house is ghost-only
            return False
        return True

    def can(self, dx, dy, ghost=False):
        nx, ny = self.cell[0] + dx, self.cell[1] + dy
        if ny == TUNNEL_ROW and (nx < 0 or nx >= GRID_W):
            return True                 # stepping off the tunnel wraps around
        return self._cell_open(nx, ny, ghost)

    def move(self, dt, ghost=False):
        self.progress += self.speed * dt
        while self.progress >= 1.0:
            self.progress -= 1.0
            self.prev = list(self.cell)
            if ghost:
                self.dir = self.pick_dir()
            else:
                self.dir = self.next_dir if self.can(*self.next_dir) else self.dir
            if not self.can(*self.dir, ghost=ghost):
                self.dir = (0, 0)
            self.cell[0] += self.dir[0]
            self.cell[1] += self.dir[1]
            # Arcade tunnel: leave one side of the screen, reappear on the other.
            if self.cell[1] == TUNNEL_ROW:
                if self.cell[0] < 0:
                    self.cell[0] = GRID_W - 1
                    self.prev[0] = GRID_W   # slide back in from the right edge
                elif self.cell[0] >= GRID_W:
                    self.cell[0] = 0
                    self.prev[0] = -1       # slide back in from the left edge

    def pixel(self):
        px = self.prev[0] + (self.cell[0] - self.prev[0]) * self.progress
        py = self.prev[1] + (self.cell[1] - self.prev[1]) * self.progress
        return px * TILE + TILE / 2, py * TILE + TILE / 2 + BAR

    def pick_dir(self):
        """True shortest-path steering, the way the arcade ghosts worked:
        BFS the whole maze toward the target, then take the first step of the
        shortest route. Ghosts may never reverse direction mid-corridor."""
        opts = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        valid = [d for d in opts if self.can(*d, ghost=True)]
        if not valid:
            return (0, 0)
        if self.target is None:          # frightened ghosts wander randomly
            return random.choice(valid)
        start = tuple(self.cell)
        target = (self.target[0] % GRID_W, self.target[1])
        dist = {start: 0}
        queue = [start]
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            if node == target:
                break
            for dx, dy in opts:
                nx, ny = node[0] + dx, node[1] + dy
                if ny == TUNNEL_ROW:
                    nx %= GRID_W
                nxt = (nx, ny)
                if nxt in dist or not self._cell_open(nx, ny, ghost=True):
                    continue
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
        best, best_d = None, 1e18
        for d in valid:
            if d == (-self.dir[0], -self.dir[1]) and len(valid) > 1:
                continue
            nx, ny = self.cell[0] + d[0], self.cell[1] + d[1]
            if ny == TUNNEL_ROW:
                nx %= GRID_W
            dd = dist.get((nx, ny), 1e9)
            if dd < best_d:
                best, best_d = d, dd
        return best or (0, 0)


class Ghost(Actor):
    def __init__(self, x, y, color, idx):
        super().__init__(x, y, 5.4)
        self.color = color
        self.idx = idx
        self.target = (0, 0)
        self.eaten = False
        self.home = [GHOST_HOME[0], GHOST_HOME[1]]
        self.start = list((x, y))

    def update(self, dt, pac, pac_dir, frightened, mode, blinky=None):
        """Each ghost uses its authentic arcade targeting rule."""
        if self.eaten:
            self.speed = 16.0           # eaten ghosts race home at double speed
            self.target = tuple(self.home)
        elif frightened:
            self.speed = 3.5            # scared ghosts crawl and wander
            self.target = None
        else:
            self.speed = 5.4 + 0.12 * self.idx
            if mode == "scatter":
                self.target = SCATTER[self.idx]
            elif self.idx == 0:         # Blinky — chases Pac-Man directly
                self.target = tuple(pac)
            elif self.idx == 1:         # Pinky — ambushes 4 cells ahead of Pac
                self.target = (pac[0] + pac_dir[0] * 4, pac[1] + pac_dir[1] * 4)
            elif self.idx == 2 and blinky is not None:  # Inky — vector from Blinky
                self.target = (pac[0] * 2 - blinky[0], pac[1] * 2 - blinky[1])
            elif self.idx == 3:         # Clyde — shy: retreats when close
                if math.hypot(pac[0] - self.cell[0], pac[1] - self.cell[1]) > 8:
                    self.target = tuple(pac)
                else:
                    self.target = SCATTER[3]
            else:
                self.target = tuple(pac)
        self.move(dt, ghost=True)
        if self.eaten and tuple(self.cell) == tuple(self.home):
            self.eaten = False          # back home: revived, exits again
            self.cell = list(self.start)
            self.prev = list(self.start)
            self.progress = 0.0
        return self.cell[0] == pac[0] and self.cell[1] == pac[1]


class Game(Game):
    name = "Pac-Dash"
    emoji = "👻"
    tagline = "Eat every dot. Dodge the ghosts."
    controls = "Arrows/WASD move · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.score = 0
        self.lives = 3
        self.level = 1
        self.fright = 0.0
        self.mode = "scatter"
        self.mode_t = 0.0
        self.over = False
        self.won = False
        self.won_t = 0.0
        self.dead_t = 0.0
        self.pac = Actor(PAC_START[0], PAC_START[1], 7.2)
        self.ghosts = [Ghost(*pos, col, i)
                       for i, (pos, col) in enumerate(zip(GHOST_STARTS, GHOST_COLORS))]
        self.dots_eaten = 0
        self.fruit = None
        self.build_dots()

    def build_dots(self):
        self.dots = set()
        self.pellets = set()
        for y, row in enumerate(MAZE):
            for x, c in enumerate(row):
                if c == ".":
                    self.dots.add((x, y))
                elif c == "o":
                    self.dots.add((x, y))
                    self.pellets.add((x, y))

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN and self.dead_t <= 0 and not self.won:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.pac.next_dir = (-1, 0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.pac.next_dir = (1, 0)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.pac.next_dir = (0, -1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.pac.next_dir = (0, 1)

    def respawn(self):
        self.pac = Actor(PAC_START[0], PAC_START[1], 7.2 + 0.4 * (self.level - 1))
        for g, start in zip(self.ghosts, GHOST_STARTS):
            g.cell = list(start)
            g.prev = list(start)
            g.dir = (0, 0)
            g.progress = 0.0
            g.eaten = False
        self.dead_t = 0.0

    def die(self):
        self.lives -= 1
        self.fright = 0.0
        self.dead_t = 1.2
        self.particles.burst(*self.pac.pixel(), (255, 224, 80), n=26, speed=180)
        if self.lives <= 0:
            self.over = True
            self.dead_t = 0.0
            self.show_menu("GAME OVER", ["Retry", "Main Menu"],
                           f"Score: {self.score} · Level {self.level}")

    def advance_level(self):
        self.level += 1
        self.won = False
        self.build_dots()
        self.respawn()

    def update(self, dt):
        self.particles.update(dt)
        if self.over:
            return
        if self.dead_t > 0:
            self.dead_t -= dt
            if self.dead_t <= 0:
                self.respawn()
            return
        if self.won:
            self.won_t -= dt
            if self.won_t <= 0:
                self.advance_level()
            return
        self.mode_t += dt
        if self.mode == "scatter" and self.mode_t > 7:
            self.mode, self.mode_t = "chase", 0
        elif self.mode == "chase" and self.mode_t > 18:
            self.mode, self.mode_t = "scatter", 0
        self.fright = max(0.0, self.fright - dt)

        self.pac.move(dt)
        pc = [int(round(self.pac.cell[0])), int(round(self.pac.cell[1]))]
        cell = (pc[0], pc[1])
        if cell in self.dots:
            self.dots.discard(cell)
            if cell in self.pellets:
                self.pellets.discard(cell)
                self.score += 50
                self.fright = 7.0
            else:
                self.score += 10
            self.dots_eaten += 1
            if self.dots_eaten in FRUIT_SCHEDULE and self.fruit is None:
                self.fruit = dict(kind=self.dots_eaten, t=9.0)

        if self.fruit:
            self.fruit["t"] -= dt
            if self.fruit["t"] <= 0:
                self.fruit = None
            elif cell == FRUIT_POS:
                score = FRUIT_SCHEDULE[self.fruit["kind"]][1]
                self.score += score
                self.particles.burst(*self.pac.pixel(), (255, 120, 120), n=14)
                self.fruit = None

        blinky = self.ghosts[0].cell
        for g in self.ghosts:
            hit = g.update(dt, pc, self.pac.dir, self.fright > 0, self.mode, blinky)
            if hit:
                if self.fright > 0:
                    g.eaten = True
                    self.score += 200
                    self.particles.burst(*g.pixel(), (255, 255, 140), n=18)
                else:
                    self.die()
                    break
        if not self.dots and not self.over:
            self.won = True
            self.won_t = 2.0
            self.score += 1000

    def draw_pac(self, surf):
        if self.dead_t > 0:
            return
        x, y = self.pac.pixel()
        x, y = int(x), int(y)
        r = TILE // 2 - 3
        pygame.draw.circle(surf, (255, 224, 80), (x, y), r)
        d = self.pac.dir
        ang = math.atan2(d[1], d[0]) if d != (0, 0) else 0.0
        top, bot = ang + 0.45, ang - 0.45
        tip = (x + math.cos(ang) * r, y + math.sin(ang) * r)
        pygame.draw.polygon(surf, (14, 16, 34),
                            [(x, y), (x + math.cos(top) * r, y + math.sin(top) * r), tip])
        pygame.draw.polygon(surf, (14, 16, 34),
                            [(x, y), (x + math.cos(bot) * r, y + math.sin(bot) * r), tip])
        pygame.draw.circle(surf, (20, 24, 50), (x - 4, y - 5), 2)

    def draw_ghost(self, surf, g):
        x, y = g.pixel()
        x, y = int(x), int(y)
        r = TILE // 2 - 4
        if g.eaten:
            pygame.draw.circle(surf, (255, 255, 255), (x - 5, y), 4)
            pygame.draw.circle(surf, (255, 255, 255), (x + 5, y), 4)
            pygame.draw.circle(surf, (40, 50, 100), (x - 5 + g.dir[0] * 2, y + g.dir[1] * 2), 2)
            pygame.draw.circle(surf, (40, 50, 100), (x + 5 + g.dir[0] * 2, y + g.dir[1] * 2), 2)
            return
        if self.fright > 0:
            col = (90, 130, 255)
            if self.fright < 2.0 and int(self.fright * 8) % 2 == 0:
                col = (240, 240, 255)
        else:
            col = g.color
        pygame.draw.circle(surf, col, (x, y - 2), r)
        pygame.draw.rect(surf, col, (x - r, y - 2, r * 2, r))
        for ex in (-5, 5):
            pygame.draw.circle(surf, (255, 255, 255), (x + ex, y - 3), 5)
            pygame.draw.circle(surf, (35, 45, 95), (x + ex + g.dir[0] * 2, y - 3 + g.dir[1] * 2), 2)

    def draw(self, surf):
        surf.fill((14, 16, 34))
        for y in range(GRID_H):
            for x in range(GRID_W):
                c = MAZE[y][x]
                rect = pygame.Rect(x * TILE, y * TILE + BAR, TILE, TILE)
                if c == "#":
                    pygame.draw.rect(surf, (30, 48, 128), rect, border_radius=6)
                elif c == "=":
                    pygame.draw.rect(surf, (46, 34, 92), rect, border_radius=6)
        for (x, y) in self.dots:
            cx, cy = x * TILE + TILE // 2, y * TILE + TILE // 2 + BAR
            if (x, y) in self.pellets:
                if int(pygame.time.get_ticks() / 400) % 2 == 0:
                    pygame.draw.circle(surf, (255, 210, 120), (cx, cy), 7)
            else:
                pygame.draw.circle(surf, (230, 210, 150), (cx, cy), 4)
        if self.fruit:
            x, y = FRUIT_POS[0] * TILE + TILE // 2, FRUIT_POS[1] * TILE + TILE // 2 + BAR
            if self.fruit["kind"] == 70:   # cherry
                pygame.draw.circle(surf, (220, 40, 40), (x - 5, y + 3), 6)
                pygame.draw.circle(surf, (220, 40, 40), (x + 5, y + 3), 6)
                pygame.draw.line(surf, (80, 200, 80), (x - 2, y - 1), (x - 1, y - 7), 2)
                pygame.draw.line(surf, (80, 200, 80), (x + 2, y - 1), (x + 1, y - 7), 2)
            else:                            # strawberry
                pygame.draw.ellipse(surf, (230, 60, 60), (x - 8, y - 4, 16, 14))
                pygame.draw.ellipse(surf, (80, 200, 80), (x - 3, y - 6, 6, 5))
                for sx, sy in ((-5, -1), (0, -2), (5, -1), (-3, 3), (3, 3)):
                    pygame.draw.circle(surf, (255, 220, 120), (x + sx, y + sy), 1)
        for g in self.ghosts:
            self.draw_ghost(surf, g)
        self.draw_pac(surf)
        self.particles.draw(surf)

        draw_text(surf, f"SCORE {self.score:06d}", 22, (255, 255, 255), (14, 8))
        draw_text(surf, f"LEVEL {self.level}  DOTS {len(self.dots)}", 22,
                  (255, 255, 255), (WIDTH - 14, 8), align="topright")
        for i in range(max(0, self.lives)):
            pygame.draw.circle(surf, (255, 224, 80), (30 + i * 26, 44), 9)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/pacman.py
    from games.engine import App
    App(Game).run()
