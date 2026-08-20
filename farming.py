"""Harvest Hills — a farming sim: till, plant, water, harvest, sell."""
import random

import pygame

try:
    from .engine import Game, draw_text, WIDTH, HEIGHT, Button, clamp
except ImportError:  # allow direct run: python games/farming.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, WIDTH, HEIGHT, Button, clamp

GW, GH = 12, 8
TILE = 60
OX = (WIDTH - GW * TILE) // 2
OY = 96
GOAL = 500

# Real crop facts, compressed to the game's day scale. Each crop has the
# seasons it can actually be planted in (wheat is a spring/autumn cereal,
# tomato and corn need warm summer soil) and the market pays more in winter
# when local supply dries up.
CROPS = {
    "wheat":  dict(name="Wheat",  seed=10, sell=22, days=3, seasons=(0, 2),
                    color=(230, 210, 120)),
    "tomato": dict(name="Tomato", seed=15, sell=34, days=4, seasons=(1,),
                    color=(230, 90, 80)),
    "corn":   dict(name="Corn",   seed=20, sell=48, days=5, seasons=(1,),
                    color=(255, 200, 90)),
}
SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
SEASON_DAYS = 4
PRICE_MULT = [1.0, 1.0, 0.9, 1.3]      # winter shortages raise market prices
WEATHERS = ["sunny", "rain", "drought"]
WEATHER_ICON = {"sunny": "☀️", "rain": "🌧️", "drought": "🥵"}


