"""Mega Park Tycoon — build attractions, keep customers happy, make it big."""
import random

import pygame

try:
    from .engine import Game, draw_text, WIDTH, HEIGHT, Button
except ImportError:  # allow direct run: python games/tycoon.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, WIDTH, HEIGHT, Button

GW, GH = 12, 9
TILE = 62
OX = (WIDTH - GW * TILE) // 2
OY = 76
GOAL = 1500

ATTRACTIONS = {
    "hotdog":  dict(name="Hot Dog Stand", cost=50,  income=3,  upkeep=1,  color=(255, 170, 90),  icon="🌭"),
    "carousel": dict(name="Carousel",     cost=160, income=8,  upkeep=3,  color=(255, 120, 200), icon="🎠"),
    "coaster":  dict(name="Roller Coaster", cost=420, income=20, upkeep=9, color=(140, 200, 255), icon="🎢"),
    "bench":    dict(name="Bench",        cost=15,  income=0,  upkeep=0,  color=(150, 220, 130), icon="🪑"),
}
ORDER = ["hotdog", "carousel", "coaster", "bench"]


class Customer:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.target = None
        self.speed = random.uniform(34, 60)
        self.hue = random.choice([(230, 210, 120), (200, 140, 220), (140, 200, 255),
                                  (255, 160, 140), (160, 230, 180)])

    def update(self, dt, game):
        if self.target is None:
            options = [a for a in game.attractions if a["kind"] != "bench"]
            if options:
                self.target = random.choice(options)
            else:
                self.target = random.choice(game.attractions)
        a = self.target
        dx, dy = a["x"] - self.x, a["y"] - self.y
        d = (dx * dx + dy * dy) ** 0.5
        if d < 8:
            if a["kind"] != "bench":
                # Demand: every visit pushes this ride's price up; neglect
                # lets demand (and income) decay back to the baseline.
                a["demand"] = min(2.0, a["demand"] + 0.12)
                a["income_acc"] += (a["income"] * game.happiness_mult()
                                     * a["demand"])
            self.target = None
            return True
        self.x += dx / d * self.speed * dt
        self.y += dy / d * self.speed * dt
        return False


