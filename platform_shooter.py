"""Run & Gun — a side-scrolling platform shooter with 3 levels."""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         clamp)
except ImportError:  # allow direct run: python games/platform_shooter.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              clamp)

TILE = 40
# Real-feel platformer physics. At the 0.6 m/tile scale Earth gravity is
# ~654 px/s²; we use a slightly stronger 1200 px/s² (~18 m/s²) to keep the
# arcade snappiness. Terminal velocity, variable jumps and coyote time are
# all real jump physics.
GRAVITY = 1200.0
JUMP_V = 500.0
TERMINAL_FALL = 1300.0
JUMP_CUT = 0.45       # releasing jump mid-rise cuts upward speed to 45%
COYOTE_TIME = 0.08    # you can still jump briefly after walking off a ledge
JUMP_BUFFER = 0.12    # a jump pressed slightly before landing still fires
LEVELS = [
    ["############################################################",
     "#                                                          #",
     "#  C                 C                                     #",
     "#        PPPPPP                   C                        #",
     "#                                    PPPPPP                #",
     "#  E              C         E                    E         #",
     "#        C                    PPPPPP          C           #",
     "#                     PPPPPP                PPPPPP        #",
     "#  C         C          E         C                C      F#",
     "############################################################"],
    ["############################################################",
     "#                                                          #",
     "#        C        PPPPPP        C         PPPPPP           #",
     "#  E                    E                       E          #",
     "#        PPPPPP                C                          #",
     "#                                             C           #",
     "#  C         C        PPPPPP     PPPPPP        PPPPPP      #",
     "#  E                                                      #",
     "#                        C                    C          F#",
     "############################################################"],
    ["############################################################",
     "#  C     PPPPPP      C      PPPPPP      C      PPPPPP     #",
     "#  E                    E                       E         #",
     "#        C                          C                     #",
     "#                PPPPPP     PPPPPP       PPPPPP           #",
     "#  E                    E                    E            #",
     "#        PPPPPP                       C                  #",
     "#  C                    C              PPPPPP             #",
     "#                                     C               C F#",
     "############################################################"],
]


class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.face = 1
        self.hp = 100
        self.inv = 0.0
        self.fire_t = 0.0
        self.on_ground = False
        self.coyote_t = 0.0
        self.buffer_t = 0.0

    def rect(self):
        return pygame.Rect(int(self.x) - 12, int(self.y) - 26, 24, 40)


class Walker:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = random.choice([-1, 1]) * 40
        self.hp = 30
        self.dead = False

    def rect(self):
        return pygame.Rect(int(self.x) - 12, int(self.y) - 22, 24, 34)


class Flyer:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.base_y = y
        self.t = random.uniform(0, 6)
        self.hp = 20
        self.dead = False

    def rect(self):
        return pygame.Rect(int(self.x) - 12, int(self.y) - 12, 24, 24)


