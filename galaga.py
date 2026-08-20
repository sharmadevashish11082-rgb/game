"""Galaga Strike — formation waves, dive bombers and bonus ships."""
import math
import random

import pygame

try:
    from .engine import Game, draw_text, Particles, WIDTH, HEIGHT, clamp
except ImportError:  # allow direct run: python games/galaga.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, Particles, WIDTH, HEIGHT, clamp

STARS = [(random.randrange(WIDTH), random.randrange(HEIGHT), random.random())
         for _ in range(60)]
COLS, ROWS = 5, 4
BUG_COLORS = [(230, 70, 90), (120, 200, 255), (255, 190, 80), (160, 120, 255)]


class Bug:
    def __init__(self, col, row, x, y):
        self.col, self.row = col, row
        self.x, self.y = x, y
        self.start_x = x
        self.state = "enter"       # enter -> form -> dive
        self.t = 0.0
        self.vy = 0.0              # dive speed builds up, like the arcade swoop
        self.enter_slot = col + row * 0.3
        self.fire_t = random.uniform(0.5, 2.0)
        self.hp = 2 if row == 0 else 1
        self.dir = 1

    def update(self, dt, game):
        self.t += dt
        if self.state == "enter":
            self.enter_slot -= dt * 2.2
            self.x = self.start_x + math.sin(self.t * 4) * 40
            self.y += 60 * dt
            if self.enter_slot <= 0:
                self.state = "form"
        elif self.state == "form":
            self.x = self.start_x + math.sin(game.time * 1.5 + self.row) * 6
            self.y = 90 + self.row * 44
        elif self.state == "dive":
            # authentic swoop: the dive accelerates (gravity-like) while the
            # bug weaves side to side, then loops and climbs back to formation.
            self.vy += 640 * dt
            self.vy = min(self.vy, 330)
            self.x += math.sin(self.t * 3.0) * 150 * dt
            self.y += self.vy * dt
            self.fire_t -= dt
            if self.fire_t <= 0:
                self.fire_t = 1.6
                game.enemy_bullets.append([self.x, self.y,
                                           math.atan2(game.player[1] - self.y,
                                                      game.player[0] - self.x)])
            if self.y > HEIGHT + 40:
                self.state = "leaving"
        elif self.state == "leaving":
            self.t -= dt * 3
            self.vy = max(0.0, self.vy - 420 * dt)
            self.x = self.start_x + math.sin(self.t * 4) * 40
            self.y -= (60 + self.vy) * dt
            if self.t <= 0:
                self.y = -40
                self.vy = 0.0
                self.state = "enter"
                self.enter_slot = 2.0 + self.col * 0.1
        return self.hp <= 0