class Game(Game):
    name = "Mega Park Tycoon"
    emoji = "💰"
    tagline = "Build the park. Hit the target. Don't go broke."
    controls = "1-4 pick attraction · Click place · 5 bulldoze · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.money = 200
        self.attractions = []
        self.customers = []
        self.happiness = 70
        self.t = 0.0
        self.inflation = 0.0      # build costs creep up over time
        self.upkeep_t = 0.0
        self.spawn_t = 2.0
        self.sel = "hotdog"
        self.over = False
        self.victory = False
        self.msg = ""
        self.msg_t = 0.0
        self.buttons = []
        for i, k in enumerate(ORDER):
            a = ATTRACTIONS[k]
            self.buttons.append(Button((OX + i * 175, 20, 165, 48),
                                       f"{i + 1} {a['name']} ${a['cost']}", size=14))
        self.buttons.append(Button((WIDTH - 90, 20, 80, 48), "5 Bulldoze", size=14))

    def cell_at(self, pos):
        x, y = pos
        cx, cy = (x - OX) // TILE, (y - OY) // TILE
        if 0 <= cx < GW and 0 <= cy < GH:
            return cx, cy
        return None

    def happiness_mult(self):
        return 0.5 + self.happiness / 100.0

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
                self.sel = "hotdog"
            elif event.key == pygame.K_2:
                self.sel = "carousel"
            elif event.key == pygame.K_3:
                self.sel = "coaster"
            elif event.key == pygame.K_4:
                self.sel = "bench"
            elif event.key == pygame.K_5:
                self.sel = "bulldoze"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.handle(event):
                    self.sel = ["hotdog", "carousel", "coaster", "bench", "bulldoze"][self.buttons.index(b)]
                    return
            cell = self.cell_at(event.pos)
            if cell:
                if self.sel == "bulldoze":
                    for a in list(self.attractions):
                        if a["cell"] == cell:
                            self.attractions.remove(a)
                            self.money += ATTRACTIONS[a["kind"]]["cost"] // 2
                else:
                    if any(a["cell"] == cell for a in self.attractions):
                        return
                    spec = ATTRACTIONS[self.sel]
                    cost = int(spec["cost"] * (1 + self.inflation))
                    if self.money >= cost:
                        self.money -= cost
                        self.attractions.append(dict(cell=cell, kind=self.sel,
                                                     x=OX + cell[0] * TILE + TILE // 2,
                                                     y=OY + cell[1] * TILE + TILE // 2,
                                                     income_acc=0.0, demand=1.0))

    def update(self, dt):
        if self.over:
            return
        self.t += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        self.upkeep_t += dt
        if self.upkeep_t >= 8.0:
            self.upkeep_t -= 8.0
            # Wear: heavily-used rides cost more to maintain — real physics.
            upkeep = sum(int(ATTRACTIONS[a["kind"]]["upkeep"]
                             * (1 + (a["demand"] - 1) * 0.8))
                         for a in self.attractions)
            self.money -= upkeep
            if upkeep:
                self.msg = f"Upkeep paid: ${upkeep}"
                self.msg_t = 2.0
        # Inflation: materials and wages drift upward as the day goes on.
        self.inflation = min(0.6, self.inflation + 0.0007 * dt)
        for a in self.attractions:
            a["demand"] = max(1.0, a["demand"] - 0.004 * dt)
        self.spawn_t -= dt
        if self.spawn_t <= 0 and len(self.customers) < 14:
            self.spawn_t = random.uniform(1.0, 2.5)
            self.customers.append(Customer(random.uniform(40, WIDTH - 40), 12))
        for c in list(self.customers):
            if c.update(dt, self):
                self.customers.remove(c)
        for a in self.attractions:
            self.money += a["income_acc"]
            a["income_acc"] = 0.0
        benches = sum(1 for a in self.attractions if a["kind"] == "bench")
        attractions = [a for a in self.attractions if a["kind"] != "bench"]
        target = 100
        if attractions:
            target = min(100, 55 + benches * 6 + len(attractions) * 4)
        self.happiness += (target - self.happiness) * 0.02
        if self.money <= -50:
            self.over = True
            self.show_menu("BANKRUPT!", ["Retry", "Main Menu"],
                           f"You went broke with ${self.money}")
        elif self.money >= GOAL:
            self.over = True
            self.victory = True
            self.show_menu("PARK EMPIRE!", ["Play Again", "Main Menu"],
                           f"Reached ${GOAL} with {len(self.customers)} guests",
                           title_color=(120, 255, 150))

    def draw(self, surf):
        surf.fill((30, 50, 30))
        for y in range(GH):
            for x in range(GW):
                col = (56, 96, 48) if (x + y) % 2 == 0 else (60, 102, 52)
                pygame.draw.rect(surf, col, (OX + x * TILE, OY + y * TILE, TILE, TILE))
        for a in self.attractions:
            spec = ATTRACTIONS[a["kind"]]
            cx, cy = a["x"], a["y"]
            pygame.draw.rect(surf, spec["color"], (cx - 22, cy - 22, 44, 44), border_radius=8)
            pygame.draw.rect(surf, (30, 34, 50), (cx - 22, cy - 22, 44, 44), 2, border_radius=8)
            draw_text(surf, spec["icon"], 22, (255, 255, 255), (cx, cy - 4), align="center")
            if spec["income"]:
                draw_text(surf, f"+${spec['income']}", 11, (255, 255, 255),
                          (cx, cy + 14), align="center")
        for c in self.customers:
            pygame.draw.circle(surf, c.hue, (int(c.x), int(c.y)), 7)
            pygame.draw.circle(surf, (255, 235, 200), (int(c.x), int(c.y) - 8), 5)
        pygame.draw.rect(surf, (16, 18, 34), (0, 0, WIDTH, 70))
        pygame.draw.rect(surf, (255, 208, 74), (0, 70, WIDTH, 2))
        draw_text(surf, f"MONEY ${int(self.money)}", 24, (255, 208, 74), (14, 12),
                  bold=True)
        draw_text(surf, f"Target ${GOAL}", 15, (220, 224, 240), (14, 44))
        draw_text(surf, f"Guests {len(self.customers)}", 15, (200, 204, 224),
                  (WIDTH // 2, 44), align="center")
        draw_text(surf, f"Happiness {int(self.happiness)}% · prices +{int(self.inflation * 100)}%",
                  15, (150, 220, 150), (WIDTH - 14, 8), align="topright")
        for b in self.buttons:
            b.draw(surf)
        sel_spec = ATTRACTIONS.get(self.sel)
        if sel_spec:
            draw_text(surf, f"Selected: {sel_spec['name']} (${sel_spec['cost']})", 14,
                      (255, 208, 74), (WIDTH // 2, HEIGHT - 10), align="center")
        else:
            draw_text(surf, "Bulldoze mode — click an attraction to remove it", 14,
                      (255, 150, 90), (WIDTH // 2, HEIGHT - 10), align="center")
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 15, (255, 255, 255), (WIDTH // 2, 100),
                      align="center")
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/tycoon.py
    from games.engine import App
    App(Game).run()