class Game(Game):
    name = "Harvest Hills"
    emoji = "🌾"
    tagline = "Tend your crops through the seasons."
    controls = "1-6 tool · Click field · 7 sleep · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.money = 50
        self.day = 1
        self.season = 0
        self.weather = "sunny"
        self.energy = 100
        self.t = 0.0
        self.tool = "hoe"
        self.plots = [[None for _ in range(GW)] for _ in range(GH)]
        self.msg = ""
        self.msg_t = 0.0
        self.over = False
        self.victory = False
        self.buttons = []
        for i, (k, name) in enumerate([("hoe", "Hoe"), ("plant", "Plant"),
                                       ("water", "Water"), ("harvest", "Harvest"),
                                       ("sell", "Sell All")]):
            self.buttons.append(Button((OX + i * 150, 14, 140, 40),
                                       f"{i + 1} {name}", size=14))
        self.buttons.append(Button((WIDTH - 130, 14, 120, 40), "7 Sleep", size=14))

    def season_name(self):
        return SEASONS[self.season]

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
            keys = {pygame.K_1: "hoe", pygame.K_2: "plant", pygame.K_3: "water",
                    pygame.K_4: "harvest", pygame.K_5: "sell", pygame.K_6: "plant",
                    pygame.K_7: "sleep"}
            if event.key in keys:
                self.tool = keys[event.key]
            if event.key == pygame.K_7:
                self.sleep()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in self.buttons:
                if b.handle(event):
                    label = b.label.split()[1] if len(b.label.split()) > 1 else b.label
                    if b.label.startswith("7"):
                        self.sleep()
                    else:
                        self.tool = {"Hoe": "hoe", "Plant": "plant", "Water": "water",
                                     "Harvest": "harvest", "Sell": "sell"}.get(label, "hoe")
                    return
            cell = self.cell_at(event.pos)
            if cell:
                self.use_tool(*cell)

    def cell_at(self, pos):
        x, y = pos
        cx, cy = (x - OX) // TILE, (y - OY) // TILE
        if 0 <= cx < GW and 0 <= cy < GH:
            return cx, cy
        return None

    def grow_mult(self):
        """Seasonal growth × weather: rain helps, drought and winter hurt."""
        if self.season in (0, 1):
            m = 1.4
        elif self.season == 2:
            m = 1.0
        else:
            m = 0.4
        if self.weather == "rain":
            m *= 1.2
        elif self.weather == "drought":
            m *= 0.6
        return m

    def use_tool(self, x, y):
        if self.energy < 3:
            self.msg = "Too tired! Sleep to recover energy."
            self.msg_t = 2.0
            return
        plot = self.plots[y][x]
        if self.tool == "hoe":
            if plot is None:
                self.plots[y][x] = dict(crop=None, tilled=True, watered=False,
                                        growth=0.0, kind=None)
                self.energy -= 3
        elif self.tool == "plant":
            if plot and plot["tilled"] and plot["crop"] is None:
                if plot["kind"] is None:
                    # pick the cheapest seed you can afford that is in season
                    for k, spec in sorted(CROPS.items(),
                                          key=lambda kv: kv[1]["seed"]):
                        if self.season not in spec["seasons"]:
                            continue
                        if self.money >= spec["seed"]:
                            plot["crop"] = k
                            plot["kind"] = k
                            self.money -= spec["seed"]
                            self.energy -= 3
                            return
                    if not any(self.season in CROPS[k]["seasons"] and
                               self.money >= CROPS[k]["seed"] for k in CROPS):
                        in_season = [CROPS[k]["name"] for k in CROPS
                                     if self.season in CROPS[k]["seasons"]]
                        self.msg = (f"Nothing in season! Plant in: "
                                    f"{', '.join(in_season) or 'none'}.")
                    else:
                        self.msg = "No seeds affordable!"
                    self.msg_t = 2.0
        elif self.tool == "water":
            if plot and plot["crop"]:
                plot["watered"] = True
                self.energy -= 2
        elif self.tool == "harvest":
            if plot and plot["crop"] and plot["growth"] >= 1.0:
                crop = CROPS[plot["crop"]]
                price = int(crop["sell"] * PRICE_MULT[self.season])
                self.money += price
                plot["crop"] = None
                plot["kind"] = None
                plot["growth"] = 0.0
                plot["tilled"] = False     # real soil: crops deplete the plot
                self.energy -= 3
                self.msg = f"Sold {crop['name']} for ${price}!"
                self.msg_t = 2.0
        elif self.tool == "sell":
            count = 0
            total = 0
            for row in self.plots:
                for p in row:
                    if p and p["crop"] and p["growth"] >= 1.0:
                        price = int(CROPS[p["crop"]]["sell"] * PRICE_MULT[self.season])
                        self.money += price
                        total += price
                        count += 1
                        p["crop"] = None
                        p["kind"] = None
                        p["growth"] = 0.0
                        p["tilled"] = False
            if count:
                self.msg = f"Sold {count} crops for ${total}!"
                self.msg_t = 2.0

    def sleep(self):
        self.day += 1
        self.energy = 100
        old = self.season
        if self.day % SEASON_DAYS == 1:
            self.season = (self.season + 1) % 4
            self.msg = f"Welcome to {self.season_name()}!"
        else:
            self.msg = f"Day {self.day} — {self.season_name()}"
        # overnight weather forecast for the new day
        self.weather = random.choice(WEATHERS)
        if self.weather == "rain":
            self.msg += " Rain overnight — fields watered."
        elif self.weather == "drought":
            self.msg += " Drought — crops will struggle."
        else:
            self.msg += " Clear skies."
        self.msg_t = 3.0
        mult = self.grow_mult()
        raining = self.weather == "rain"
        for row in self.plots:
            for p in row:
                if p and p["crop"]:
                    if p["watered"] or raining:
                        p["growth"] += mult / CROPS[p["crop"]]["days"]
                        p["watered"] = False
                    else:
                        p["growth"] += mult * 0.4 / CROPS[p["crop"]]["days"]
                if p:
                    p["growth"] = min(1.0, p["growth"])
        if self.money >= GOAL:
            self.over = True
            self.victory = True
            self.show_menu("FARM MAGNATE!", ["Play Again", "Main Menu"],
                           f"Reached ${GOAL} by day {self.day}",
                           title_color=(120, 255, 150))

    def update(self, dt):
        self.msg_t = max(0.0, self.msg_t - dt)
        if self.money <= -50:
            self.over = True
            self.show_menu("BANKRUPT!", ["Retry", "Main Menu"], f"Day {self.day}")

    def draw(self, surf):
        surf.fill((58, 90, 48))
        pygame.draw.rect(surf, (46, 74, 40), (0, 56, WIDTH, 36))
        for y in range(GH):
            for x in range(GW):
                rect = pygame.Rect(OX + x * TILE, OY + y * TILE, TILE, TILE)
                plot = self.plots[y][x]
                if plot and plot["tilled"]:
                    pygame.draw.rect(surf, (96, 70, 44), rect)
                    if plot["watered"]:
                        pygame.draw.rect(surf, (70, 90, 110), rect, 3)
                else:
                    pygame.draw.rect(surf, (64, 104, 54), rect)
                pygame.draw.rect(surf, (40, 62, 34), rect, 1)
                if plot and plot["crop"]:
                    crop = CROPS[plot["crop"]]
                    g = plot["growth"]
                    cx, cy = rect.centerx, rect.centery
                    if g < 0.35:
                        pygame.draw.line(surf, (90, 200, 80), (cx, cy + 10), (cx, cy - 6), 2)
                        pygame.draw.circle(surf, (90, 200, 80), (cx, cy - 6), 3)
                    elif g < 0.8:
                        for k in (-4, 4):
                            pygame.draw.line(surf, crop["color"], (cx + k, cy + 12),
                                             (cx + k, cy - 8), 3)
                        pygame.draw.line(surf, (90, 200, 80), (cx, cy + 12), (cx, cy - 6), 3)
                    else:
                        for k in (-5, 0, 5):
                            pygame.draw.line(surf, crop["color"], (cx + k, cy + 12),
                                             (cx + k, cy - 12), 3)
                            pygame.draw.circle(surf, crop["color"], (cx + k, cy - 12), 3)
        # farmhouse
        pygame.draw.rect(surf, (190, 110, 80), (OX - 10, 4, 70, 52), border_radius=4)
        pygame.draw.polygon(surf, (150, 70, 50), [(OX - 18, 4), (OX + 25, -6), (OX + 68, 4)])
        draw_text(surf, f"DAY {self.day}", 16, (255, 255, 255), (OX - 10, 30))
        for b in self.buttons:
            b.draw(surf)
        draw_text(surf, f"💰 ${int(self.money)}", 24, (255, 208, 74), (14, 6), bold=True)
        draw_text(surf, f"Goal ${GOAL}", 14, (220, 224, 240), (14, 34))
        draw_text(surf, f"⚡ {self.energy}", 18, (150, 220, 150), (WIDTH - 14, 6),
                  align="topright")
        draw_text(surf, f"{self.season_name()} {WEATHER_ICON[self.weather]}"
                   f" · day {self.day % SEASON_DAYS or SEASON_DAYS}/{SEASON_DAYS} ·"
                   f" prices x{PRICE_MULT[self.season]:.1f}", 15, (200, 204, 224),
                  (WIDTH - 14, 30), align="topright")
        draw_text(surf, f"Tool: {self.tool.title()}", 16, (255, 208, 74),
                  (WIDTH // 2, 66), align="center")
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 18, (255, 255, 255), (WIDTH // 2, 88),
                      align="center")
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/farming.py
    from games.engine import App
    App(Game).run()
