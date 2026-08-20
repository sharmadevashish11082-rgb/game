"""Bullet Hell — dodge dense fire patterns and survive the boss."""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         clamp, angle_to)
except ImportError:  # allow direct run: python games/bullet_hell.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              clamp, angle_to)

STARS = [(random.randrange(WIDTH), random.randrange(HEIGHT), random.random())
         for _ in range(70)]


class Bullet:
    def __init__(self, x, y, vx, vy, r=4, color=(255, 90, 90)):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r = r
        self.color = color

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        return -30 < self.x < WIDTH + 30 and -30 < self.y < HEIGHT + 30


class Enemy:
    def __init__(self, x, y, pattern, game):
        self.x, self.y = x, y
        self.pattern = pattern
        self.hp = 3
        self.t = 0.0
        self.fire_t = 0.0
        self.ang = random.random() * 6.28
        self.base_y = random.uniform(70, 190)
        self.game = game

    def update(self, dt, player):
        self.t += dt
        self.fire_t -= dt
        if self.y < self.base_y:
            self.y += 90 * dt
        else:
            self.x += math.sin(self.t * 2.2) * 40 * dt
        if self.fire_t <= 0:
            self.fire(self.player_angle(player))
            self.fire_t = self.rate()
        return self.hp <= 0

    def player_angle(self, player):
        return angle_to(self.x, self.y, player[0], player[1])

    def rate(self):
        return {0: 1.1, 1: 0.28, 2: 1.4, 3: 2.0}[self.pattern]

    def fire(self, ang):
        b = self.game.bullets
        if self.pattern == 0:      # aimed triple
            for k in (-1, 0, 1):
                b.append(Bullet(self.x, self.y, math.cos(ang + k * 0.22) * 230,
                                math.sin(ang + k * 0.22) * 230, 5, (255, 120, 90)))
        elif self.pattern == 1:    # spiral
            self.ang += 0.55
            b.append(Bullet(self.x, self.y, math.cos(self.ang) * 190,
                            math.sin(self.ang) * 190, 4, (120, 255, 200)))
        elif self.pattern == 2:    # aimed
            b.append(Bullet(self.x, self.y, math.cos(ang) * 260,
                            math.sin(ang) * 260, 5, (255, 160, 90)))
        else:                      # ring
            for k in range(8):
                a = k * math.pi / 4 + self.t * 0.3
                b.append(Bullet(self.x, self.y, math.cos(a) * 150,
                                math.sin(a) * 150, 4, (150, 160, 255)))


    def color_hint(self):
        return [(255, 120, 90), (120, 255, 200), (255, 160, 90), (150, 160, 255)][self.pattern]


class Boss:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = 90
        self.max_hp = 90
        self.t = 0.0
        self.fire_t = 1.2

    def update(self, dt, player, bullets):
        self.t += dt
        self.x = WIDTH / 2 + math.sin(self.t * 0.5) * 260
        self.fire_t -= dt
        if self.fire_t <= 0:
            ang = angle_to(self.x, self.y, player[0], player[1])
            if int(self.t * 2) % 2 == 0:      # spiral
                for k in range(6):
                    a = ang + k * 1.05
                    bullets.append(Bullet(self.x, self.y, math.cos(a) * 200,
                                          math.sin(a) * 200, 5, (255, 120, 220)))
            else:                              # ring
                for k in range(10):
                    a = k * math.pi / 5 + self.t
                    bullets.append(Bullet(self.x, self.y, math.cos(a) * 140,
                                          math.sin(a) * 140, 4, (255, 200, 90)))
            self.fire_t = 1.0
        return self.hp <= 0


