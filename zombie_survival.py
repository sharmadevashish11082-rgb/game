"""Zombie Outbreak — top-down wave survival shooter."""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         clamp, angle_to)
except ImportError:  # allow direct run: python games/zombie_survival.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              clamp, angle_to)

ARENA_W, ARENA_H = 1400, 1000


class Zombie:
    def __init__(self, x, y, hp, speed, dmg):
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.hp = hp
        self.max_hp = hp
        self.speed = speed
        self.dmg = dmg
        self.hit_t = 0.0
        self.wob = random.uniform(0, 6)

    def update(self, dt, px, py, others):
        """Real horde motion: zombies steer toward the target but carry
        momentum (they can't teleport or turn on a dime) and push apart so
        they shove through each other instead of stacking on one pixel."""
        self.hit_t = max(0.0, self.hit_t - dt)
        self.wob += dt * 6
        ang = angle_to(self.x, self.y, px, py)
        ax = math.cos(ang) * 300
        ay = math.sin(ang) * 300
        for o in others:                    # separation from nearby zombies
            dx, dy = self.x - o.x, self.y - o.y
            d2 = dx * dx + dy * dy
            if 0 < d2 < 38 * 38:
                d = d2 ** 0.5 or 1.0
                ax += dx / d * 110
                ay += dy / d * 110
        # damped approach: velocity eases toward the steering force
        self.vx += (ax - self.vx * 2.0) * dt
        self.vy += (ay - self.vy * 2.0) * dt
        spd = math.hypot(self.vx, self.vy)
        if spd > self.speed:                # top speed is a physical limit
            self.vx *= self.speed / spd
            self.vy *= self.speed / spd
        self.x += self.vx * dt
        self.y += self.vy * dt
        return math.hypot(px - self.x, py - self.y) < 34