class Game(Game):
    name = "Galaga Strike"
    emoji = "🛸"
    tagline = "Break formation, dive, and blast the swarm."
    controls = "←→ move · Space shoot · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.time = 0.0
        self.level = 1
        self.score = 0
        self.lives = 3
        self.player = [WIDTH / 2, HEIGHT - 50]
        self.fire_t = 0.0
        self.pbullets = []
        self.enemy_bullets = []
        self.ufo = None
        self.ufo_t = 8.0
        self.dive_t = 6.0
        self.over = False
        self.banner = f"LEVEL {self.level}"
        self.banner_t = 2.0
        self.spawn_formation()

    def spawn_formation(self):
        self.bugs = []
        for row in range(ROWS):
            for col in range(COLS):
                x = WIDTH / 2 + (col - 2) * 74
                y = -60 - (row * 10 + col * 6)
                b = Bug(col, row, x, y)
                b.enter_slot = 1.0 + (row * 0.5 + col * 0.12) + self.level * 0.08
                self.bugs.append(b)

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            pass  # firing handled via held()

    def update(self, dt):
        self.particles.update(dt)
        if self.over:
            return
        self.time += dt
        self.banner_t = max(0.0, self.banner_t - dt)
        spd = 260
        if self.held(pygame.K_LEFT, pygame.K_a):
            self.player[0] -= spd * dt
        if self.held(pygame.K_RIGHT, pygame.K_d):
            self.player[0] += spd * dt
        self.player[0] = clamp(self.player[0], 20, WIDTH - 20)

        self.fire_t -= dt
        if self.held(pygame.K_SPACE) and self.fire_t <= 0:
            self.fire_t = 0.22
            self.pbullets.append([self.player[0], self.player[1] - 20])

        self.ufo_t -= dt
        if self.ufo_t <= 0:
            self.ufo_t = random.uniform(14, 22)
            self.ufo = [WIDTH + 30, 46, -1 if random.random() < 0.5 else 1]
        if self.ufo:
            self.ufo[0] += self.ufo[2] * 150 * dt
            if self.ufo[0] < -40 or self.ufo[0] > WIDTH + 40:
                self.ufo = None

        self.dive_t -= dt
        if self.dive_t <= 0:
            self.dive_t = max(3.0, 7.0 - self.level * 0.7)
            divers = [b for b in self.bugs if b.state == "form"]
            if divers:
                for b in random.sample(divers, min(2 + self.level // 2, len(divers))):
                    b.state = "dive"
                    b.t = 0.0
                    b.vy = 0.0

        for b in self.pbullets:
            b[1] -= 620 * dt
        self.pbullets = [b for b in self.pbullets if b[1] > -20]
        for b in self.enemy_bullets:
            b[0] += math.cos(b[2]) * 240 * dt
            b[1] += math.sin(b[2]) * 240 * dt
        self.enemy_bullets = [b for b in self.enemy_bullets if -30 < b[0] < WIDTH + 30]

        for b in self.bugs:
            if b.update(dt, self):
                self.bugs.remove(b)
                pts = 150 if b.row == 0 else 100
                self.score += pts * (1 + (self.level - 1) * 0.5)
                self.particles.burst(b.x, b.y, BUG_COLORS[b.row % 4], n=14)

        for b in self.pbullets:
            hit = None
            for e in self.bugs:
                if (b[0] - e.x) ** 2 + (b[1] - e.y) ** 2 < 24 ** 2:
                    e.hp -= 1
                    hit = e
                    break
            if self.ufo and (b[0] - self.ufo[0]) ** 2 + (b[1] - self.ufo[1]) ** 2 < 26 ** 2:
                self.score += 300
                self.particles.burst(self.ufo[0], self.ufo[1], (255, 255, 120), n=16)
                self.ufo = None
                hit = True
            if hit:
                if b in self.pbullets:
                    self.pbullets.remove(b)
        self.bugs = [b for b in self.bugs if b.hp > 0]

        for b in self.enemy_bullets:
            if (b[0] - self.player[0]) ** 2 + (b[1] - self.player[1]) ** 2 < 16 ** 2:
                self.enemy_bullets.remove(b)
                self.hit()
                break
        for e in self.bugs:
            if e.state == "dive" and (e.x - self.player[0]) ** 2 + (e.y - self.player[1]) ** 2 < 22 ** 2:
                self.hit()
                break

        if not self.bugs:
            self.level += 1
            self.score += 500
            self.banner = f"LEVEL {self.level}!"
            self.banner_t = 2.0
            self.spawn_formation()
        self.score += int(20 * dt)

    def hit(self):
        self.lives -= 1
        self.particles.burst(*self.player, (255, 140, 80), n=20)
        if self.lives <= 0:
            self.over = True
            self.show_menu("GAME OVER", ["Retry", "Main Menu"],
                           f"Score: {self.score} · Level {self.level}")

    def draw_bug(self, surf, b):
        col = BUG_COLORS[b.row % 4]
        x, y = int(b.x), int(b.y)
        if b.state == "dive":
            col = (255, 255, 255)
        pygame.draw.polygon(surf, col, [(x - 14, y), (x - 6, y - 12), (x + 6, y - 12),
                                        (x + 14, y), (x + 8, y + 10), (x - 8, y + 10)])
        pygame.draw.polygon(surf, col, [(x - 14, y), (x - 22, y + 8), (x - 12, y + 6)])
        pygame.draw.polygon(surf, col, [(x + 14, y), (x + 22, y + 8), (x + 12, y + 6)])
        pygame.draw.circle(surf, (20, 20, 40), (x - 4, y - 3), 3)
        pygame.draw.circle(surf, (20, 20, 40), (x + 4, y - 3), 3)

    def draw(self, surf):
        surf.fill((6, 8, 22))
        for sx, sy, sp in STARS:
            y = (sy + pygame.time.get_ticks() * 0.015 * sp) % HEIGHT
            pygame.draw.circle(surf, (110, 115, 150), (sx, int(y)), 1 if sp < 0.5 else 2)
        for b in self.bugs:
            self.draw_bug(surf, b)
        if self.ufo:
            draw_text(surf, "👽", 30, (255, 255, 255), (int(self.ufo[0]), int(self.ufo[1])),
                      align="center")
        px, py = int(self.player[0]), int(self.player[1])
        pygame.draw.polygon(surf, (90, 220, 120),
                            [(px, py - 18), (px - 14, py + 12), (px, py + 6), (px + 14, py + 12)])
        pygame.draw.circle(surf, (255, 255, 255), (px, py - 6), 3)
        for b in self.pbullets:
            pygame.draw.rect(surf, (255, 240, 140), (int(b[0]) - 2, int(b[1]) - 8, 4, 14))
        for b in self.enemy_bullets:
            pygame.draw.circle(surf, (255, 100, 100), (int(b[0]), int(b[1])), 4)
        self.particles.draw(surf)
        draw_text(surf, f"SCORE {self.score}", 22, (255, 255, 255), (14, 10))
        draw_text(surf, f"LEVEL {self.level}", 20, (255, 208, 74), (WIDTH - 14, 10),
                  align="topright")
        draw_text(surf, f"{'♥' * self.lives}", 20, (255, 120, 120), (14, 40))
        if self.banner and self.banner_t > 0:
            draw_text(surf, self.banner, 34, (255, 208, 74), (WIDTH // 2, HEIGHT // 2),
                      align="center", outline=2)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/galaga.py
    from games.engine import App
    App(Game).run()
