"""Deep Dungeon — a grid-based roguelike crawler with fog of war."""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, WIDTH, HEIGHT, clamp)
except ImportError:  # allow direct run: python games/dungeon.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, WIDTH, HEIGHT, clamp)

GW, GH = 40, 30
TILE = 20
DEPTHS_TO_WIN = 5

MONSTER_TYPES = {
    "slime":     dict(hp=20, atk=4, color=(120, 200, 90)),
    "bat":       dict(hp=12, atk=3, color=(160, 120, 220)),
    "skeleton":  dict(hp=30, atk=7, color=(220, 220, 225)),
    "dragon":    dict(hp=220, atk=16, color=(255, 90, 60)),
}


class Game(Game):
    name = "Deep Dungeon"
    emoji = "🗺️"
    tagline = "Descend five levels. Find the stairs. Don't die."
    controls = "Arrows/WASD step · Q drink potion · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.depth = 1
        self.hp = 100
        self.max_hp = 100
        self.atk = 8
        self.level = 1
        self.xp = 0
        self.gold = 0
        self.keys = 0
        self.potions = 2
        self.food = 100               # classic roguelike hunger
        self.steps = 0
        self.over = False
        self.won = False
        self.msg = ""
        self.msg_t = 0.0
        self.gen_level()

    def gen_level(self):
        rng = random.Random(self.depth * 977 + 13)
        g = [["#" for _ in range(GW)] for _ in range(GH)]
        rooms = []
        for _ in range(8):
            w = rng.randint(5, 9)
            h = rng.randint(4, 6)
            x = rng.randint(1, GW - w - 2)
            y = rng.randint(1, GH - h - 2)
            if any(abs(x - rx) < w + 2 and abs(y - ry) < h + 2 for rx, ry, rw, rh in rooms):
                continue
            rooms.append((x, y, w, h))
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    g[yy][xx] = "."
        for i in range(len(rooms) - 1):
            x1, y1 = rooms[i][0] + rooms[i][2] // 2, rooms[i][1] + rooms[i][3] // 2
            x2, y2 = rooms[i + 1][0] + rooms[i + 1][2] // 2, rooms[i + 1][1] + rooms[i + 1][3] // 2
            if rng.random() < 0.5:
                self.carve(g, x1, y2, x1, y1)
                self.carve(g, x1, y2, x2, y2)
            else:
                self.carve(g, x2, y1, x1, y1)
                self.carve(g, x2, y1, x2, y2)
        self.grid = g
        self.explored = set()
        self.monsters = []
        self.chests = []
        self.items = []
        start_room = rooms[0]
        self.px = start_room[0] + start_room[2] // 2
        self.py = start_room[1] + start_room[3] // 2
        last = rooms[-1]
        stairs = (last[0] + last[2] // 2, last[1] + last[3] // 2)
        self.stairs = stairs
        if self.depth >= DEPTHS_TO_WIN:
            self.monsters.append(dict(x=stairs[0], y=stairs[1] + 1, kind="dragon",
                                      hp=MONSTER_TYPES["dragon"]["hp"],
                                      max_hp=MONSTER_TYPES["dragon"]["hp"],
                                      atk=MONSTER_TYPES["dragon"]["atk"]))
        for room in rooms[1:]:
            rx, ry, rw, rh = room
            for _ in range(rng.randint(1, 3)):
                x, y = rx + rng.randrange(rw), ry + rng.randrange(rh)
                if (x, y) == self.stairs:
                    continue
                kind = rng.choice(["slime", "slime", "bat", "skeleton"] if self.depth > 2
                                  else ["slime", "slime", "bat"])
                t = MONSTER_TYPES[kind]
                hp = int(t["hp"] * (1 + (self.depth - 1) * 0.4))
                self.monsters.append(dict(x=x, y=y, kind=kind, hp=hp, max_hp=hp,
                                          atk=t["atk"] + (self.depth - 1) * 2))
            n_items = rng.randint(0, 2)
            for _ in range(n_items):
                x, y = rx + rng.randrange(rw), ry + rng.randrange(rh)
                if (x, y) == self.stairs:
                    continue
                r = rng.random()
                if r < 0.25:
                    self.items.append(dict(x=x, y=y, kind="potion"))
                elif r < 0.45:
                    self.items.append(dict(x=x, y=y, kind="gold"))
                elif r < 0.7:
                    self.items.append(dict(x=x, y=y, kind="key"))
                else:
                    self.items.append(dict(x=x, y=y, kind="food"))
            if rng.random() < 0.7:
                cx, cy = rx + rng.randrange(rw), ry + rng.randrange(rh)
                if (cx, cy) != self.stairs:
                    self.chests.append(dict(x=cx, y=cy, opened=False))
        self.move_t = 0.0
        self.msg = f"Depth {self.depth} — find the stairs"
        self.msg_t = 3.0

    def carve(self, g, x1, y1, x2, y2):
        while x1 != x2:
            g[y1][x1] = "."
            x1 += 1 if x2 > x1 else -1
        while y1 != y2:
            g[y1][x1] = "."
            y1 += 1 if y2 > y1 else -1

    def solid(self, x, y):
        if not (0 <= x < GW and 0 <= y < GH):
            return True
        return self.grid[y][x] == "#"

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
            d = None
            if event.key in (pygame.K_LEFT, pygame.K_a):
                d = (-1, 0)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                d = (1, 0)
            elif event.key in (pygame.K_UP, pygame.K_w):
                d = (0, -1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                d = (0, 1)
            if d:
                self.step(d)
            elif event.key == pygame.K_q and self.potions > 0:
                self.potions -= 1
                self.hp = min(self.max_hp, self.hp + 50)
                self.set_msg("You drink a potion. +50 HP")

    def set_msg(self, text):
        self.msg = text
        self.msg_t = 2.5

    def step(self, d):
        self.steps += 1
        nx, ny = self.px + d[0], self.py + d[1]
        if self.solid(nx, ny):
            return
        self.px, self.py = nx, ny
        for c in self.chests:
            if (c["x"], c["y"]) == (nx, ny) and not c["opened"]:
                c["opened"] = True
                r = random.random()
                if r < 0.35:
                    self.potions += 1
                    self.set_msg("Chest! +1 potion")
                elif r < 0.65:
                    self.gold += 25
                    self.set_msg("Chest! +25 gold")
                elif r < 0.85:
                    self.keys += 1
                    self.set_msg("Chest! +1 key")
                else:
                    self.food = min(100, self.food + 35)
                    self.set_msg("Chest! Rations. +35 food")
        for it in list(self.items):
            if (it["x"], it["y"]) == (nx, ny):
                self.items.remove(it)
                if it["kind"] == "potion":
                    self.potions += 1
                    self.set_msg("A potion! (+1)")
                elif it["kind"] == "gold":
                    self.gold += 15
                    self.set_msg("Gold! (+15)")
                elif it["kind"] == "key":
                    self.keys += 1
                    self.set_msg("A key! (+1)")
                else:
                    self.food = min(100, self.food + 30)
                    self.set_msg("You eat a ration. +30 food")
        if self.grid[ny][nx] == "D":
            if self.keys > 0:
                self.keys -= 1
                self.grid[ny][nx] = "."
                self.set_msg("You unlock the door.")
            else:
                self.px, self.py = nx - d[0], ny - d[1]
                self.set_msg("Locked! You need a key.")
                return
        if (nx, ny) == self.stairs:
            if self.depth >= DEPTHS_TO_WIN:
                self.over = True
                self.won = True
                self.show_menu("DUNGEON CLEARED!", ["Play Again", "Main Menu"],
                               f"Depth {self.depth} · {self.gold} gold",
                               title_color=(120, 255, 150))
                return
            self.depth += 1
            self.hp = min(self.max_hp, self.hp + 25)
            self.food = min(100, self.food + 20)
            self.gen_level()
            return
        # Hunger: every step costs a little food, like the original Rogue.
        self.food = max(0.0, self.food - 0.9)
        if self.food <= 20:
            self.hp -= 4 if self.food <= 0 else 2
            if self.hp <= 0:
                self.hp = 0
                self.over = True
                self.show_menu("YOU DIED OF HUNGER", ["Retry", "Main Menu"],
                               f"Depth {self.depth} · {self.gold} gold")
                return
            if self.food <= 0 and random.random() < 0.3:
                self.set_msg("You are starving!")
            elif self.food <= 20 and random.random() < 0.15:
                self.set_msg("You are very hungry.")
        self.monster_turn()
        self.compute_fov()

    def monster_turn(self):
        for m in list(self.monsters):
            d = abs(m["x"] - self.px) + abs(m["y"] - self.py)
            if d <= 1:
                m["hp"] -= self.atk + random.randrange(0, 4)
                if m["hp"] <= 0:
                    self.monsters.remove(m)
                    self.xp += 10 + self.depth * 4
                    self.gold += random.randrange(3, 9)
                    if self.xp >= self.level * 40:
                        self.level += 1
                        self.max_hp += 15
                        self.atk += 2
                        self.hp = min(self.max_hp, self.hp + 30)
                        self.set_msg(f"Level up! Now level {self.level}.")
                    else:
                        self.set_msg(f"You slay the {m['kind']}.")
                else:
                    self.hp -= m["atk"] + random.randrange(0, 3)
                    self.set_msg(f"The {m['kind']} hits you!")
                    if self.hp <= 0:
                        self.hp = 0
                        self.over = True
                        self.show_menu("YOU DIED", ["Retry", "Main Menu"],
                                       f"Depth {self.depth} · {self.gold} gold")
                    return
            elif d <= 7 and random.random() < 0.8:
                step = self.approach(m)
                if not self.solid(m["x"] + step[0], m["y"] + step[1]) and \
                        not any((o["x"], o["y"]) == (m["x"] + step[0], m["y"] + step[1])
                                for o in self.monsters if o is not m):
                    m["x"] += step[0]
                    m["y"] += step[1]

    def approach(self, m):
        dx = 1 if self.px > m["x"] else -1 if self.px < m["x"] else 0
        dy = 1 if self.py > m["y"] else -1 if self.py < m["y"] else 0
        if dx and dy:
            if random.random() < 0.5:
                return (dx, 0)
            return (0, dy)
        return (dx, dy)

    def compute_fov(self):
        radius = 7
        self.visible = set()
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                x, y = self.px, self.py
                steps = max(abs(dx), abs(dy))
                if steps == 0:
                    self.visible.add((self.px, self.py))
                    self.explored.add((self.px, self.py))
                    continue
                ok = True
                for s in range(1, steps + 1):
                    x = self.px + dx * s / steps
                    y = self.py + dy * s / steps
                    cx, cy = int(round(x)), int(round(y))
                    self.visible.add((cx, cy))
                    self.explored.add((cx, cy))
                    if self.grid[cy][cx] == "#":
                        break

    def update(self, dt):
        self.msg_t = max(0.0, self.msg_t - dt)

    def draw(self, surf):
        surf.fill((10, 10, 16))
        for y in range(GH):
            for x in range(GW):
                if (x, y) not in self.explored:
                    continue
                in_view = (x, y) in self.visible
                c = self.grid[y][x]
                if c == "#":
                    col = (60, 60, 78) if in_view else (34, 34, 46)
                else:
                    col = (40, 38, 52) if in_view else (24, 23, 32)
                pygame.draw.rect(surf, col, (x * TILE, y * TILE, TILE, TILE))
                if c == "D":
                    pygame.draw.rect(surf, (150, 120, 60), (x * TILE + 4, y * TILE + 4, TILE - 8, TILE - 8))
                if (x, y) == self.stairs and in_view:
                    for k in range(3):
                        pygame.draw.circle(surf, (120, 230, 160), (x * TILE + 10, y * TILE + 10),
                                           7 - k * 2, 1)
                    draw_text(surf, "▼", 12, (120, 230, 160), (x * TILE + 10, y * TILE + 8),
                              align="center")
        for it in self.items:
            x, y = it["x"], it["y"]
            if (x, y) in self.visible:
                col = {"potion": (255, 120, 160), "gold": (255, 210, 80),
                       "key": (255, 220, 140), "food": (210, 150, 80)}[it["kind"]]
                pygame.draw.circle(surf, col, (x * TILE + 10, y * TILE + 10), 5)
        for c in self.chests:
            x, y = c["x"], c["y"]
            if (x, y) in self.visible and not c["opened"]:
                pygame.draw.rect(surf, (140, 96, 50), (x * TILE + 3, y * TILE + 3, TILE - 6, TILE - 6))
                pygame.draw.rect(surf, (255, 208, 74), (x * TILE + 3, y * TILE + 8, TILE - 6, 3))
        for m in self.monsters:
            x, y = m["x"], m["y"]
            if (x, y) in self.visible:
                t = MONSTER_TYPES[m["kind"]]
                col = (255, 255, 255) if m["hp"] <= 0 else t["color"]
                pygame.draw.circle(surf, col, (x * TILE + 10, y * TILE + 10), 8)
                pygame.draw.circle(surf, (20, 20, 30), (x * TILE + 7, y * TILE + 8), 2)
                pygame.draw.circle(surf, (20, 20, 30), (x * TILE + 13, y * TILE + 8), 2)
                draw_health_bar(surf, x * TILE + 2, y * TILE, 16, 3, m["hp"] / m["max_hp"],
                                fg=(220, 90, 90))
        if not self.over:
            pygame.draw.circle(surf, (90, 160, 255), (self.px * TILE + 10, self.py * TILE + 10), 9)
            pygame.draw.circle(surf, (210, 230, 255), (self.px * TILE + 7, self.py * TILE + 8), 3)

        h = 34
        pygame.draw.rect(surf, (14, 14, 22), (0, HEIGHT - h, WIDTH, h))
        pygame.draw.rect(surf, (255, 208, 74), (0, HEIGHT - h, WIDTH, 2))
        draw_text(surf, f"HP", 15, (255, 255, 255), (12, HEIGHT - h + 6))
        draw_health_bar(surf, 40, HEIGHT - h + 5, 130, 14, self.hp / self.max_hp,
                        fg=(255, 100, 110))
        draw_text(surf, f"Lv{self.level}  XP {self.xp}/{self.level * 40}", 13, (200, 204, 224),
                  (180, HEIGHT - h + 6))
        draw_text(surf, f"🍖 {int(self.food)}", 13,
                  (255, 190, 110) if self.food > 20 else (255, 90, 90),
                  (330, HEIGHT - h + 6))
        draw_text(surf, f"Depth {self.depth}/{DEPTHS_TO_WIN}", 15, (255, 208, 74),
                  (WIDTH - 14, HEIGHT - h + 6), align="topright", bold=True)
        draw_text(surf, f"🗝 {self.keys}   ⚱ {self.potions}   ⛁ {self.gold}", 14,
                  (220, 224, 240), (WIDTH - 14, HEIGHT - 16), align="topright")
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 18, (255, 208, 74), (WIDTH // 2, 22),
                      align="center", outline=1)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/dungeon.py
    from games.engine import App
    App(Game).run()