class Game(Game):
    name = "Run & Gun"
    emoji = "🔫"
    tagline = "Jump, shoot, and reach the flag."
    controls = "←→ move · Space jump · J shoot · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.level = 0
        self.lives = 3
        self.score = 0
        self.load_level()

    def load_level(self):
        rows = LEVELS[self.level]
        self.rows = [list(r) for r in rows]
        self.W = len(rows[0]) * TILE
        self.H = len(rows) * TILE
        self.player = Player(60, self.H - 120)
        self.enemies = []
        self.coins = []
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c == "E":
                    self.enemies.append(Walker(x * TILE + 20, y * TILE + 20))
                elif c == "F":
                    self.flag = (x * TILE, y * TILE)
                elif c == "C":
                    self.coins.append([x * TILE + 20, y * TILE + 20, True])
        self.camx = 0.0
        self.dead_t = 0.0
        self.complete = False
        self.complete_t = 0.0

    def solid(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if ty < 0 or ty >= len(self.rows):
            return False
        if tx < 0 or tx >= len(self.rows[ty]):
            return True
        return self.rows[ty][tx] == "#"

    def handle_event(self, event):
        super().handle_event(event)
        if self.lives <= 0:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self.player.fire_t = min(self.player.fire_t, 0.0)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.player.buffer_t = JUMP_BUFFER
        if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            if self.player.vy < 0:              # real jump cut on release
                self.player.vy *= JUMP_CUT

    def update(self, dt):
        self.particles.update(dt)
        if self.lives <= 0:
            return
        p = self.player
        p.inv = max(0.0, p.inv - dt)
        if self.complete:
            self.complete_t -= dt
            if self.complete_t <= 0:
                if self.level + 1 < len(LEVELS):
                    self.level += 1
                    self.load_level()
                else:
                    self.lives = 0
                    self.show_menu("ALL LEVELS CLEARED!", ["Play Again", "Main Menu"],
                                   f"Score: {self.score}", title_color=(120, 255, 150))
            return
        p.fire_t -= dt
        accel = 900
        if self.held(pygame.K_LEFT, pygame.K_a):
            p.vx -= accel * dt
            p.face = -1
        if self.held(pygame.K_RIGHT, pygame.K_d):
            p.vx += accel * dt
            p.face = 1
        p.vx *= (1 - 6 * dt) if not self.held(pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d) else (1 - 0.6 * dt)
        # Gravity with terminal velocity — falling objects stop accelerating.
        p.vy = min(p.vy + GRAVITY * dt, TERMINAL_FALL)
        # Jump with coyote time and input buffering.
        p.coyote_t = COYOTE_TIME if p.on_ground else max(0.0, p.coyote_t - dt)
        p.buffer_t = max(0.0, p.buffer_t - dt)
        if p.coyote_t > 0 and (p.buffer_t > 0 or self.held(pygame.K_SPACE)):
            p.vy = -JUMP_V
            p.on_ground = False
            p.coyote_t = 0.0
            p.buffer_t = 0.0
        # move X
        p.x += p.vx * dt
        if self.solid(p.x + 12 * (1 if p.vx > 0 else -1), p.y):
            p.vx = 0
        # move Y
        p.y += p.vy * dt
        p.on_ground = False
        if self.solid(p.x, p.y + 24):
            if p.vy > 0:
                p.y = int((p.y + 24) // TILE) * TILE - 24
                p.on_ground = True
                p.coyote_t = COYOTE_TIME
                p.vy = 0
            else:
                p.y = (int(p.y // TILE) + 1) * TILE + 26
                p.vy = 0
        if p.y > self.H + 80:
            self.hurt(50, respawn=True)

        if self.held(pygame.K_j) and p.fire_t <= 0:
            p.fire_t = 0.22
            self.pbullets = getattr(self, "pbullets", [])
            self.pbullets.append([p.x + p.face * 16, p.y - 8, p.face * 560, 1.0])
        for b in list(getattr(self, "pbullets", [])):
            b[0] += b[2] * dt
            b[3] -= dt
            if b[3] <= 0 or b[0] < 0 or b[0] > self.W:
                self.pbullets.remove(b)

        for e in self.enemies:
            if isinstance(e, Walker):
                e.x += e.vx * dt
                ahead = e.x + (14 if e.vx > 0 else -14)
                if self.solid(ahead, e.y) or not self.solid(ahead, e.y + 30):
                    e.vx = -e.vx
            else:
                e.t += dt
                e.y = e.base_y + math.sin(e.t * 2.0) * 30
            if not self.complete:
                r = e.rect()
                pr = p.rect()
                if p.inv <= 0 and r.colliderect(pr):
                    self.hurt(12)
                    e.x += (20 if e.x < p.x else -20)
        for b in list(getattr(self, "pbullets", [])):
            for e in list(self.enemies):
                if e.rect().collidepoint(b[0], b[1]):
                    e.hp -= 10
                    if b in self.pbullets:
                        self.pbullets.remove(b)
                    if e.hp <= 0:
                        self.enemies.remove(e)
                        self.score += 50
                        self.particles.burst(e.x, e.y, (255, 140, 60), n=12)
                    break
        for c in self.coins:
            if c[2] and abs(c[0] - p.x) < 26 and abs(c[1] - p.y) < 26:
                c[2] = False
                self.score += 10
                self.particles.burst(c[0], c[1], (255, 210, 80), n=8)
        if abs(p.x - self.flag[0]) < 40 and abs(p.y - self.flag[1]) < 40:
            self.complete = True
            self.complete_t = 1.5
            self.score += 200
        self.camx = clamp(p.x - WIDTH / 2, 0, max(0, self.W - WIDTH))

    def hurt(self, dmg, respawn=False):
        p = self.player
        p.hp -= dmg
        p.inv = 1.2
        if respawn:
            p.x, p.y = 60, self.H - 120
            p.hp = 100
            self.lives -= 1
            if self.lives <= 0:
                self.show_menu("GAME OVER", ["Retry", "Main Menu"], f"Score: {self.score}")
        elif p.hp <= 0:
            self.lives -= 1
            p.hp = 100
            p.x, p.y = 60, self.H - 120
            if self.lives <= 0:
                self.show_menu("GAME OVER", ["Retry", "Main Menu"], f"Score: {self.score}")

    def draw(self, surf):
        surf.fill((96, 150, 220))
        for y, row in enumerate(self.rows):
            for x, c in enumerate(row):
                sx = x * TILE - self.camx
                if c == "#":
                    pygame.draw.rect(surf, (70, 96, 60), (sx, y * TILE, TILE, TILE))
                    pygame.draw.rect(surf, (96, 128, 82), (sx, y * TILE, TILE, 8))
                elif c == "F":
                    pygame.draw.rect(surf, (120, 200, 120), (sx, y * TILE, TILE, TILE))
                    pygame.draw.line(surf, (255, 255, 255), (sx + 12, y * TILE), (sx + 12, y * TILE - 60), 3)
                    pygame.draw.polygon(surf, (255, 220, 80), [(sx + 12, y * TILE - 60), (sx + 34, y * TILE - 52), (sx + 12, y * TILE - 44)])
                elif c == "P":
                    pygame.draw.rect(surf, (150, 110, 70), (sx, y * TILE, TILE, 14))
        for c in self.coins:
            if c[2]:
                sx = c[0] - self.camx
                pygame.draw.circle(surf, (255, 210, 70), (int(sx), int(c[1])), 7)
                pygame.draw.circle(surf, (255, 255, 255), (int(sx), int(c[1])), 3)
        for e in self.enemies:
            sx = e.x - self.camx
            if isinstance(e, Walker):
                pygame.draw.rect(surf, (210, 80, 80), (sx - 12, e.y - 22, 24, 34), border_radius=6)
                pygame.draw.circle(surf, (255, 255, 255), (int(sx - 4), int(e.y - 14)), 3)
                pygame.draw.circle(surf, (255, 255, 255), (int(sx + 4), int(e.y - 14)), 3)
            else:
                pygame.draw.circle(surf, (150, 90, 220), (int(sx), int(e.y)), 12)
                pygame.draw.polygon(surf, (180, 130, 240),
                                    [(int(sx - 14), int(e.y)), (int(sx - 24), int(e.y + 8)), (int(sx - 10), int(e.y + 6))])
                pygame.draw.polygon(surf, (180, 130, 240),
                                    [(int(sx + 14), int(e.y)), (int(sx + 24), int(e.y + 8)), (int(sx + 10), int(e.y + 6))])
        p = self.player
        sx = p.x - self.camx
        pygame.draw.rect(surf, (90, 150, 255), (sx - 12, p.y - 26, 24, 40), border_radius=8)
        pygame.draw.circle(surf, (220, 235, 255), (int(sx + p.face * 4), int(p.y - 26)), 9)
        pygame.draw.rect(surf, (60, 90, 160), (sx + p.face * 10, p.y - 8, 18 * p.face, 6))
        for b in getattr(self, "pbullets", []):
            pygame.draw.circle(surf, (255, 230, 120), (int(b[0] - self.camx), int(b[1])), 4)
        self.particles.draw(surf)
        draw_text(surf, f"SCORE {self.score}", 20, (255, 255, 255), (14, 10))
        draw_text(surf, f"LEVEL {self.level + 1}/{len(LEVELS)}", 18, (255, 208, 74),
                  (WIDTH - 14, 10), align="topright")
        draw_text(surf, f"LIVES {'♥' * self.lives}", 18, (255, 120, 120), (14, 38))
        draw_health_bar(surf, 120, 12, 160, 14, p.hp / 100, fg=(90, 220, 120))
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/platform_shooter.py
    from games.engine import App
    App(Game).run()
