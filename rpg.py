"""Quest RPG — a tiny top-down overworld adventure with NPCs and slimes."""
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         distance, clamp)
except ImportError:  # allow direct run: python games/rpg.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              distance, clamp)

TW, TH = 40, 30
TILE = 32
WORLD_W, WORLD_H = TW * TILE, TH * TILE
QUEST_KILLS = 6
SOLID = "TWR"

NPCS = [
    (22, 14, "Elder", ["Welcome, hero!", "Slimes have overrun the valley.",
                       f"Slay {QUEST_KILLS} of them and I will reward you."]),
    (26, 16, "Mae", ["The berries west are tasty.", "Careful near the water, it's deep."]),
    (18, 12, "Finn", ["Monsters drop gold, you know.", "Experience makes you stronger."]),
]


class Game(Game):
    name = "Quest RPG"
    emoji = "🧙"
    tagline = "Slay slimes, talk to townsfolk, level up."
    controls = "Arrows/WASD move · E talk · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.rng = random.Random(7)
        self.world = self.gen_world()
        self.p = {"x": TW // 2 * TILE, "y": TH // 2 * TILE,
                  "hp": 100, "max_hp": 100, "level": 1, "xp": 0, "gold": 0,
                  "face": (0, 1), "atk_cd": 0.0, "inv": 0.0}
        self.kills = 0
        self.monsters = []
        self.pickups = []
        self.npcs = [dict(x=x * TILE + TILE // 2, y=y * TILE + TILE // 2,
                          name=n, lines=lines, i=0) for x, y, n, lines in NPCS]
        self.talk = None
        self.banner = None
        self.banner_t = 0.0
        self.over = False
        self.spawn_monster()
        self.spawn_monster()
        self.spawn_monster()

    def gen_world(self):
        g = [["." for _ in range(TW)] for _ in range(TH)]
        for x in range(TW):
            g[TH // 2][x] = "p"
        for y in range(TH):
            g[y][TW // 2] = "p"
        for y in range(TH):
            for x in range(TW):
                if g[y][x] == "p":
                    continue
                r = self.rng.random()
                if r < 0.10:
                    g[y][x] = "T"
                elif r < 0.13:
                    g[y][x] = "R"
        for _ in range(6):
            cx, cy = self.rng.randrange(4, TW - 4), self.rng.randrange(4, TH - 4)
            rad = self.rng.randint(2, 3)
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    if dx * dx + dy * dy <= rad * rad + 1:
                        x, y = cx + dx, cy + dy
                        if 0 <= x < TW and 0 <= y < TH and g[y][x] == ".":
                            g[y][x] = "W"
        return g

    def spawn_monster(self):
        for _ in range(40):
            x = self.rng.randrange(4, TW - 4)
            y = self.rng.randrange(4, TH - 4)
            if self.world[y][x] not in SOLID and distance(x * TILE, y * TILE,
                                                          self.p["x"], self.p["y"]) > 260:
                lvl = self.p["level"]
                self.monsters.append(dict(x=x * TILE + TILE // 2, y=y * TILE + TILE // 2,
                                          hp=22 + lvl * 6, max_hp=22 + lvl * 6,
                                          dmg=2 + lvl, atk_cd=0.0, wander=0.0,
                                          tx=0, ty=0, flash=0.0))
                return

    def tile(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if not (0 <= tx < TW and 0 <= ty < TH):
            return "#"
        return self.world[ty][tx]

    def blocked(self, x, y, half=9):
        for dx in (-half, half):
            for dy in (-half, half):
                if self.tile(x + dx, y + dy) in SOLID:
                    return True
        return False

    def move_player(self, ox, oy):
        if ox and not self.blocked(self.p["x"] + ox, self.p["y"]):
            self.p["x"] += ox
        if oy and not self.blocked(self.p["x"], self.p["y"] + oy):
            self.p["y"] += oy
        self.p["x"] = clamp(self.p["x"], 12, WORLD_W - 12)
        self.p["y"] = clamp(self.p["y"], 12, WORLD_H - 12)

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
            if self.talk is not None:
                if event.key in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN):
                    self.talk["i"] += 1
                    if self.talk["i"] >= len(self.talk["lines"]):
                        self.talk = None
                return
            if event.key in (pygame.K_e, pygame.K_SPACE):
                self.try_talk()

    def try_talk(self):
        for npc in self.npcs:
            if distance(npc["x"], npc["y"], self.p["x"], self.p["y"]) < 40:
                self.talk = npc
                npc["i"] = 0
                return

    def update(self, dt):
        self.particles.update(dt)
        if self.over or self.talk is not None:
            return
        self.banner_t = max(0.0, self.banner_t - dt)
        p = self.p
        p["inv"] = max(0.0, p["inv"] - dt)
        dx = dy = 0
        if self.held(pygame.K_LEFT, pygame.K_a):
            dx -= 1
        if self.held(pygame.K_RIGHT, pygame.K_d):
            dx += 1
        if self.held(pygame.K_UP, pygame.K_w):
            dy -= 1
        if self.held(pygame.K_DOWN, pygame.K_s):
            dy += 1
        if dx or dy:
            p["face"] = (dx, dy)
        speed = 200 * dt
        self.move_player(dx * speed, dy * speed)
        p["atk_cd"] = max(0.0, p["atk_cd"] - dt)

        for m in list(self.monsters):
            m["atk_cd"] = max(0.0, m["atk_cd"] - dt)
            m["flash"] = max(0.0, m["flash"] - dt)
            d = distance(m["x"], m["y"], p["x"], p["y"])
            if d < 60 and p["atk_cd"] <= 0:
                p["atk_cd"] = 0.45
                m["hp"] -= 5 + p["level"] * 2
                m["flash"] = 0.15
                self.particles.burst(m["x"], m["y"], (255, 90, 90), n=9, speed=100)
                if m["hp"] <= 0:
                    self.kill_monster(m)
            elif d < 150:
                self.move_monster(m, p["x"], p["y"], dt)
            elif m["wander"] <= 0:
                m["wander"] = self.rng.uniform(1.2, 3.0)
                m["tx"] = m["x"] + self.rng.uniform(-70, 70)
                m["ty"] = m["y"] + self.rng.uniform(-70, 70)
            else:
                m["wander"] -= dt
                self.move_monster(m, m["tx"], m["ty"], dt)
            if d < 46 and m["atk_cd"] <= 0:
                m["atk_cd"] = 1.0
                p["hp"] -= 3 + m["dmg"]
                self.particles.burst(p["x"], p["y"], (220, 60, 60), n=7, speed=90)
                if p["hp"] <= 0:
                    p["hp"] = 0
                    self.over = True
                    self.show_menu("YOU DIED", ["Retry", "Main Menu"],
                                   f"Level {p['level']} · {self.kills} slimes slain")

        for it in list(self.pickups):
            if distance(it["x"], it["y"], p["x"], p["y"]) < 28:
                self.pickups.remove(it)
                if it["kind"] == "heart":
                    p["hp"] = min(p["max_hp"], p["hp"] + 25)
                elif it["kind"] == "coin":
                    p["gold"] += 10
                self.particles.burst(it["x"], it["y"], (255, 220, 90), n=10)

        if len(self.monsters) < 6 and self.rng.random() < dt * 0.5:
            self.spawn_monster()

    def move_monster(self, m, tx, ty, dt):
        d = distance(m["x"], m["y"], tx, ty)
        if d < 4:
            return
        spd = 55 * dt
        nx = m["x"] + (tx - m["x"]) / d * spd
        ny = m["y"] + (ty - m["y"]) / d * spd
        if not self.blocked(nx, m["y"], 8):
            m["x"] = nx
        if not self.blocked(m["x"], ny, 8):
            m["y"] = ny

    def kill_monster(self, m):
        self.monsters.remove(m)
        self.kills += 1
        p = self.p
        p["xp"] += 12
        p["gold"] += 5 + self.rng.randrange(6)
        self.particles.burst(m["x"], m["y"], (160, 90, 220), n=16)
        r = self.rng.random()
        if r < 0.20:
            self.pickups.append(dict(kind="heart", x=m["x"], y=m["y"]))
        elif r < 0.45:
            self.pickups.append(dict(kind="coin", x=m["x"], y=m["y"]))
        if p["xp"] >= p["level"] * 30:
            p["level"] += 1
            p["max_hp"] += 25
            p["hp"] = p["max_hp"]
            self.banner = f"LEVEL UP! You are now level {p['level']}"
            self.banner_t = 2.5
        elif self.kills == QUEST_KILLS:
            self.banner = "Quest complete! Return to the Elder."
            self.banner_t = 3.0

    def draw(self, surf):
        camx = clamp(self.p["x"] - WIDTH // 2, 0, WORLD_W - WIDTH)
        camy = clamp(self.p["y"] - HEIGHT // 2, 0, WORLD_H - HEIGHT)
        surf.fill((24, 30, 26))
        for ty in range(int(camy // TILE) - 1, int((camy + HEIGHT) // TILE) + 2):
            for tx in range(int(camx // TILE) - 1, int((camx + WIDTH) // TILE) + 2):
                if not (0 <= tx < TW and 0 <= ty < TH):
                    continue
                c = self.world[ty][tx]
                sx, sy = tx * TILE - camx, ty * TILE - camy
                if c == ".":
                    shade = 46 + ((tx * 7 + ty * 13) % 3) * 5
                    pygame.draw.rect(surf, (shade, 84 + (ty % 2) * 6, shade - 8),
                                     (sx, sy, TILE, TILE))
                elif c == "p":
                    pygame.draw.rect(surf, (128, 110, 82), (sx, sy, TILE, TILE))
                    pygame.draw.rect(surf, (110, 94, 70), (sx, sy, TILE, 3))
                elif c == "W":
                    pygame.draw.rect(surf, (40, 90, 160), (sx, sy, TILE, TILE))
                elif c == "T":
                    pygame.draw.rect(surf, (46, 84, 46), (sx, sy, TILE, TILE))
                    pygame.draw.rect(surf, (96, 70, 44), (sx + 12, sy + 18, 8, 12))
                    pygame.draw.circle(surf, (36, 110, 48), (sx + 16, sy + 10), 12)
                elif c == "R":
                    pygame.draw.rect(surf, (46, 84, 46), (sx, sy, TILE, TILE))
                    pygame.draw.circle(surf, (120, 120, 128), (sx + 16, sy + 16), 11)
                    pygame.draw.circle(surf, (140, 140, 148), (sx + 12, sy + 12), 5)
        for it in self.pickups:
            sx, sy = it["x"] - camx, it["y"] - camy
            if it["kind"] == "heart":
                pygame.draw.circle(surf, (235, 70, 90), (int(sx), int(sy)), 7)
                pygame.draw.circle(surf, (255, 140, 150), (int(sx) - 2, int(sy) - 2), 3)
            else:
                pygame.draw.circle(surf, (255, 200, 60), (int(sx), int(sy)), 6)
        for m in self.monsters:
            sx, sy = int(m["x"] - camx), int(m["y"] - camy)
            col = (255, 255, 255) if m["flash"] > 0 else (150, 70, 200)
            pygame.draw.circle(surf, col, (sx, sy), 11)
            pygame.draw.circle(surf, (30, 30, 50), (sx - 4, sy - 3), 3)
            pygame.draw.circle(surf, (30, 30, 50), (sx + 4, sy - 3), 3)
            draw_health_bar(surf, sx - 12, sy - 20, 24, 4, m["hp"] / m["max_hp"],
                            fg=(200, 80, 200))
        for npc in self.npcs:
            sx, sy = int(npc["x"] - camx), int(npc["y"] - camy)
            pygame.draw.circle(surf, (120, 150, 255), (sx, sy), 11)
            pygame.draw.circle(surf, (240, 240, 255), (sx - 4, sy - 3), 3)
            pygame.draw.circle(surf, (240, 240, 255), (sx + 4, sy - 3), 3)
            draw_text(surf, npc["name"], 12, (230, 235, 255), (sx, sy - 22), align="center")
        p = self.p
        px, py = int(p["x"] - camx), int(p["y"] - camy)
        pygame.draw.circle(surf, (90, 160, 255), (px, py), 12)
        pygame.draw.circle(surf, (200, 220, 255), (px - 4, py - 3), 3)
        pygame.draw.circle(surf, (200, 220, 255), (px + 4, py - 3), 3)
        self.particles.draw(surf)

        if self.talk is not None:
            box = pygame.Rect(40, HEIGHT - 130, WIDTH - 80, 110)
            pygame.draw.rect(surf, (18, 22, 40), box, border_radius=10)
            pygame.draw.rect(surf, (120, 130, 180), box, 2, border_radius=10)
            draw_text(surf, f"{self.talk['name']}:", 20, (255, 208, 74), (box.x + 16, box.y + 10))
            draw_text(surf, self.talk["lines"][self.talk["i"]], 19, (230, 234, 248),
                      (box.x + 16, box.y + 44), max_width=box.w - 32)
            draw_text(surf, "▼", 16, (255, 208, 74), (box.right - 18, box.bottom - 22))

        hp_r = p["hp"] / p["max_hp"]
        draw_text(surf, f"Lv {p['level']}", 18, (255, 208, 74), (14, 10), bold=True)
        draw_health_bar(surf, 70, 10, 150, 16, hp_r, fg=(90, 220, 120))
        draw_text(surf, f"{p['hp']}/{p['max_hp']}", 14, (255, 255, 255), (70, 31))
        draw_text(surf, f"⚔ {p['gold']}g   XP {p['xp']}/{p['level'] * 30}", 15,
                  (220, 224, 240), (240, 10))
        draw_text(surf, f"Slimes: {self.kills}/{QUEST_KILLS}", 16,
                  (255, 120, 120) if self.kills < QUEST_KILLS else (120, 255, 140),
                  (WIDTH - 14, 10), align="topright")
        draw_text(surf, "Quest: slay the slimes, then talk to the Elder.", 13,
                  (150, 158, 190), (WIDTH - 14, 32), align="topright")
        if self.banner and self.banner_t > 0:
            draw_text(surf, self.banner, 24, (255, 220, 120), (WIDTH // 2, 70),
                      align="center", outline=2)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/rpg.py
    from games.engine import App
    App(Game).run()
