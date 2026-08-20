"""Wilderness — survive five days: gather, drink, stay warm, hold off the wolves.

The simulation uses real-world vitals instead of abstract bars:

  kcal   — you burn roughly 2 200 kcal a day; starving hurts.
  water  — you need ~2.5 L a day; dehydration kills faster than hunger.
  body   — core temperature in °C; below ~35 °C is hypothermia, below 33 °C
           it becomes life-threatening fast. Fires and torches warm you.
  air    — the mountain air follows a real diurnal curve (warm day, cold
           night); the clock runs 24 real hours per day-night cycle.
"""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         clamp)
except ImportError:  # allow direct run: python games/survival.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              clamp)

GRID_W, GRID_H = 40, 26
TILE = 24
DAY_LEN, NIGHT_LEN = 22.0, 12.0
CYCLE = DAY_LEN + NIGHT_LEN      # one full game-day (≈ 24 hours of game time)
HOURS_PER_CYCLE = 24.0
START_HOUR = 6.0                 # day one starts at 06:00
DAYS_TO_WIN = 5

# Real human physiology, compressed to the game's timescale.
KCAL_NEEDED = 2200.0             # daily burn
KCAL_DECAY = KCAL_NEEDED / CYCLE
WATER_NEEDED = 1.8               # litres per day (light activity)
WATER_DECAY = WATER_NEEDED / CYCLE
STARVATION_LIMIT = 500.0         # below this, hunger starts hurting
DEHYDRATION_LIMIT = 0.25         # below this, thirst is life-threatening
HYPOTHERMIA_CRITICAL = 33.0      # °C — below this you're in real danger


class Wolf:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.hp = 25
        self.hit_t = 0.0
        self.wob = random.uniform(0, 6)

    def update(self, dt, px, py):
        self.hit_t = max(0.0, self.hit_t - dt)
        self.wob += dt * 7
        ang = math.atan2(py - self.y, px - self.x)
        self.x += math.cos(ang) * 64 * dt
        self.y += math.sin(ang) * 64 * dt
        return math.hypot(px - self.x, py - self.y) < 22


