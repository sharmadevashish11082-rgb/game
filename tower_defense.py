"""Tower Defense — place towers, stop the waves from reaching the exit."""
import math
import random

import pygame

try:
    from .engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, clamp, lerp
except ImportError:  # allow direct run: python games/tower_defense.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, clamp, lerp

TILE = 40
GRID_W, GRID_H = 24, 14
BAR_H = 80
GRID_X, GRID_Y = 0, BAR_H

PATH = [(0, 10), (6, 10), (6, 3), (15, 3), (15, 12), (23, 12)]

TOWER_TYPES = {
    "gun":    dict(name="Gun",    cost=50,  dmg=10, rate=0.35, rng=115, color=(120, 200, 255)),
    "cannon": dict(name="Cannon", cost=110, dmg=30, rate=0.90, rng=100, color=(255, 150, 60)),
    "frost":  dict(name="Frost",  cost=75,  dmg=4,  rate=0.50, rng=108, color=(140, 240, 255),
                   slow=0.5, slow_t=2.0),
}
TOWER_ORDER = ["gun", "cannon", "frost"]

MAX_WAVE = 12
START_MONEY = 150
START_LIVES = 20


def px(cell):
    return (cell[0] * TILE + TILE // 2, cell[1] * TILE + TILE // 2 + BAR_H)


class Enemy:
    def __init__(self, hp, speed, kind):
        self.hp = hp
        self.max_hp = hp
        self.speed = speed
        self.kind = kind
        self.seg = 0
        self.prog = 0.0
        self.slow_t = 0.0
        self.dead = False

    def pos(self):
        p1, p2 = PATH[self.seg], PATH[self.seg + 1]
        return lerp(px(p1)[0], px(p2)[0], self.prog), lerp(px(p1)[1], px(p2)[1], self.prog)

    def update(self, dt):
        if self.dead:
            return
        if self.slow_t > 0:
            self.slow_t -= dt
            mult = 0.5
        else:
            mult = 1.0
        p1, p2 = PATH[self.seg], PATH[self.seg + 1]
        seg_len = TILE * (abs(p2[0] - p1[0]) + abs(p2[1] - p1[1]))
        self.prog += self.speed * mult * dt / seg_len
        if self.prog >= 1.0:
            self.prog -= 1.0
            self.seg += 1
            if self.seg >= len(PATH) - 1:
                self.dead = True


class Game(Game):
    name = "Tower Defense"
    emoji = "🏰"
    tagline = "Build towers and defend the path."
    controls = "1/2/3 pick tower · Click place/upgrade · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.money = START_MONEY
        self.lives = START_LIVES
        self.wave = 0
        self.state = "build"          # build / spawning / done
        self.spawn_q = []
        self.spawn_t = 0.0
        self.inter_t = 2.0
        self.towers = []
        self.enemies = []
        self.projectiles = []
        self.over = False
        self.victory = False
        self.sel_type = "gun"
        self.hover = None
        self.selected = None

    def is_path(self, x, y):
        for i in range(len(PATH) - 1):
            p1, p2 = PATH[i], PATH[i + 1]
            if p1[0] == p2[0]:
                if x == p1[0] and min(p1[1], p2[1]) <= y <= max(p1[1], p2[1]):
                    return True
            elif p1[1] == p2[1]:
                if y == p1[1] and min(p1[0], p2[0]) <= x <= max(p1[0], p2[0]):
                    return True
        return False

    def tile_at(self, pos):
        x, y = pos
        tx, ty = (x - GRID_X) // TILE, (y - GRID_Y) // TILE
        if 0 <= tx < GRID_W and 0 <= ty < GRID_H:
            return tx, ty
        return None

    def build_wave(self, n):
        count = 4 + n * 2
        q = []
        for i in range(count):
            r = random.random()
            if n >= 5 and r < 0.18:
                kind = "tank"
            elif n >= 2 and r < 0.45:
                kind = "fast"
            else:
                kind = "normal"
            q.append((kind, i * max(0.35, 1.2 - n * 0.05)))
        random.shuffle(q[:3]) if len(q) > 3 else None
        return q

    def start_wave(self):
        if self.state == "spawning" or self.over:
            return
        self.wave += 1
        self.spawn_q = self.build_wave(self.wave)
        self.state = "spawning"
        self.spawn_t = 0.0

    def spawn_enemy(self, kind):
        base = 26 * (1.25 ** (self.wave - 1))
        if kind == "fast":
            hp, spd = int(base * 0.6), 120
        elif kind == "tank":
            hp, spd = int(base * 3.2), 42
        else:
            hp, spd = int(base), 80
        self.enemies.append(Enemy(hp, spd, kind))

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
            if event.key == pygame.K_1:
                self.sel_type = "gun"
            elif event.key == pygame.K_2:
                self.sel_type = "cannon"
            elif event.key == pygame.K_3:
                self.sel_type = "frost"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_wave()
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.tile_at(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.hover = self.tile_at(event.pos)
            if event.button == 1 and self.hover:
                self.click(self.hover)
            elif event.button == 3 and self.hover:
                self.upgrade(self.hover)

    def click(self, cell):
        for t in self.towers:
            if t["cell"] == cell:
                self.selected = t if self.selected != t else None
                return
        if self.money < TOWER_TYPES[self.sel_type]["cost"]:
            return
        if self.is_path(*cell):
            return
        if any(t["cell"] == cell for t in self.towers):
            return
        self.towers.append(dict(cell=cell, kind=self.sel_type, lvl=1,
                                cd=0.0, target=None))
        self.money -= TOWER_TYPES[self.sel_type]["cost"]
        self.selected = self.towers[-1]

    def upgrade(self, cell):
        for t in self.towers:
            if t["cell"] == cell:
                cost = TOWER_TYPES[t["kind"]]["cost"] // 2
                if t["lvl"] < 4 and self.money >= cost:
                    self.money -= cost
                    t["lvl"] += 1
                self.selected = t
                return

    def update(self, dt):
        if self.over:
            return
        if self.state == "build":
            self.inter_t -= dt
            if self.inter_t <= 0:
                self.start_wave()
        elif self.state == "spawning":
            if self.spawn_q:
                kind, delay = self.spawn_q[0]
                self.spawn_t -= dt
                if self.spawn_t <= 0:
                    self.spawn_q.pop(0)
                    self.spawn_enemy(kind)
                    self.spawn_t = delay
            else:
                self.state = "done"

        for e in self.enemies:
            e.update(dt)
        self.enemies = [e for e in self.enemies if not e.dead]

        for t in self.towers:
            t["cd"] -= dt
            spec = TOWER_TYPES[t["kind"]]
            if t["cd"] <= 0:
                target = None
                best_prog = -1
                ex, ey = px(t["cell"])
                rng = spec["rng"] * (1 + (t["lvl"] - 1) * 0.15)
                for e in self.enemies:
                    ex2, ey2 = e.pos()
                    if (ex2 - ex) ** 2 + (ey2 - ey) ** 2 <= rng * rng:
                        prog = e.seg * 100 + e.prog
                        if prog > best_prog:
                            best_prog = prog
                            target = e
                if target:
                    t["cd"] = spec["rate"] / (1 + (t["lvl"] - 1) * 0.25)
                    dmg = spec["dmg"] * (1 + (t["lvl"] - 1) * 0.5)
                    self.projectiles.append(dict(x=ex, y=ey, target=target,
                                                 dmg=dmg, kind=t["kind"]))

        for pr in list(self.projectiles):
            if pr["target"].dead:
                self.projectiles.remove(pr)
                continue
            tx, ty = pr["target"].pos()
            dx, dy = tx - pr["x"], ty - pr["y"]
            d = (dx * dx + dy * dy) ** 0.5
            if d < 12:
                self.projectiles.remove(pr)
                self.hit(pr)
            else:
                # Real muzzle velocities: rifle rounds are fast, shells are
                # lobbed slow and heavy, frost bolts in between.
                spd = {"gun": 560, "cannon": 300, "frost": 420}[pr["kind"]] * dt
                pr["x"] += dx / d * spd
                pr["y"] += dy / d * spd

        reached = [e for e in self.enemies if e.seg >= len(PATH) - 1]
        for e in reached:
            self.enemies.remove(e)
            self.lives -= 1
            if self.lives <= 0:
                self.lives = 0
                self.over = True
                self.show_menu("GAME OVER", ["Retry", "Main Menu"],
                               f"Reached wave {self.wave}")
        if self.state == "done" and not self.enemies:
            bonus = 30 + self.wave * 8
            self.money += bonus
            if self.wave >= MAX_WAVE:
                self.over = True
                self.victory = True
                self.show_menu("VICTORY!", ["Play Again", "Main Menu"],
                               f"All {MAX_WAVE} waves defended!",
                               title_color=(120, 255, 150))
            else:
                self.state = "build"
                self.inter_t = 2.5

    def hit(self, pr):
        spec = TOWER_TYPES[pr["kind"]]
        e = pr["target"]
        e.hp -= pr["dmg"]
        if pr["kind"] == "cannon":
            ex, ey = e.pos()
            for other in self.enemies:
                ox, oy = other.pos()
                if (ox - ex) ** 2 + (oy - ey) ** 2 <= 34 * 34:
                    other.hp -= pr["dmg"] * 0.5
        elif pr["kind"] == "frost" and "slow" in spec:
            e.slow_t = spec["slow_t"]
        if e.hp <= 0:
            e.dead = True
            self.money += 8 + self.wave * 2

    def draw(self, surf):
        surf.fill((18, 22, 40))
        pygame.draw.rect(surf, (16, 18, 34), (0, 0, WIDTH, BAR_H))
        pygame.draw.rect(surf, (255, 208, 74), (0, BAR_H - 2, WIDTH, 2))
        for y in range(GRID_H):
            for x in range(GRID_W):
                if (x + y) % 2:
                    pygame.draw.rect(surf, (38, 52, 34), (GRID_X + x * TILE, GRID_Y + y * TILE, TILE, TILE))
                else:
                    pygame.draw.rect(surf, (42, 56, 38), (GRID_X + x * TILE, GRID_Y + y * TILE, TILE, TILE))
        for i in range(len(PATH) - 1):
            pygame.draw.line(surf, (120, 96, 60), px(PATH[i]), px(PATH[i + 1]), 30)
            pygame.draw.line(surf, (150, 124, 82), px(PATH[i]), px(PATH[i + 1]), 8)
        for t in self.towers:
            spec = TOWER_TYPES[t["kind"]]
            cx, cy = px(t["cell"])
            rng = spec["rng"] * (1 + (t["lvl"] - 1) * 0.15)
            if t is self.selected or t["cell"] == self.hover:
                pygame.draw.circle(surf, (255, 255, 255, 60), (cx, cy), int(rng), 1)
            col = spec["color"]
            if t["kind"] == "gun":
                pygame.draw.circle(surf, col, (cx, cy), 13)
                pygame.draw.circle(surf, (30, 40, 70), (cx, cy), 6)
            elif t["kind"] == "cannon":
                pygame.draw.rect(surf, col, (cx - 12, cy - 12, 24, 24), border_radius=4)
                pygame.draw.circle(surf, (30, 40, 70), (cx, cy), 6)
            else:
                pygame.draw.circle(surf, col, (cx, cy), 13)
                for k in range(3):
                    a = k * 2.09
                    pygame.draw.line(surf, (30, 40, 70), (cx, cy),
                                     (cx + 10 * math.cos(a), cy + 10 * math.sin(a)), 3)
            for i in range(t["lvl"] - 1):
                pygame.draw.circle(surf, (255, 208, 74), (cx - 12 + i * 7, cy - 17), 2)
        for e in self.enemies:
            ex, ey = e.pos()
            col = {"normal": (230, 80, 90), "fast": (240, 200, 80), "tank": (140, 80, 200)}[e.kind]
            pygame.draw.circle(surf, col, (int(ex), int(ey)), 11)
            draw_health_bar(surf, int(ex) - 13, int(ey) - 22, 26, 4, e.hp / e.max_hp, fg=col)
        for pr in self.projectiles:
            col = TOWER_TYPES[pr["kind"]]["color"]
            pygame.draw.circle(surf, col, (int(pr["x"]), int(pr["y"])), 4)
            pygame.draw.circle(surf, (255, 255, 255), (int(pr["x"]), int(pr["y"])), 2)

        draw_text(surf, f"💎 {self.money}", 24, (255, 208, 74), (14, 10), bold=True)
        draw_text(surf, f"❤ {self.lives}", 22, (255, 120, 120), (160, 12))
        wave_label = f"Wave {self.wave}/{MAX_WAVE}"
        if self.state == "build":
            wave_label += " — press Space or wait..."
        draw_text(surf, wave_label, 22, (255, 255, 255), (WIDTH - 14, 10), align="topright")
        for i, key in enumerate(TOWER_ORDER):
            spec = TOWER_TYPES[key]
            x = 250 + i * 150
            sel = self.sel_type == key
            pygame.draw.rect(surf, (255, 208, 74) if sel else (40, 46, 78),
                             (x, 8, 140, 56), border_radius=8)
            draw_text(surf, f"{i + 1} {spec['name']} ${spec['cost']}", 16,
                      (20, 20, 34) if sel else (235, 238, 250), (x + 10, 16))
            draw_text(surf, f"{spec['dmg']}dmg · rng {spec['rng']}", 12,
                      (20, 20, 34) if sel else (170, 176, 205), (x + 10, 40))
        if self.selected:
            t = self.selected
            spec = TOWER_TYPES[t["kind"]]
            draw_text(surf, f"{spec['name']} Lv{t['lvl']} — Right-click to upgrade "
                            f"(${spec['cost'] // 2})", 14, (200, 204, 224),
                      (14, 60))
        if self.over:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/tower_defense.py
    from games.engine import App
    App(Game).run()