class Game(Game):
    name = "Zombie Outbreak"
    emoji = "🧟"
    tagline = "Hold the line as the horde closes in."
    controls = "WASD move · Mouse aim · LMB shoot · R reload · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.p = [ARENA_W / 2, ARENA_H / 2]
        self.hp = 100
        self.stamina = 100
        self.stamina_regen_delay = 0.0
        self.ammo = 60
        self.max_ammo = 60
        self.reload_t = 0.0
        self.fire_t = 0.0
        self.speed_boost = 0.0
        self.wave = 1
        self.kills = 0
        self.score = 0
        self.zombies = []
        self.bullets = []
        self.to_spawn = 0
        self.spawn_t = 0.0
        self.inter_t = 0.0
        self.state = "inter"          # inter / fighting
        self.banner = "WAVE 1"
        self.banner_t = 2.0
        self.over = False
        self.blood = Particles()

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            self.reload_t = 1.1

    def start_wave(self):
        self.state = "fighting"
        self.to_spawn = 4 + self.wave * 3
        self.spawn_t = 0.0

    def update(self, dt):
        self.particles.update(dt)
        self.blood.update(dt)
        if self.over:
            return
        self.banner_t = max(0.0, self.banner_t - dt)
        if self.state == "inter":
            self.inter_t -= dt
            if self.inter_t <= 0:
                self.start_wave()
        else:
            self.spawn_t -= dt
            if self.to_spawn > 0 and self.spawn_t <= 0:
                self.spawn_t = max(0.15, 0.8 - self.wave * 0.05)
                self.to_spawn -= 1
                side = random.randrange(4)
                if side == 0:
                    x, y = random.uniform(30, ARENA_W - 30), 20
                elif side == 1:
                    x, y = random.uniform(30, ARENA_W - 30), ARENA_H - 20
                elif side == 2:
                    x, y = 20, random.uniform(30, ARENA_H - 30)
                else:
                    x, y = ARENA_W - 20, random.uniform(30, ARENA_H - 30)
                hp = 30 * (1 + self.wave * 0.35)
                spd = 42 + self.wave * 5 + random.uniform(-8, 8)
                self.zombies.append(Zombie(x, y, hp, spd, 5 + self.wave))

        self.speed_boost = max(0.0, self.speed_boost - dt)
        self.update_pickups(dt)
        # Stamina: sprinting burns energy, and a real person can't sprint
        # forever — when it runs out you're exhausted until it recovers.
        sprint = self.held(pygame.K_LSHIFT, pygame.K_RSHIFT) and self.stamina > 1
        if sprint:
            self.stamina = max(0.0, self.stamina - 22 * dt)
            self.stamina_regen_delay = 0.6
        else:
            if self.stamina_regen_delay > 0:
                self.stamina_regen_delay -= dt
            else:
                self.stamina = min(100.0, self.stamina + 13 * dt)
        spd = (240 if not sprint else 380) * (1.5 if self.speed_boost > 0 else 1.0)
        if self.held(pygame.K_w):
            self.p[1] -= spd * dt
        if self.held(pygame.K_s):
            self.p[1] += spd * dt
        if self.held(pygame.K_a):
            self.p[0] -= spd * dt
        if self.held(pygame.K_d):
            self.p[0] += spd * dt
        self.p[0] = clamp(self.p[0], 16, ARENA_W - 16)
        self.p[1] = clamp(self.p[1], 16, ARENA_H - 16)

        self.reload_t = max(0.0, self.reload_t - dt)
        if self.reload_t > 0 and self.ammo == 0 and self.state == "fighting":
            pass
        self.fire_t -= dt
        if pygame.mouse.get_pressed()[0] and self.fire_t <= 0 and self.state == "fighting":
            if self.ammo > 0:
                self.fire_t = 0.12
                self.ammo -= 1
                mx, my = pygame.mouse.get_pos()
                camx, camy = self.camera()
                ang = angle_to(self.p[0], self.p[1], mx + camx, my + camy)
                self.bullets.append([self.p[0], self.p[1], math.cos(ang) * 760,
                                     math.sin(ang) * 760, 0.5])
            else:
                self.reload_t = 1.1

        for b in self.bullets:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            b[4] -= dt
        self.bullets = [b for b in self.bullets if b[4] > 0]

        for z in list(self.zombies):
            z.update(dt, self.p[0], self.p[1], self.zombies)
            if z.hit_t <= 0 and math.hypot(self.p[0] - z.x, self.p[1] - z.y) < 34:
                z.hit_t = 0.8
                self.hp -= z.dmg
                self.blood.burst(self.p[0], self.p[1], (120, 10, 10), n=8, speed=120)
                if self.hp <= 0:
                    self.hp = 0
                    self.over = True
                    self.show_menu("YOU DIED", ["Retry", "Main Menu"],
                                   f"Wave {self.wave} · {self.kills} kills · {self.score} pts")

        for b in list(self.bullets):
            for z in list(self.zombies):
                if (b[0] - z.x) ** 2 + (b[1] - z.y) ** 2 < 26 ** 2:
                    z.hp -= 8
                    self.particles.burst(b[0], b[1], (255, 120, 60), n=4, speed=70)
                    self.blood.burst(z.x, z.y, (140, 20, 20), n=6, speed=90)
                    if b in self.bullets:
                        self.bullets.remove(b)
                    if z.hp <= 0:
                        self.zombies.remove(z)
                        self.kills += 1
                        self.score += 10 + self.wave * 2
                        self.particles.burst(z.x, z.y, (120, 200, 90), n=14)
                        if random.random() < 0.16:
                            self.drop_pickup(z.x, z.y)
                    break

        if self.state == "fighting" and self.to_spawn <= 0 and not self.zombies:
            self.state = "inter"
            self.inter_t = 5.0
            self.wave += 1
            self.banner = f"WAVE {self.wave}"
            self.banner_t = 2.0
            self.score += 100 + self.wave * 20

    def drop_pickup(self, x, y):
        kind = random.choice(["med", "ammo", "speed"])
        if not hasattr(self, "pickups"):
            self.pickups = []
        self.pickups.append(dict(kind=kind, x=x, y=y))

    def camera(self):
        return (clamp(self.p[0] - WIDTH / 2, 0, ARENA_W - WIDTH),
                clamp(self.p[1] - HEIGHT / 2, 0, ARENA_H - HEIGHT))

    def update_pickups(self, dt):
        if not hasattr(self, "pickups"):
            self.pickups = []
        for it in list(self.pickups):
            if math.hypot(it["x"] - self.p[0], it["y"] - self.p[1]) < 30:
                if it["kind"] == "med":
                    self.hp = min(100, self.hp + 40)
                elif it["kind"] == "ammo":
                    self.ammo = min(self.max_ammo, self.ammo + 30)
                else:
                    self.speed_boost = 5.0
                if it in self.pickups:
                    self.pickups.remove(it)
                self.particles.burst(it["x"], it["y"], (255, 220, 90), n=12)

    def draw(self, surf):
        camx, camy = self.camera()
        surf.fill((20, 22, 26))
        for gx in range(0, ARENA_W, 70):
            pygame.draw.line(surf, (26, 28, 34), (gx - camx, 0), (gx - camx, HEIGHT))
        for gy in range(0, ARENA_H, 70):
            pygame.draw.line(surf, (26, 28, 34), (0, gy - camy), (WIDTH, gy - camy))
        pygame.draw.rect(surf, (38, 24, 24), (int(-camx), int(-camy), ARENA_W, ARENA_H), 6)
        for z in self.zombies:
            x, y = int(z.x - camx), int(z.y - camy)
            col = (110, 170, 80)
            pygame.draw.circle(surf, col, (x, y), 13)
            pygame.draw.circle(surf, (70, 120, 50), (x, y + 6), 10)
            wob = math.sin(z.wob) * 3
            pygame.draw.line(surf, col, (x - 10, y - 6), (x - 16, y - 14 + wob), 4)
            pygame.draw.line(surf, col, (x + 10, y - 6), (x + 16, y - 14 + wob), 4)
            pygame.draw.circle(surf, (255, 60, 60), (x - 4, y - 4), 4)
            pygame.draw.circle(surf, (255, 60, 60), (x + 4, y - 4), 4)
            draw_health_bar(surf, x - 14, y - 24, 28, 4, z.hp / z.max_hp, fg=(140, 220, 90))
        for it in getattr(self, "pickups", []):
            x, y = int(it["x"] - camx), int(it["y"] - camy)
            col = {"med": (255, 90, 110), "ammo": (255, 200, 90), "speed": (120, 220, 255)}[it["kind"]]
            pygame.draw.circle(surf, col, (x, y), 8)
            pygame.draw.circle(surf, (255, 255, 255), (x, y), 3)
        px, py = int(self.p[0] - camx), int(self.p[1] - camy)
        pygame.draw.circle(surf, (90, 160, 255), (px, py), 13)
        pygame.draw.circle(surf, (210, 230, 255), (px - 4, py - 3), 3)
        pygame.draw.circle(surf, (210, 230, 255), (px + 4, py - 3), 3)
        mx, my = pygame.mouse.get_pos()
        ang = angle_to(px, py, mx, my)
        pygame.draw.line(surf, (40, 50, 80), (px + math.cos(ang) * 10, py + math.sin(ang) * 10),
                         (px + math.cos(ang) * 34, py + math.sin(ang) * 34), 5)
        for b in self.bullets:
            pygame.draw.circle(surf, (255, 230, 120), (int(b[0] - camx), int(b[1] - camy)), 4)
        self.particles.draw(surf)
        self.blood.draw(surf)
        pygame.draw.circle(surf, (255, 80, 80), (mx, my), 6, 2)
        pygame.draw.circle(surf, (255, 80, 80), (mx, my), 1)

        draw_health_bar(surf, 14, 12, 220, 18, self.hp / 100, fg=(255, 90, 110))
        draw_text(surf, f"{self.hp}", 15, (255, 255, 255), (18, 33))
        draw_health_bar(surf, 14, 34, 220, 10, self.stamina / 100, fg=(120, 220, 255))
        draw_text(surf, f"AMMO {self.ammo}/{self.max_ammo}", 18, (255, 208, 74),
                  (14, 52), bold=True)
        if self.held(pygame.K_LSHIFT, pygame.K_RSHIFT):
            draw_text(surf, "SPRINT (Shift)", 13, (150, 230, 255), (18, 68))
        if self.reload_t > 0:
            draw_text(surf, "RELOADING...", 16, (255, 150, 90), (14, 76))
        draw_text(surf, f"WAVE {self.wave}", 22, (255, 255, 255), (WIDTH - 14, 12),
                  align="topright")
        draw_text(surf, f"KILLS {self.kills}   SCORE {self.score}", 16, (200, 204, 224),
                  (WIDTH - 14, 40), align="topright")
        if self.banner and self.banner_t > 0:
            draw_text(surf, self.banner, 40, (255, 90, 90), (WIDTH // 2, HEIGHT // 2),
                      align="center", outline=3)
        if self.state == "inter" and self.banner_t <= 0:
            draw_text(surf, f"Next wave in {max(0, int(self.inter_t) + 1)}...", 22,
                      (200, 204, 224), (WIDTH // 2, HEIGHT // 2), align="center")
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/zombie_survival.py
    from games.engine import App
    App(Game).run()