class Game(Game):
    name = "Wilderness"
    emoji = "🏝️"
    tagline = "Gather, drink, stay warm, and survive the night."
    controls = "WASD move · E gather · C craft · F eat · G drink · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        rng = random.Random(99)
        self.grid = [["g" for _ in range(GRID_W)] for _ in range(GRID_H)]
        for y in range(GRID_H):
            for x in range(GRID_W):
                r = rng.random()
                if r < 0.06:
                    self.grid[y][x] = "w"
                elif r < 0.14:
                    self.grid[y][x] = "t"
                elif r < 0.19:
                    self.grid[y][x] = "r"
                elif r < 0.23:
                    self.grid[y][x] = "b"
        self.px, self.py = GRID_W / 2 * TILE, GRID_H / 2 * TILE
        self.hp = 100
        self.kcal = 2600.0                 # start well-fed (kcal)
        self.water = 2.0                   # litres of body hydration
        self.canteen = 1.0                 # litres you carry
        self.body = 36.6                   # core temperature, °C
        self.wood = 3
        self.stone = 0
        self.berries = 2
        self.t = 0.0
        self.day = 1
        self.wolves = []
        self.fires = []
        self.torches = []
        self.walls = []
        self.wolf_t = 4.0
        self.over = False
        self.won = False
        self.msg = "Gather wood and stone, then build a campfire."
        self.msg_t = 4.0
        self.gather_cd = 0.0

    # -- helpers -------------------------------------------------------------

    def is_night(self):
        return self.t % CYCLE >= DAY_LEN

    def clock(self):
        """Hours since midnight, e.g. 14.5 → 14:30."""
        return (START_HOUR + (self.t % CYCLE) / CYCLE * HOURS_PER_CYCLE) % 24.0

    def air_temp(self):
        """Diurnal air temperature (°C): warm midday, cold pre-dawn night."""
        f = (self.t % CYCLE) / CYCLE
        if f < DAY_LEN / CYCLE:                      # day: bell curve, 14→22→14
            d = f * CYCLE / DAY_LEN
            return 14.0 + 8.0 * math.sin(math.pi * d)
        n = (f - DAY_LEN / CYCLE) * CYCLE / NIGHT_LEN   # night: 10 → 6
        return 10.0 - 4.0 * n

    def cell(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if not (0 <= tx < GRID_W and 0 <= ty < GRID_H):
            return None
        return tx, ty

    def near(self, kind, radius=26):
        for y in range(GRID_H):
            for x in range(GRID_W):
                if self.grid[y][x] == kind:
                    cx, cy = x * TILE + TILE / 2, y * TILE + TILE / 2
                    if math.hypot(cx - self.px, cy - self.py) < radius:
                        return x, y
        return None

    # -- input ---------------------------------------------------------------

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
            if event.key == pygame.K_e:
                self.gather()
            elif event.key == pygame.K_c:
                self.show_menu("CRAFT", ["Campfire (5 wood)", "Wall (10 wood)",
                                         "Torch (2 wood)", "Close"])
            elif event.key == pygame.K_f and self.berries > 0:
                self.berries -= 1
                self.kcal = min(3000.0, self.kcal + 350.0)
                self.water = min(3.0, self.water + 0.12)
                self.msg = "You eat berries. +350 kcal"
                self.msg_t = 2.0
            elif event.key == pygame.K_g and self.canteen >= 0.25:
                self.canteen -= 0.25
                self.water = min(3.0, self.water + 0.35)
                self.msg = "You drink from your canteen. +0.35 L"
                self.msg_t = 2.0
            else:
                choice = self.menu_choice(event)
                if choice == 0:
                    self.craft("fire")
                elif choice == 1:
                    self.craft("wall")
                elif choice == 2:
                    self.craft("torch")

    def craft(self, kind):
        if kind == "fire" and self.wood >= 5:
            self.wood -= 5
            cx, cy = self.cell(self.px, self.py)
            self.fires.append(dict(x=cx * TILE + TILE / 2, y=cy * TILE + TILE / 2,
                                   fuel=60.0))
            self.msg = "Campfire built! Stay near it at night."
        elif kind == "wall" and self.wood >= 10:
            self.wood -= 10
            tx, ty = self.cell(self.px, self.py)
            if self.facing == "up":
                ty -= 1
            elif self.facing == "down":
                ty += 1
            elif self.facing == "left":
                tx -= 1
            else:
                tx += 1
            if 0 <= tx < GRID_W and 0 <= ty < GRID_H and (tx, ty) not in self.walls:
                self.walls.append((tx, ty))
                self.msg = "Wall built — wolves can't pass."
        elif kind == "torch" and self.wood >= 2:
            self.wood -= 2
            cx, cy = self.cell(self.px, self.py)
            self.torches.append(dict(x=cx * TILE + TILE / 2, y=cy * TILE + TILE / 2,
                                     fuel=40.0))
            self.msg = "Torch lit — a small circle of warmth."
        self.msg_t = 2.5

    def gather(self):
        self.gather_cd = 0.4
        w = self.near("w")
        if w and self.canteen < 2.0:
            self.canteen = min(2.0, self.canteen + 0.6)
            self.msg = "You fill your canteen at the stream. +0.6 L"
            self.msg_t = 2.0
            return
        t = self.near("t")
        if t:
            self.wood += 2
            self.msg = "+2 wood"
            self.msg_t = 2.0
            return
        r = self.near("r")
        if r:
            self.stone += 2
            self.msg = "+2 stone"
            self.msg_t = 2.0
            return
        b = self.near("b")
        if b:
            self.berries += 2
            self.msg = "+2 berries"
            self.msg_t = 2.0
            return
        self.msg = "Nothing to gather here."
        self.msg_t = 2.0

    # -- simulation ----------------------------------------------------------

    def update(self, dt):
        self.particles.update(dt)
        if self.over:
            return
        self.msg_t = max(0.0, self.msg_t - dt)
        self.gather_cd = max(0.0, self.gather_cd - dt)
        self.t += dt
        if self.t // CYCLE >= self.day:
            self.day += 1
            if self.day > DAYS_TO_WIN:
                self.over = True
                self.won = True
                self.show_menu("SURVIVED!", ["Play Again", "Main Menu"],
                               f"You lasted {self.day - 1} days and nights",
                               title_color=(120, 255, 150))
                return
            self.msg = f"Day {self.day} — keep going!"
            self.msg_t = 3.0
        night = self.is_night()
        spd = 150 * dt
        dx = dy = 0
        if self.held(pygame.K_w):
            dy -= 1
            self.facing = "up"
        if self.held(pygame.K_s):
            dy += 1
            self.facing = "down"
        if self.held(pygame.K_a):
            dx -= 1
            self.facing = "left"
        if self.held(pygame.K_d):
            dx += 1
            self.facing = "right"
        self.px = clamp(self.px + dx * spd, 12, GRID_W * TILE - 12)
        self.py = clamp(self.py + dy * spd, 12, GRID_H * TILE - 12)
        cell = self.cell(self.px, self.py)
        if cell and self.grid[cell[1]][cell[0]] == "w":
            self.px -= dx * spd
            self.py -= dy * spd

        # --- real vitals -------------------------------------------------
        temp = self.air_temp()
        near_fire = False
        for f in list(self.fires):
            f["fuel"] -= dt
            if f["fuel"] <= 0:
                self.fires.remove(f)
            elif math.hypot(f["x"] - self.px, f["y"] - self.py) < 70:
                near_fire = True
                if random.random() < dt * 30:
                    self.particles.burst(f["x"], f["y"] - 8, (255, 180, 60), n=1,
                                         speed=30, up=True)
        for t in list(self.torches):
            t["fuel"] -= dt
            if t["fuel"] <= 0:
                self.torches.remove(t)
            elif math.hypot(t["x"] - self.px, t["y"] - self.py) < 42:
                near_fire = True

        # Body temperature: below ~15 °C air you lose heat to the world;
        # flames push you back toward a healthy 37 °C.
        if near_fire:
            if self.body < 37.0:
                self.body = min(37.0, self.body + 0.9 * dt)
            elif temp > 24.0 and self.body < 38.5:   # too much fire in the sun
                self.body += 0.4 * dt
        elif temp < 15.0:
            self.body -= (15.0 - temp) * 0.05 * dt
        else:
            self.body = min(37.0, self.body + 0.15 * dt)

        self.kcal = max(0.0, self.kcal - KCAL_DECAY * dt)
        self.water = max(0.0, self.water - WATER_DECAY * dt)

        if self.body < 33.0:
            self.hp -= 6.0 * dt                       # severe hypothermia
        elif self.body < 35.0:
            self.hp -= 1.5 * dt                       # mild hypothermia
        elif self.body > 39.5:
            self.hp -= 4.0 * dt                       # fever
        if self.kcal < STARVATION_LIMIT:
            self.hp -= 1.5 * dt
        if self.water < DEHYDRATION_LIMIT:
            self.hp -= 2.0 * dt
        if self.kcal > 1500 and self.water > 1.0 and 36.0 < self.body < 37.4:
            self.hp = min(100.0, self.hp + 3.0 * dt)  # well-fed recovery
        if self.hp <= 0:
            self.hp = 0
            self.over = True
            self.show_menu("YOU DIED", ["Retry", "Main Menu"],
                           f"Survived {self.day} day(s)")
            return

        # --- wolves ------------------------------------------------------
        if night:
            self.wolf_t -= dt
            if self.wolf_t <= 0 and len(self.wolves) < 5:
                self.wolf_t = random.uniform(2.5, 4.5)
                side = random.randrange(4)
                if side == 0:
                    x, y = random.uniform(10, GRID_W * TILE - 10), 6
                elif side == 1:
                    x, y = random.uniform(10, GRID_W * TILE - 10), GRID_H * TILE - 6
                elif side == 2:
                    x, y = 6, random.uniform(10, GRID_H * TILE - 10)
                else:
                    x, y = GRID_W * TILE - 6, random.uniform(10, GRID_H * TILE - 10)
                self.wolves.append(Wolf(x, y))
            for w in self.wolves:
                w.update(dt, self.px, self.py)
                for wx, wy in self.walls:
                    if abs(w.x - (wx * TILE + TILE / 2)) < TILE and \
                            abs(w.y - (wy * TILE + TILE / 2)) < TILE:
                        w.x -= math.cos(math.atan2(self.py - w.y, self.px - w.x)) * 20 * dt
                        w.y -= math.sin(math.atan2(self.py - w.y, self.px - w.x)) * 20 * dt
                if w.hit_t <= 0 and math.hypot(w.x - self.px, w.y - self.py) < 22:
                    w.hit_t = 1.0
                    self.hp -= 9
                    self.msg = "A wolf bites you!"
                    self.msg_t = 2.0
            self.wolves = [w for w in self.wolves
                           if 0 < w.x < GRID_W * TILE and 0 < w.y < GRID_H * TILE]
        else:
            self.wolves.clear()

    # -- rendering -----------------------------------------------------------

    def draw(self, surf):
        for y in range(GRID_H):
            for x in range(GRID_W):
                c = self.grid[y][x]
                if c == "g":
                    col = (74, 110, 58) if (x + y) % 2 else (78, 114, 62)
                elif c == "w":
                    col = (52, 96, 168)
                elif c == "t":
                    col = (74, 110, 58)
                elif c == "r":
                    col = (74, 110, 58)
                else:
                    col = (84, 122, 62)
                pygame.draw.rect(surf, col, (x * TILE, y * TILE, TILE, TILE))
        for y in range(GRID_H):
            for x in range(GRID_W):
                c = self.grid[y][x]
                cx, cy = x * TILE + TILE // 2, y * TILE + TILE // 2
                if c == "w":
                    pygame.draw.circle(surf, (70, 120, 190), (cx, cy), 6)
                elif c == "t":
                    pygame.draw.rect(surf, (96, 70, 44), (cx - 3, cy + 4, 6, 8))
                    pygame.draw.circle(surf, (40, 110, 52), (cx, cy - 2), 10)
                elif c == "r":
                    pygame.draw.circle(surf, (130, 128, 136), (cx, cy + 2), 8)
                    pygame.draw.circle(surf, (150, 148, 156), (cx - 3, cy), 4)
                elif c == "b":
                    pygame.draw.circle(surf, (60, 140, 70), (cx, cy + 2), 8)
                    for k in range(4):
                        a = k * 1.57 + 0.4
                        pygame.draw.circle(surf, (220, 70, 90),
                                           (cx + math.cos(a) * 6, cy + 2 + math.sin(a) * 6), 2)
        for wx, wy in self.walls:
            pygame.draw.rect(surf, (120, 100, 70),
                             (wx * TILE + 1, wy * TILE + 1, TILE - 2, TILE - 2),
                             border_radius=3)
            pygame.draw.rect(surf, (80, 64, 44),
                             (wx * TILE + 1, wy * TILE + 1, TILE - 2, 4))
        for f in self.fires:
            pygame.draw.circle(surf, (60, 50, 36), (int(f["x"]), int(f["y"])), 9)
            pygame.draw.circle(surf, (255, 170, 60), (int(f["x"]), int(f["y"]) - 4), 5)
            pygame.draw.circle(surf, (255, 230, 120), (int(f["x"]), int(f["y"]) - 5), 3)
        for t in self.torches:
            pygame.draw.line(surf, (96, 70, 44), (t["x"], t["y"] + 6), (t["x"], t["y"] - 8), 3)
            pygame.draw.circle(surf, (255, 200, 90), (int(t["x"]), int(t["y"]) - 10), 4)
            pygame.draw.circle(surf, (255, 240, 160), (int(t["x"]), int(t["y"]) - 11), 2)
        for w in self.wolves:
            x, y = int(w.x), int(w.y)
            pygame.draw.circle(surf, (120, 120, 128), (x, y), 10)
            pygame.draw.circle(surf, (160, 160, 168), (x - 3, y - 4), 5)
            pygame.draw.circle(surf, (255, 60, 60), (x - 4, y - 5), 2)
            pygame.draw.circle(surf, (255, 60, 60), (x + 4, y - 5), 2)
            pygame.draw.line(surf, (120, 120, 128), (x - 9, y - 6), (x - 13, y - 9), 3)
            pygame.draw.line(surf, (120, 120, 128), (x + 9, y - 6), (x + 13, y - 9), 3)
        self.particles.draw(surf)
        px, py = int(self.px), int(self.py)
        pygame.draw.circle(surf, (90, 160, 255), (px, py), 11)
        pygame.draw.circle(surf, (210, 230, 255), (px - 4, py - 3), 3)
        pygame.draw.circle(surf, (210, 230, 255), (px + 4, py - 3), 3)

        if self.is_night():
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((0, 0, 30, 150))
            surf.blit(veil, (0, 0))
            glow = pygame.Surface((90, 90), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 200, 80, 60), (45, 45), 45)
            surf.blit(glow, (px - 45, py - 45))
            for f in self.fires:
                surf.blit(glow, (int(f["x"]) - 45, int(f["y"]) - 45))
            for t in self.torches:
                surf.blit(glow, (int(t["x"]) - 45, int(t["y"]) - 45))

        h = 36
        pygame.draw.rect(surf, (14, 14, 22), (0, HEIGHT - h, WIDTH, h))
        pygame.draw.rect(surf, (255, 208, 74), (0, HEIGHT - h, WIDTH, 2))
        draw_health_bar(surf, 10, HEIGHT - h + 4, 84, 12, self.hp / 100, fg=(255, 100, 110))
        draw_text(surf, "HP", 11, (255, 255, 255), (10, HEIGHT - h + 20))
        draw_health_bar(surf, 100, HEIGHT - h + 4, 84, 12, self.kcal / 3000, fg=(255, 200, 90))
        draw_text(surf, "KCAL", 11, (255, 255, 255), (100, HEIGHT - h + 20))
        draw_health_bar(surf, 190, HEIGHT - h + 4, 84, 12, self.water / 3, fg=(120, 200, 255))
        draw_text(surf, "WATER", 11, (255, 255, 255), (190, HEIGHT - h + 20))
        draw_health_bar(surf, 280, HEIGHT - h + 4, 84, 12,
                        (self.body - 30) / 10, fg=(255, 170, 90))
        draw_text(surf, "BODY°C", 11, (255, 255, 255), (280, HEIGHT - h + 20))
        hh = int(self.clock())
        mm = int((self.clock() - hh) * 60)
        icon = "☀" if not self.is_night() else "🌙"
        draw_text(surf, f"{icon} Day {self.day}/{DAYS_TO_WIN} · {hh:02d}:{mm:02d} · "
                        f"{self.air_temp():.0f}°C", 15, (255, 208, 74),
                  (WIDTH - 10, HEIGHT - h + 4), align="topright")
        draw_text(surf, f"🪵 {self.wood}  🪨 {self.stone}  🫐 {self.berries}  "
                        f"💧 {self.canteen:.1f}L", 14, (220, 224, 240),
                  (WIDTH - 10, HEIGHT - 18), align="topright")
        draw_text(surf, "E gather · C craft · F eat · G drink", 12, (140, 146, 175),
                  (WIDTH // 2, HEIGHT - h + 6), align="center")
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 18, (255, 255, 255), (WIDTH // 2, 60),
                      align="center", outline=1)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/survival.py
    from games.engine import App
    App(Game).run()
