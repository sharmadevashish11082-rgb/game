"""Rise of Kingdoms — a Civ-style 4X-lite: found cities, train armies, conquer."""
import random

import pygame

try:
    from .engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, clamp, Button
except ImportError:  # allow direct run: python games/civ.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, clamp, Button

MW, MH = 24, 18
TILE = 32
BOARD_W, BOARD_H = MW * TILE, MH * TILE
PANEL_X = BOARD_W + 10
TURN_LIMIT = 45

UNIT_TYPES = {
    "settler":  dict(name="Settler",  cost=50, str=0,  moves=2, color=(255, 210, 120)),
    "warrior":  dict(name="Warrior",  cost=30, str=6,  moves=2, color=(220, 90, 90)),
    "archer":   dict(name="Archer",   cost=45, str=8,  moves=2, color=(120, 200, 90)),
    "horseman": dict(name="Horseman", cost=70, str=11, moves=3, color=(150, 120, 255)),
}
TECH = {1: ["warrior", "settler"], 2: ["archer"], 3: ["horseman"]}
TERRAIN_COLORS = {
    "g": (84, 140, 70), "f": (40, 100, 48), "h": (150, 130, 80),
    "w": (60, 110, 190), "m": (110, 110, 120),
}


class Game(Game):
    name = "Rise of Kingdoms"
    emoji = "🌎"
    tagline = "Found cities, research tech, conquer the map."
    controls = "Click unit → click move/attack · Enter/End Turn · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.map = self.gen_map()
        self.turn = 1
        self.over = False
        self.winner = None
        self.selected = None
        self.path = []
        self.msg = ""
        self.msg_t = 0.0
        self.civs = []
        colors = [(90, 150, 255), (255, 90, 90), (120, 220, 120)]
        for i in range(3):
            x = 3 + i * 9
            y = 4 + (i % 2) * 9
            civ = dict(name=f"Civ {i + 1}", color=colors[i], gold=60, science=0,
                       tech=1, alive=True, cities=[], units=[], ai=(i != 0))
            civ["cities"].append(dict(x=x, y=y, hp=20, capital=True,
                                      name=f"City {i + 1}"))
            civ["units"].append(dict(x=x + 1, y=y, kind="settler", civ=i, moves=0))
            civ["units"].append(dict(x=x - 1, y=y, kind="warrior", civ=i, moves=0))
            self.civs.append(civ)
        self.phase = "player"
        self.end_btn = Button((PANEL_X, HEIGHT - 60, 180, 44), "End Turn [Enter]", size=16)
        self.buttons = []
        self.train_buttons = []
        self.city_sel = None
        self.hover_city_x = -1
        self.hover_city_y = -1
        self.update_buttons()
        self.turn_civ = 1

    def gen_map(self):
        rng = random.Random(42)
        g = [["g" for _ in range(MW)] for _ in range(MH)]
        for y in range(MH):
            for x in range(MW):
                r = rng.random()
                if r < 0.08:
                    g[y][x] = "f"
                elif r < 0.13:
                    g[y][x] = "h"
                elif r < 0.17:
                    g[y][x] = "w"
                elif r < 0.19:
                    g[y][x] = "m"
        # smoothing
        for _ in range(2):
            ng = [row[:] for row in g]
            for y in range(MH):
                for x in range(MW):
                    counts = {}
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < MH and 0 <= xx < MW:
                                counts[g[yy][xx]] = counts.get(g[yy][xx], 0) + 1
                    if counts.get("w", 0) >= 5:
                        ng[y][x] = "w"
                    elif counts.get("m", 0) >= 5:
                        ng[y][x] = "m"
            g = ng
        return g

    def tile(self, x, y):
        if not (0 <= x < MW and 0 <= y < MH):
            return "m"
        return self.map[y][x]

    def passable(self, x, y):
        return self.tile(x, y) not in ("w", "m")

    def unit_at(self, x, y):
        for civ in self.civs:
            for u in civ["units"]:
                if u["x"] == x and u["y"] == y:
                    return u
        return None

    def city_at(self, x, y):
        for civ in self.civs:
            for c in civ["cities"]:
                if c["x"] == x and c["y"] == y:
                    return c, civ
        return None, None

    def update_buttons(self):
        self.buttons = []
        if self.selected:
            u = self.selected
            if u["kind"] == "settler":
                self.buttons.append(Button((PANEL_X, 170, 180, 36),
                                           "Found City", size=15))
            else:
                self.buttons.append(Button((PANEL_X, 170, 180, 36),
                                           "Disband", size=15))
        self.train_buttons = []
        self.city_sel = None
        hx, hy = getattr(self, "hover_city_x", -1), getattr(self, "hover_city_y", -1)
        city = None
        for c in self.civs[0]["cities"]:
            if c["x"] == hx and c["y"] == hy:
                city = c
                break
        if city:
            self.city_sel = city
            civ = self.civs[0]
            y = 260
            for kind in TECH.get(civ["tech"], []):
                if UNIT_TYPES[kind]["cost"] <= civ["gold"]:
                    self.train_buttons.append(
                        Button((PANEL_X, y, 180, 30),
                               f"{UNIT_TYPES[kind]['name']} "
                               f"${UNIT_TYPES[kind]['cost']}", size=13))
                    y += 36

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.MOUSEMOTION:
            self.hover_city_x = (event.pos[0]) // TILE if event.pos[0] < BOARD_W else -1
            self.hover_city_y = (event.pos[1]) // TILE if event.pos[1] < BOARD_H else -1
            self.update_buttons()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if event.pos[0] < BOARD_W:
                self.click_board(event.pos)
            else:
                for b in self.buttons:
                    if b.handle(event):
                        self.do_action(b.label)
                        return
                for b in self.train_buttons:
                    if b.handle(event):
                        self.train(b.label.split()[0])
                        return
                if self.end_btn.handle(event):
                    self.end_turn()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_e):
                if self.phase == "player":
                    self.end_turn()

    def click_board(self, pos):
        if self.phase != "player":
            return
        x, y = pos[0] // TILE, pos[1] // TILE
        u = self.unit_at(x, y)
        if u and u["civ"] == 0:
            self.selected = u
            self.path = []
        elif self.selected:
            self.move_selected(x, y)

    def move_selected(self, x, y):
        u = self.selected
        if u["moves"] <= 0 or not self.passable(x, y):
            return
        target = self.unit_at(x, y)
        if target and target["civ"] != u["civ"]:
            self.battle(u, target)
            self.selected = None
            return
        city, civ = self.city_at(x, y)
        if city and civ != self.civs[u["civ"]]:
            self.attack_city(u, city, civ)
            self.selected = None
            return
        if city:
            return
        path = self.bfs(u["x"], u["y"], x, y, u["moves"])
        if path:
            u["x"], u["y"] = x, y
            u["moves"] -= len(path) - 1
            self.selected = None

    def bfs(self, sx, sy, tx, ty, max_steps):
        if (sx, sy) == (tx, ty):
            return []
        from collections import deque
        q = deque([(sx, sy)])
        prev = {(sx, sy): None}
        while q:
            x, y = q.popleft()
            if (x, y) == (tx, ty):
                path = []
                cur = (tx, ty)
                while cur:
                    path.append(cur)
                    cur = prev[cur]
                path.reverse()
                if len(path) - 1 <= max_steps:
                    return path
                return None
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in prev or not self.passable(nx, ny):
                    continue
                if self.unit_at(nx, ny) and (nx, ny) != (tx, ty):
                    continue
                prev[(nx, ny)] = (x, y)
                q.append((nx, ny))
        return None

    def battle(self, att, target):
        civ_a = self.civs[att["civ"]]
        civ_b = self.civs[target["civ"]]
        a_str = UNIT_TYPES[att["kind"]]["str"] + random.randrange(0, 5)
        b_str = UNIT_TYPES[target["kind"]]["str"] + random.randrange(0, 5)
        self.msg = f"{civ_a['name']} {att['kind']} vs {civ_b['name']} {target['kind']}"
        if a_str > b_str:
            civ_b["units"].remove(target)
            att["x"], att["y"] = target["x"], target["y"]
            att["moves"] = 0
            self.msg += " — attacker wins!"
        else:
            civ_a["units"].remove(att)
            self.msg += " — defender holds!"
        self.msg_t = 3.0
        self.check_alive()

    def attack_city(self, u, city, civ):
        u_str = UNIT_TYPES[u["kind"]]["str"] + random.randrange(0, 5)
        city_str = 8 + random.randrange(0, 5)
        if u_str > city_str:
            city["hp"] -= 6
            u["moves"] = 0
            self.msg = f"You strike {civ['name']}'s city! ({city['hp']} hp)"
            if city["hp"] <= 0:
                civ["cities"].remove(city)
                self.msg = f"You captured a city of {civ['name']}!"
                self.check_alive()
        else:
            self.civs[u["civ"]]["units"].remove(u)
            self.msg = "The city walls hold — your unit falls!"
        self.msg_t = 3.0

    def do_action(self, label):
        u = self.selected
        if label == "Found City":
            civ = self.civs[u["civ"]]
            civ["units"].remove(u)
            civ["cities"].append(dict(x=u["x"], y=u["y"], hp=20, capital=False,
                                      name=f"Outpost"))
            self.msg = "You founded a new city!"
            self.msg_t = 2.5
        elif label == "Disband":
            civ = self.civs[u["civ"]]
            civ["units"].remove(u)
            civ["gold"] += 10
        self.selected = None
        self.update_buttons()

    def train(self, kind):
        if not self.city_sel:
            return
        civ = self.civs[0]
        if kind not in TECH.get(civ["tech"], []):
            return
        cost = UNIT_TYPES[kind]["cost"]
        if civ["gold"] < cost:
            return
        civ["gold"] -= cost
        x, y = self.city_sel["x"], self.city_sel["y"]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if self.passable(nx, ny) and not self.unit_at(nx, ny):
                civ["units"].append(dict(x=nx, y=ny, kind=kind, civ=0, moves=0))
                break
        self.update_buttons()

    def end_turn(self):
        if self.phase != "player":
            return
        self.selected = None
        self.turn_civ = 1
        self.phase = "ai"
        self.ai_turn()

    def ai_turn(self):
        for i in range(1, len(self.civs)):
            civ = self.civs[i]
            if not civ["alive"]:
                continue
            civ["gold"] += len(civ["cities"]) * 4 + random.randrange(3)
            civ["science"] += len(civ["cities"])
            if civ["science"] >= civ["tech"] * 12 and civ["tech"] < 3:
                civ["tech"] += 1
            # build units
            if civ["gold"] >= 30 and civ["cities"]:
                kind = random.choice(["warrior", "warrior", "archer"])
                if civ["tech"] >= 3:
                    kind = random.choice(["warrior", "archer", "horseman"])
                city = random.choice(civ["cities"])
                cost = UNIT_TYPES[kind]["cost"]
                if civ["gold"] >= cost:
                    civ["gold"] -= cost
                    x, y = city["x"], city["y"]
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
                        nx, ny = x + dx, y + dy
                        if self.passable(nx, ny) and not self.unit_at(nx, ny):
                            civ["units"].append(dict(x=nx, y=ny, kind=kind, civ=i,
                                                     moves=0))
                            break
            # move units
            for u in list(civ["units"]):
                if u["kind"] == "settler":
                    # find open land and settle
                    best = None
                    best_d = 1e9
                    for y in range(MH):
                        for x in range(MW):
                            if self.passable(x, y) and not self.city_at(x, y)[0] and \
                                    not self.unit_at(x, y):
                                d = abs(x - u["x"]) + abs(y - u["y"])
                                if d < best_d and d > 2:
                                    best_d = d
                                    best = (x, y)
                    if best and best_d <= 6:
                        u["x"], u["y"] = best
                        civ["units"].remove(u)
                        civ["cities"].append(dict(x=best[0], y=best[1], hp=20,
                                                  capital=False, name="Outpost"))
                    continue
                # seek enemy cities
                target = None
                best_d = 1e9
                for j, other in enumerate(self.civs):
                    if j == i or not other["alive"]:
                        continue
                    for c in other["cities"]:
                        d = abs(c["x"] - u["x"]) + abs(c["y"] - u["y"])
                        if d < best_d:
                            best_d = d
                            target = c
                if target is None:
                    continue
                if best_d <= 1:
                    self.attack_city(u, target, self.civ_of(target))
                elif best_d <= 8:
                    path = self.bfs(u["x"], u["y"], target["x"], target["y"], 1)
                    if path and len(path) > 1:
                        nx, ny = path[1]
                        other_u = self.unit_at(nx, ny)
                        if other_u and other_u["civ"] != i:
                            self.battle(u, other_u)
                        elif not other_u:
                            u["x"], u["y"] = nx, ny
        self.check_alive()
        if self.over:
            return
        self.turn += 1
        self.phase = "player"
        for civ in self.civs:
            if not civ["alive"]:
                continue
            civ["gold"] += len(civ["cities"]) * 3 + random.randrange(3)
            civ["science"] += len(civ["cities"])
            if civ["science"] >= civ["tech"] * 12 and civ["tech"] < 3:
                civ["tech"] += 1
            for u in civ["units"]:
                u["moves"] = UNIT_TYPES[u["kind"]]["moves"]
        if self.turn > TURN_LIMIT:
            self.check_alive()
            if not self.over:
                self.over = True
                self.show_menu("TIME UP!", ["Play Again", "Main Menu"],
                               "Survive to turn 45 — score by cities")
        self.update_buttons()

    def civ_of(self, city):
        for civ in self.civs:
            if city in civ["cities"]:
                return civ
        return self.civs[0]

    def check_alive(self):
        for civ in self.civs:
            if not civ["cities"]:
                civ["alive"] = False
                civ["units"].clear()
        alive = [c for c in self.civs if c["alive"]]
        if len(alive) <= 1:
            self.over = True
            if alive:
                self.winner = alive[0]
                if alive[0] is self.civs[0]:
                    self.show_menu("VICTORY!", ["Play Again", "Main Menu"],
                                   f"Conquered by turn {self.turn}",
                                   title_color=(120, 255, 150))
                else:
                    self.show_menu("DEFEAT", ["Play Again", "Main Menu"],
                                   f"{alive[0]['name']} conquered the map")

    def update(self, dt):
        self.msg_t = max(0.0, self.msg_t - dt)

    def draw(self, surf):
        surf.fill((18, 20, 34))
        for y in range(MH):
            for x in range(MW):
                t = self.tile(x, y)
                base = TERRAIN_COLORS[t]
                shade = 1 + ((x * 7 + y * 13) % 3) * 0.05
                col = tuple(min(255, int(c * shade)) for c in base)
                pygame.draw.rect(surf, col, (x * TILE, y * TILE, TILE, TILE))
                if t == "f":
                    pygame.draw.circle(surf, (30, 80, 40), (x * TILE + 8, y * TILE + 8), 5)
                elif t == "h":
                    pygame.draw.polygon(surf, (200, 180, 110),
                                        [(x * TILE + 4, y * TILE + 20), (x * TILE + 16, y * TILE + 6),
                                         (x * TILE + 28, y * TILE + 20)])
                elif t == "m":
                    pygame.draw.polygon(surf, (150, 150, 160),
                                        [(x * TILE + 2, y * TILE + 26), (x * TILE + 16, y * TILE + 4),
                                         (x * TILE + 30, y * TILE + 26)])
        for civ in self.civs:
            if not civ["alive"]:
                continue
            for u in civ["units"]:
                spec = UNIT_TYPES[u["kind"]]
                x, y = u["x"] * TILE + 16, u["y"] * TILE + 16
                if u is self.selected:
                    pygame.draw.circle(surf, (255, 255, 255), (x, y), 14, 2)
                pygame.draw.circle(surf, civ["color"], (x, y), 10)
                pygame.draw.circle(surf, (20, 20, 34), (x, y), 4)
                draw_text(surf, {"settler": "⚒", "warrior": "🗡", "archer": "🏹",
                                 "horseman": "🐴"}[u["kind"]], 12, (255, 255, 255),
                          (x, y), align="center")
            for c in civ["cities"]:
                x, y = c["x"] * TILE, c["y"] * TILE
                pygame.draw.rect(surf, civ["color"], (x + 6, y + 6, 20, 20), border_radius=4)
                pygame.draw.rect(surf, (255, 255, 255), (x + 6, y + 6, 20, 20), 2, border_radius=4)
                pygame.draw.rect(surf, (20, 20, 34), (x + 12, y + 12, 8, 8))
                draw_text(surf, c["name"][0].upper(), 12, (255, 255, 255),
                          (x + 16, y + 16), align="center")
        if self.path:
            for i, (x, y) in enumerate(self.path):
                pygame.draw.circle(surf, (255, 208, 74), (x * TILE + 16, y * TILE + 16),
                                   5 if i else 8)
        pygame.draw.rect(surf, (90, 96, 130), (0, 0, BOARD_W, BOARD_H), 2)
        pygame.draw.rect(surf, (24, 28, 52), (PANEL_X, 0, WIDTH - PANEL_X, HEIGHT))
        pygame.draw.rect(surf, (255, 208, 74), (PANEL_X, 0, 2, HEIGHT))
        draw_text(surf, f"TURN {self.turn}/{TURN_LIMIT}", 18, (255, 208, 74),
                  (PANEL_X + 10, 10), bold=True)
        civ0 = self.civs[0]
        draw_text(surf, f"You: {civ0['gold']}g  {civ0['science']} sci", 14,
                  (220, 224, 240), (PANEL_X + 10, 36))
        draw_text(surf, f"Tech {civ0['tech']}/3", 14, (150, 220, 150),
                  (PANEL_X + 10, 56))
        if self.selected:
            u = self.selected
            spec = UNIT_TYPES[u["kind"]]
            draw_text(surf, f"{spec['name']} ({u['civ'] + 1})", 16, (255, 255, 255),
                      (PANEL_X + 10, 96))
            draw_text(surf, f"Str {spec['str']} · Moves {u['moves']}/{spec['moves']}",
                      13, (200, 204, 224), (PANEL_X + 10, 120))
            for b in self.buttons:
                b.draw(surf)
        draw_text(surf, "CITIES", 15, (150, 158, 190), (PANEL_X + 10, 210))
        for i, c in enumerate(civ0["cities"]):
            draw_text(surf, f"{c['name']} ({c['x']},{c['y']})", 13, (220, 224, 240),
                      (PANEL_X + 10, 232 + i * 18))
        for b in self.train_buttons:
            b.draw(surf)
        self.end_btn.draw(surf)
        y = 96
        for i, civ in enumerate(self.civs):
            if not civ["alive"]:
                continue
            draw_text(surf, f"{civ['name']}: {len(civ['cities'])} cities", 13,
                      civ["color"], (PANEL_X + 10, y))
            y += 20
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 18, (255, 208, 74), (WIDTH // 2, HEIGHT - 6),
                      align="center", outline=1)
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/civ.py
    from games.engine import App
    App(Game).run()
