"""Street Fury — a 1v1 2D fighting game with a blocking AI."""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         clamp)
except ImportError:  # allow direct run: python games/fighting.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              clamp)

GROUND_Y = HEIGHT - 80
MOVE_DEFS = {
    "punch": dict(dmg=7, range=48, cd=0.34, wind=0.07, active=0.12, kb=60, color=(255, 220, 120)),
    "kick":  dict(dmg=12, range=66, cd=0.62, wind=0.12, active=0.14, kb=140, color=(255, 140, 120)),
}


class Fighter:
    def __init__(self, x, color, name, ai=False):
        self.x, self.y = float(x), float(GROUND_Y)
        self.vx, self.vy = 0.0, 0.0
        self.facing = 1 if x < WIDTH / 2 else -1
        self.hp = 100
        self.max_hp = 100
        self.color = color
        self.name = name
        self.ai = ai
        self.hitstun = 0.0
        self.attack = None     # dict with t since start
        self.blocking = False
        self.cd = 0.0
        self.on_ground = True
        self.flash = 0.0

    def start_attack(self, kind):
        if self.cd > 0 or self.hitstun > 0:
            return False
        self.attack = dict(kind=kind, t=0.0)
        self.cd = MOVE_DEFS[kind]["cd"]
        return True

    def update(self, dt, other):
        self.flash = max(0.0, self.flash - dt)
        if self.hitstun > 0:
            self.hitstun -= dt
        else:
            self.vx *= (1 - 6 * dt)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 1500 * dt
        if self.y >= GROUND_Y:
            self.y = GROUND_Y
            self.vy = 0.0
            self.on_ground = True
        self.x = clamp(self.x, 50, WIDTH - 50)
        if self.attack:
            self.attack["t"] += dt
            spec = MOVE_DEFS[self.attack["kind"]]
            if self.attack["t"] >= spec["wind"] + spec["active"]:
                self.attack = None
        self.cd = max(0.0, self.cd - dt)
        # resolve hit
        if self.attack and spec_active(self):
            spec = MOVE_DEFS[self.attack["kind"]]
            fx = self.x + self.facing * spec["range"] / 2
            if (other.x - fx) * self.facing >= 0 and abs(other.x - self.x) < spec["range"]:
                if abs(other.y - self.y) < 70 and other.hitstun <= 0 and not other.dead():
                    other.hitstun = 0.32
                    dmg = spec["dmg"] if not other.blocking else max(1, spec["dmg"] // 5)
                    other.hp -= dmg
                    other.vx = self.facing * spec["kb"]
                    if self.attack["kind"] == "kick":
                        other.vy = min(other.vy, -80)   # kicks lift the target
                    other.flash = 0.1
                    self.vx -= self.facing * spec["kb"] * 0.18   # recoil
                    self.attack["t"] = 99  # only hits once
                    return (fx, other.y, spec["color"], dmg)
        return None

    def dead(self):
        return self.hp <= 0


def spec_active(f):
    if not f.attack:
        return False
    spec = MOVE_DEFS[f.attack["kind"]]
    return spec["wind"] <= f.attack["t"] < spec["wind"] + spec["active"]


class Game(Game):
    name = "Street Fury"
    emoji = "🥷"
    tagline = "Punch, kick, block — beat the challenger."
    controls = "P1: A/D move · W jump · J punch · K kick · L block · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.p1 = Fighter(260, (90, 150, 255), "P1", ai=False)
        self.p2 = Fighter(700, (255, 90, 90), "CPU", ai=True)
        self.time = 90.0
        self.hits = []
        self.over = False
        self.winner = ""
        self.round_go_t = 1.0

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_j:
                self.p1.start_attack("punch")
            elif event.key == pygame.K_k:
                self.p1.start_attack("kick")

    def update(self, dt):
        self.particles.update(dt)
        if self.over:
            return
        self.round_go_t = max(0.0, self.round_go_t - dt)
        if self.round_go_t > 0:
            return
        self.time -= dt
        p1, p2 = self.p1, self.p2

        # P1 controls
        p1.blocking = self.held(pygame.K_l)
        if self.held(pygame.K_a):
            p1.vx += -420 * dt
            p1.facing = -1
        if self.held(pygame.K_d):
            p1.vx += 420 * dt
            p1.facing = 1
        if self.held(pygame.K_w) and p1.on_ground:
            p1.vy = -560
            p1.on_ground = False

        # CPU AI
        p2.blocking = False
        dist = abs(p2.x - p1.x)
        if p2.hitstun <= 0:
            if dist > 90:
                p2.vx += (380 if p1.x > p2.x else -380) * dt
                p2.facing = 1 if p1.x > p2.x else -1
            elif random.random() < dt * 1.2:
                p2.start_attack("punch" if random.random() < 0.65 else "kick")
            elif random.random() < dt * 1.0:
                p2.blocking = True
            elif random.random() < dt * 0.3 and p2.on_ground:
                p2.vy = -520
                p2.on_ground = False

        h1 = p1.update(dt, p2)
        h2 = p2.update(dt, p1)
        for hit in (h1, h2):
            if hit:
                x, y, color, dmg = hit
                self.hits.append([x, y, color, 0.25])
                self.particles.burst(x, y, color, n=10, speed=130)

        if p1.dead() or p2.dead() or self.time <= 0:
            self.over = True
            if p1.dead() or (self.time <= 0 and p2.hp >= p1.hp):
                self.winner = "CPU"
            else:
                self.winner = "P1"
            self.show_menu(f"{self.winner} WINS!", ["Rematch", "Main Menu"],
                           f"{p1.hp:.0f} vs {p2.hp:.0f} HP")

    def draw_fighter(self, surf, f):
        x, y = int(f.x), int(f.y)
        col = (255, 255, 255) if f.flash > 0 else f.color
        if f.blocking and f.hitstun <= 0:
            pygame.draw.circle(surf, (140, 220, 255), (x, y - 46), 26, 3)
        # legs
        pygame.draw.line(surf, (40, 44, 60), (x, y), (x - 10 * f.facing, y - 24), 6)
        pygame.draw.line(surf, (40, 44, 60), (x, y), (x + 10 * f.facing, y - 24), 6)
        # body
        pygame.draw.rect(surf, col, (x - 16, y - 58, 32, 40), border_radius=8)
        # head
        pygame.draw.circle(surf, (235, 210, 180), (x, y - 70), 13)
        pygame.draw.circle(surf, (30, 30, 40), (x + 5 * f.facing, y - 73), 3)
        # arms
        if f.attack and spec_active(f):
            kind = f.attack["kind"]
            reach = MOVE_DEFS[kind]["range"]
            pygame.draw.line(surf, MOVE_DEFS[kind]["color"], (x + 12 * f.facing, y - 44),
                             (x + f.facing * reach, y - 46), 8)
            pygame.draw.circle(surf, MOVE_DEFS[kind]["color"],
                               (x + f.facing * reach, y - 46), 6)
        else:
            pygame.draw.line(surf, col, (x + 12 * f.facing, y - 48),
                             (x + 20 * f.facing, y - 30), 7)

    def draw(self, surf):
        surf.fill((44, 30, 66))
        for i in range(8):
            shade = 60 - i * 4
            pygame.draw.rect(surf, (shade, 34 + i * 2, 78 - i * 2), (0, i * 80, WIDTH, 80))
        pygame.draw.rect(surf, (70, 64, 58), (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        pygame.draw.rect(surf, (90, 84, 76), (0, GROUND_Y, WIDTH, 8))
        draw_text(surf, "ROUND", 16, (150, 158, 190), (WIDTH // 2, 12), align="center")
        self.draw_fighter(surf, self.p1)
        self.draw_fighter(surf, self.p2)
        for h in self.hits:
            h[3] -= 1 / 60
            if h[3] > 0:
                pygame.draw.circle(surf, h[2], (int(h[0]), int(h[1])), int(12 * h[3] * 4), 2)
        self.hits = [h for h in self.hits if h[3] > 0]
        self.particles.draw(surf)

        draw_text(surf, "P1", 20, (160, 200, 255), (20, 40), bold=True)
        draw_health_bar(surf, 70, 40, 360, 22, self.p1.hp / self.p1.max_hp, fg=(90, 160, 255))
        draw_text(surf, "CPU", 20, (255, 160, 160), (WIDTH - 20, 40), align="topright", bold=True)
        draw_health_bar(surf, WIDTH - 430, 40, 360, 22, self.p2.hp / self.p2.max_hp, fg=(255, 110, 110))
        draw_text(surf, f"{max(0, int(self.time))}", 30, (255, 255, 255), (WIDTH // 2, 40),
                  align="center", bold=True)
        if self.round_go_t > 0:
            draw_text(surf, "FIGHT!", 60, (255, 208, 74), (WIDTH // 2, HEIGHT // 2),
                      align="center", outline=3)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/fighting.py
    from games.engine import App
    App(Game).run()