class Game(Game):
    name = "Bullet Hell"
    emoji = "🚀"
    tagline = "Thread the needle through endless fire."
    controls = "Arrows move · Shift slow · Space shoot · X bomb · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.player = [WIDTH / 2, HEIGHT - 60]
        self.pvx, self.pvy = 0.0, 0.0     # the ship carries real momentum
        self.lives = 3
        self.bombs = 3
        self.score = 0
        self.kills = 0
        self.inv = 0.0
        self.fire_t = 0.0
        self.spawn_t = 1.4
        self.enemies = []
        self.bullets = []
        self.pbullets = []
        self.boss = None
        self.over = False
        self.banner = ""
        self.banner_t = 0.0

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_x and self.bombs > 0:
            self.bombs -= 1
            self.bullets.clear()
            for e in self.enemies:
                e.hp -= 6
            if self.boss:
                self.boss.hp -= 6

    def update(self, dt):
        self.particles.update(dt)
        if self.over:
            return
        self.banner_t = max(0.0, self.banner_t - dt)
        self.inv = max(0.0, self.inv - dt)
        p = self.player
        slow = self.held(pygame.K_LSHIFT, pygame.K_RSHIFT)
        spd = 130 if slow else 280
        # Real flight: the ship eases toward the commanded velocity instead
        # of teleporting, so changes of direction carry momentum.
        tx = (self.held(pygame.K_RIGHT, pygame.K_d) -
              self.held(pygame.K_LEFT, pygame.K_a)) * spd
        ty = (self.held(pygame.K_DOWN, pygame.K_s) -
              self.held(pygame.K_UP, pygame.K_w)) * spd
        k = min(1.0, 16.0 * dt)
        self.pvx += (tx - self.pvx) * k
        self.pvy += (ty - self.pvy) * k
        p[0] += self.pvx * dt
        p[1] += self.pvy * dt
        p[0] = clamp(p[0], 14, WIDTH - 14)
        p[1] = clamp(p[1], 14, HEIGHT - 14)

        self.fire_t -= dt
        if self.held(pygame.K_SPACE) and self.fire_t <= 0:
            self.fire_t = 0.16
            self.pbullets.append([p[0], p[1] - 16, 0.0])
            self.pbullets.append([p[0] - 10, p[1] - 8, -0.08])
            self.pbullets.append([p[0] + 10, p[1] - 8, 0.08])

        for b in self.pbullets:
            b[1] -= 640 * dt
            b[0] += b[2] * 200 * dt
        self.pbullets = [b for b in self.pbullets if b[1] > -20]

        if self.boss is None and self.kills >= 15 and not self.enemies:
            self.boss = Boss(WIDTH / 2, 90)
            self.banner = "⚠ BOSS INCOMING ⚠"
            self.banner_t = 2.0
        elif self.boss is None:
            self.spawn_t -= dt
            if self.spawn_t <= 0:
                self.spawn_t = max(0.55, 1.4 - self.kills * 0.03)
                pattern = random.randrange(4)
                self.enemies.append(Enemy(random.uniform(60, WIDTH - 60), -30,
                                          pattern, self))
        for e in self.enemies:
            if e.update(dt, p):
                self.enemies.remove(e)
                self.kills += 1
                self.score += 100
                self.particles.burst(e.x, e.y, e.color_hint(), n=18)
        if self.boss:
            if self.boss.update(dt, p, self.bullets):
                self.boss = None
                self.score += 1000
                self.particles.burst(self.boss.x, self.boss.y, (255, 220, 90), n=40)
                self.banner = "BOSS DESTROYED!"
                self.banner_t = 2.0

        for b in self.bullets:
            if not b.update(dt):
                self.bullets.remove(b)
                continue
            if (b.x - p[0]) ** 2 + (b.y - p[1]) ** 2 < (b.r + 4) ** 2 and self.inv <= 0:
                self.bullets.remove(b)
                self.hit()
        self.bullets = [b for b in self.bullets
                        if (b.x - p[0]) ** 2 + (b.y - p[1]) ** 2 > (b.r + 4) ** 2 or self.inv > 0]

        for b in self.pbullets:
            for e in list(self.enemies):
                if (b[0] - e.x) ** 2 + (b[1] - e.y) ** 2 < 22 ** 2:
                    e.hp -= 1
                    if b in self.pbullets:
                        self.pbullets.remove(b)
                    break
            if self.boss and (b[0] - self.boss.x) ** 2 + (b[1] - self.boss.y) ** 2 < 40 ** 2:
                self.boss.hp -= 1
                if b in self.pbullets:
                    self.pbullets.remove(b)
        self.enemies = [e for e in self.enemies if e.hp > 0]
        self.score += int(60 * dt)

    def hit(self):
        self.lives -= 1
        self.inv = 1.6
        self.bullets.clear()
        self.particles.burst(*self.player, (255, 255, 255), n=22)
        if self.lives <= 0:
            self.over = True
            self.show_menu("GAME OVER", ["Retry", "Main Menu"],
                           f"Score: {self.score} · {self.kills} kills")

    def draw(self, surf):
        surf.fill((8, 8, 18))
        for sx, sy, sp in STARS:
            y = (sy + pygame.time.get_ticks() * 0.02 * sp) % HEIGHT
            pygame.draw.circle(surf, (120, 120, 150), (sx, int(y)), 1 if sp < 0.5 else 2)
        for b in self.bullets:
            pygame.draw.circle(surf, b.color, (int(b.x), int(b.y)), b.r)
            pygame.draw.circle(surf, (255, 255, 255), (int(b.x), int(b.y)), max(1, b.r // 2))
        for e in self.enemies:
            pygame.draw.polygon(surf, e.color_hint(),
                                [(e.x, e.y - 14), (e.x - 12, e.y + 10), (e.x + 12, e.y + 10)])
            pygame.draw.circle(surf, (20, 20, 40), (int(e.x), int(e.y - 2)), 4)
        if self.boss:
            bx, by = int(self.boss.x), int(self.boss.y)
            pygame.draw.polygon(surf, (200, 90, 220),
                                [(bx, by - 34), (bx - 30, by + 20), (bx + 30, by + 20)])
            pygame.draw.circle(surf, (255, 255, 255), (bx - 12, by - 6), 6)
            pygame.draw.circle(surf, (255, 255, 255), (bx + 12, by - 6), 6)
            draw_health_bar(surf, bx - 50, by - 46, 100, 8, self.boss.hp / self.boss.max_hp,
                            fg=(255, 120, 200))
        px, py = int(self.player[0]), int(self.player[1])
        if self.inv <= 0 or int(self.inv * 10) % 2 == 0:
            pygame.draw.polygon(surf, (110, 220, 255),
                                [(px, py - 16), (px - 12, py + 12), (px + 12, py + 12)])
            pygame.draw.circle(surf, (230, 250, 255), (px, py), 4)
            pygame.draw.polygon(surf, (255, 180, 60),
                                [(px - 4, py + 12), (px + 4, py + 12), (px, py + 20)])
        for b in self.pbullets:
            pygame.draw.circle(surf, (255, 240, 160), (int(b[0]), int(b[1])), 4)
        self.particles.draw(surf)
        draw_text(surf, f"SCORE {self.score}", 22, (255, 255, 255), (14, 10))
        draw_text(surf, f"KILLS {self.kills}", 18, (170, 176, 205), (14, 40))
        draw_text(surf, f"LIVES {'♥' * max(0, self.lives)}", 20, (255, 120, 120), (14, 66))
        draw_text(surf, f"BOMBS {'●' * self.bombs}{'○' * (3 - self.bombs)}  [X]", 16,
                  (255, 208, 74), (WIDTH - 14, 10), align="topright")
        if self.banner and self.banner_t > 0:
            draw_text(surf, self.banner, 30, (255, 120, 120), (WIDTH // 2, HEIGHT // 2),
                      align="center", outline=2)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/bullet_hell.py
    from games.engine import App
    App(Game).run()
