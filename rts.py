"""Ironclad Command — a bite-size RTS: gather gold, build units, crush the HQ."""
import random

import pygame

try:
    from .engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, Button, clamp
except ImportError:  # allow direct run: python games/rts.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, Button, clamp

UNIT_TYPES = {
    "soldier": dict(name="Soldier", cost=40, hp=60, dmg=9, speed=110, rng=30, color=(220, 120, 90)),
    "archer":  dict(name="Archer",  cost=30, hp=34, dmg=7, speed=95,  rng=130, color=(120, 200, 90)),
}
BASES = {"P": (150, HEIGHT // 2), "E": (WIDTH - 150, HEIGHT // 2)}
MINES = [(400, 160), (560, 160), (400, 480), (560, 480), (WIDTH // 2, HEIGHT // 2)]


class Unit:
    def __init__(self, x, y, kind, side):
        s = UNIT_TYPES[kind]
        self.x, self.y = float(x), float(y)
        self.kind = kind
        self.side = side
        self.hp = s["hp"]
        self.max_hp = s["hp"]
        self.dmg = s["dmg"]
        self.speed = s["speed"]
        self.rng = s["rng"]
        self.target = None
        self.move_to = None
        self.cd = 0.0
        self.flash = 0.0

    def rect(self):
        return pygame.Rect(int(self.x) - 14, int(self.y) - 14, 28, 28)


class Game(Game):
    name = "Ironclad Command"
    emoji = "🏰"
    tagline = "Spend gold, command units, destroy the enemy HQ."
    controls = "Click select · Right-click move · 1 soldier · 2 archer · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.gold = 120
        self.income = 10.0
        self.income_t = 0.0
        self.units = []
        self.selected = None
        self.hq = {"P": 500, "E": 500}
        self.spawn_cd = {"P": 0.0, "E": 0.0}
        self.ai_gold = 90
        self.ai_units = 0
        self.over = False
        self.victory = False
        self.msg = ""
        self.msg_t = 0.0
        self.buttons = [
            Button((12, HEIGHT - 56, 150, 44), "Soldier  [1]  $40", size=15),
            Button((172, HEIGHT - 56, 140, 44), "Archer  [2]  $30", size=15),
        ]
        self.gold_mines = []
        for mx, my in MINES:
            self.gold_mines.append(dict(x=mx, y=my, t=0.0))
        self.spawn_unit("P", "soldier")
        self.spawn_unit("E", "soldier")

    def spawn_unit(self, side, kind):
        bx, by = BASES[side]
        x = bx + random.uniform(-30, 30)
        y = by + random.uniform(-20, 20)
        u = Unit(x, y, kind, side)
        self.units.append(u)
        return u

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if event.pos[1] > HEIGHT - 64:
                    for b in self.buttons:
                        if b.handle(event):
                            self.buy(b.label.split()[0])
                    return
                clicked = None
                for u in self.units:
                    if u.side == "P" and u.rect().collidepoint(event.pos):
                        clicked = u
                        break
                self.selected = clicked
            elif event.button == 3 and self.selected:
                self.selected.move_to = event.pos
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self.buy("Soldier")
            elif event.key == pygame.K_2:
                self.buy("Archer")

    def buy(self, kind):
        if kind not in ("Soldier", "Archer"):
            return
        k = "soldier" if kind == "Soldier" else "archer"
        cost = UNIT_TYPES[k]["cost"]
        if self.gold >= cost:
            self.gold -= cost
            self.spawn_unit("P", k)
            self.msg = f"Trained {UNIT_TYPES[k]['name']}!"
            self.msg_t = 2.0

    def update(self, dt):
        if self.over:
            return
        self.msg_t = max(0.0, self.msg_t - dt)
        self.income_t += dt
        if self.income_t >= 1.0:
            self.income_t -= 1.0
            self.gold += self.income
            self.ai_gold += 8
        for m in self.gold_mines:
            m["t"] += dt
            for u in self.units:
                if abs(u.x - m["x"]) < 40 and abs(u.y - m["y"]) < 40:
                    if u.side == "P":
                        self.gold += 0.5
                    break

        # AI: build units and push
        self.spawn_cd["E"] -= dt
        if self.ai_gold >= 40 and self.spawn_cd["E"] <= 0:
            self.ai_gold -= 40
            self.spawn_cd["E"] = 4.0
            self.spawn_unit("E", "soldier" if random.random() < 0.6 else "archer")

        for u in self.units:
            u.cd -= dt
            u.flash = max(0.0, u.flash - dt)
            # find target
            u.target = None
            best = 1e9
            for o in self.units:
                if o.side == u.side:
                    continue
                d = ((o.x - u.x) ** 2 + (o.y - u.y) ** 2) ** 0.5
                if d < best:
                    best = d
                    u.target = o
            hq_side = "E" if u.side == "P" else "P"
            hx, hy = BASES[hq_side]
            d_hq = ((hx - u.x) ** 2 + (hy - u.y) ** 2) ** 0.5
            if u.target and ((u.target.x - u.x) ** 2 + (u.target.y - u.y) ** 2) ** 0.5 < u.rng:
                # attack
                if u.cd <= 0:
                    u.cd = 0.9
                    u.target.hp -= u.dmg
                    u.target.flash = 0.1
                    if u.target.hp <= 0:
                        if u.target.side == "P":
                            self.ai_gold += 20
                        else:
                            self.gold += 20
                        self.units.remove(u.target)
                        u.target = None
            else:
                if u.move_to and not u.target:
                    tx, ty = u.move_to
                elif u.target:
                    tx, ty = u.target.x, u.target.y
                else:
                    tx, ty = hx, hy
                d = ((tx - u.x) ** 2 + (ty - u.y) ** 2) ** 0.5
                if d > 8:
                    u.x += (tx - u.x) / d * u.speed * dt
                    u.y += (ty - u.y) / d * u.speed * dt
                elif u.move_to:
                    u.move_to = None
            u.x = clamp(u.x, 10, WIDTH - 10)
            u.y = clamp(u.y, 10, HEIGHT - 70)

        # HQ damage from adjacent enemy units
        for side in ("P", "E"):
            hx, hy = BASES[side]
            for u in self.units:
                if u.side != side and abs(u.x - hx) < 34 and abs(u.y - hy) < 34:
                    if u.cd <= 0:
                        u.cd = 0.8
                        self.hq[side] -= u.dmg * 0.7
        if self.hq["P"] <= 0:
            self.over = True
            self.show_menu("HQ DESTROYED — DEFEAT", ["Retry", "Main Menu"])
        elif self.hq["E"] <= 0:
            self.over = True
            self.victory = True
            self.show_menu("ENEMY HQ DESTROYED!", ["Play Again", "Main Menu"],
                           title_color=(120, 255, 150))

    def draw(self, surf):
        surf.fill((38, 54, 34))
        for gx in range(0, WIDTH, 80):
            for gy in range(0, HEIGHT - 70, 80):
                if (gx // 80 + gy // 80) % 2:
                    pygame.draw.rect(surf, (42, 60, 38), (gx, gy, 80, 80))
        for m in self.gold_mines:
            x, y = m["x"], m["y"]
            pygame.draw.circle(surf, (60, 50, 30), (x, y), 18)
            pygame.draw.circle(surf, (255, 208, 74), (x, y), 10)
            pygame.draw.circle(surf, (255, 240, 160), (x, y), 4)
            draw_text(surf, "💰", 16, (255, 255, 255), (x, y), align="center")
        for side in ("P", "E"):
            hx, hy = BASES[side]
            col = (90, 150, 255) if side == "P" else (255, 90, 90)
            pygame.draw.rect(surf, col, (hx - 30, hy - 26, 60, 52), border_radius=8)
            pygame.draw.rect(surf, (30, 34, 50), (hx - 14, hy - 18, 28, 36), border_radius=4)
            draw_health_bar(surf, hx - 32, hy - 38, 64, 8, self.hq[side] / 500, fg=col)
        for u in self.units:
            col = UNIT_TYPES[u.kind]["color"]
            if u.flash > 0:
                col = (255, 255, 255)
            team = (90, 150, 255) if u.side == "P" else (255, 90, 90)
            pygame.draw.circle(surf, team, (int(u.x), int(u.y)), 12)
            pygame.draw.circle(surf, col, (int(u.x), int(u.y)), 8)
            if u is self.selected:
                pygame.draw.circle(surf, (255, 208, 74), (int(u.x), int(u.y)), 16, 2)
            draw_health_bar(surf, int(u.x) - 13, int(u.y) - 24, 26, 4,
                            u.hp / u.max_hp, fg=col)
        if self.selected and self.selected.move_to:
            mx, my = self.selected.move_to
            pygame.draw.circle(surf, (255, 208, 74), (int(mx), int(my)), 6, 2)
        pygame.draw.rect(surf, (16, 18, 34), (0, HEIGHT - 64, WIDTH, 64))
        pygame.draw.rect(surf, (255, 208, 74), (0, HEIGHT - 64, WIDTH, 2))
        draw_text(surf, f"💰 {int(self.gold)}  +{self.income}/s", 22, (255, 208, 74),
                  (14, HEIGHT - 44), bold=True)
        draw_text(surf, f"Units: {len([u for u in self.units if u.side == 'P'])}",
                  15, (220, 224, 240), (14, HEIGHT - 20))
        for b in self.buttons:
            b.draw(surf)
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 16, (255, 255, 255), (WIDTH // 2, HEIGHT - 24),
                      align="center")
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/rts.py
    from games.engine import App
    App(Game).run()
