"""Turn-based RPG — menu-driven battles against escalating waves."""
import random

import pygame

try:
    from .engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT
except ImportError:  # allow direct run: python games/turn_rpg.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT

HERO_TEMPLATES = [
    dict(name="Sir Lance", hp=150, mp=30, atk=16,
         spells=[("Slash", 0, "atk"), ("Fireball", 8, "dmg", 30),
                 ("Heal", 10, "heal", 38)]),
    dict(name="Mystra", hp=95, mp=48, atk=9,
         spells=[("Bolt", 6, "dmg", 24), ("Heal", 12, "heal", 30),
                 ("Shield", 6, "shield", 14)]),
]

ENEMY_TYPES = [("Slime", 26, 6), ("Goblin", 40, 8), ("Orc", 62, 11),
               ("Wraith", 50, 13), ("Dragon", 150, 17)]
FINAL_WAVE = 5


class Game(Game):
    name = "Turn RPG"
    emoji = "⚔️"
    tagline = "Command a party through turn-based battles."
    controls = "↑↓ select · Enter confirm · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.wave = 1
        self.xp = 0
        self.gold = 0
        self.heroes = []
        for t in HERO_TEMPLATES:
            self.heroes.append(dict(name=t["name"], hp=t["hp"], max_hp=t["hp"],
                                    mp=t["mp"], max_mp=t["mp"], atk=t["atk"],
                                    spells=list(t["spells"]), shield=0, defend=False))
        self.log = ["The adventure begins..."]
        self.phase = "setup"
        self.spawn_wave()
        self.sel = 0
        self.over = False
        self.victory = False

    def spawn_wave(self):
        n = min(4, 2 + (self.wave - 1) // 2)
        self.enemies = []
        for i in range(n):
            if self.wave >= FINAL_WAVE:
                t = ENEMY_TYPES[-1]
            else:
                t = ENEMY_TYPES[min(len(ENEMY_TYPES) - 2,
                                    (self.wave - 1) // 2 + (i % 2))]
            name, hp, atk = t
            hp = int(hp * (1 + (self.wave - 1) * 0.25))
            atk = atk + (self.wave - 1) * 2
            self.enemies.append(dict(name=name, hp=hp, max_hp=hp, atk=atk))
        self.hero_idx = 0
        self.phase = "select"
        self.sel = 0
        self.log = [f"Wave {self.wave} — {', '.join(e['name'] for e in self.enemies)}",
                    "Choose an action for each hero."] + self.log[:4]

    def handle_event(self, event):
        super().handle_event(event)
        if self.over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if self.phase == "camp":
            choice = self.menu_choice(event)
            if choice == 0:
                self.wave += 1
                self.spawn_wave()
            elif choice == 1:
                for h in self.heroes:
                    h["hp"] = min(h["max_hp"], h["hp"] + int(h["max_hp"] * 0.6))
                    h["mp"] = min(h["max_mp"], h["mp"] + int(h["max_mp"] * 0.5))
                self.log = ["You rest by the campfire and recover."] + self.log[:4]
            return
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % self.option_count()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % self.option_count()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.pick(self.sel)

    def option_count(self):
        if self.phase != "select":
            return 1
        hero = self.heroes[self.hero_idx]
        return len(hero["spells"]) + 2

    def options(self):
        hero = self.heroes[self.hero_idx]
        opts = [f"{s[0]}" + (f" ({s[1]}mp)" if s[1] else "") for s in hero["spells"]]
        opts.append("Defend")
        opts.append("Skip")
        return opts

    def alive_heroes(self):
        return [h for h in self.heroes if h["hp"] > 0]

    def pick(self, idx):
        hero = self.heroes[self.hero_idx]
        if idx < len(hero["spells"]):
            name, cost, kind = hero["spells"][idx][:3]
            if cost > hero["mp"]:
                self.log = ["Not enough MP!"] + self.log[:4]
                return
            hero["mp"] -= cost
            if kind == "atk":
                dmg = hero["atk"] + random.randrange(-2, 4)
                e = random.choice(self.enemies)
                e["hp"] -= dmg
                self.log = [f"{hero['name']} slashes {e['name']} for {dmg}!"] + self.log[:4]
                self.check_enemy_deaths()
            elif kind == "dmg":
                dmg = hero["spells"][idx][3] + random.randrange(-2, 3)
                e = random.choice(self.enemies)
                e["hp"] -= dmg
                self.log = [f"{hero['name']} blasts {e['name']} for {dmg}!"] + self.log[:4]
                self.check_enemy_deaths()
            elif kind == "heal":
                amt = hero["spells"][idx][3]
                target = min(self.alive_heroes(), key=lambda h: h["hp"])
                target["hp"] = min(target["max_hp"], target["hp"] + amt)
                self.log = [f"{hero['name']} heals {target['name']} for {amt}."] + self.log[:4]
            elif kind == "shield":
                hero["shield"] = hero["spells"][idx][3]
                self.log = [f"{hero['name']} raises a shield ({hero['shield']})."] + self.log[:4]
        elif idx == len(hero["spells"]):
            hero["defend"] = True
            self.log = [f"{hero['name']} takes a defensive stance."] + self.log[:4]
        self.next_hero()

    def check_enemy_deaths(self):
        dead = [e for e in self.enemies if e["hp"] <= 0]
        for e in dead:
            self.enemies.remove(e)
            self.gold += 8 + self.wave * 3
            self.xp += 12 + self.wave * 4
            self.log = [f"{e['name']} is defeated! +{12 + self.wave * 4} XP"] + self.log[:4]

    def next_hero(self):
        while True:
            self.hero_idx += 1
            if self.hero_idx >= len(self.heroes):
                self.enemy_turn()
                return
            if self.heroes[self.hero_idx]["hp"] > 0:
                self.sel = 0
                return

    def enemy_turn(self):
        self.phase = "enemy"
        for e in self.enemies:
            targets = self.alive_heroes()
            if not targets:
                break
            t = random.choice(targets)
            dmg = max(1, e["atk"] + random.randrange(-3, 4) - random.randrange(0, 3))
            if t["defend"]:
                dmg //= 2
            if t["shield"]:
                absorbed = min(t["shield"], dmg)
                t["shield"] -= absorbed
                dmg -= absorbed
            t["hp"] = max(0, t["hp"] - dmg)
            self.log = [f"{e['name']} hits {t['name']} for {dmg}."] + self.log[:4]
        for h in self.heroes:
            h["defend"] = False
        if not self.alive_heroes():
            self.over = True
            self.show_menu("DEFEAT", ["Retry", "Main Menu"],
                           f"Reached wave {self.wave} · {self.gold} gold")
            return
        if not self.enemies:
            self.wave_cleared()
        else:
            self.hero_idx = 0
            self.phase = "select"
            self.sel = 0

    def wave_cleared(self):
        self.xp += 40 + self.wave * 10
        self.gold += 20 + self.wave * 5
        self.log = [f"Wave {self.wave} cleared! +{40 + self.wave * 10} XP"] + self.log[:4]
        if self.wave >= FINAL_WAVE:
            self.victory = True
            self.over = True
            self.show_menu("VICTORY!", ["Play Again", "Main Menu"],
                           f"The realm is saved · {self.xp} XP · {self.gold} gold",
                           title_color=(120, 255, 150))
        else:
            self.phase = "camp"
            self.show_menu(f"WAVE {self.wave} CLEARED",
                           ["Next Wave", "Rest at Camp"],
                           f"XP {self.xp} · Gold {self.gold}",
                           title_color=(120, 255, 150))

    def update(self, dt):
        if self.phase == "enemy":
            pass  # enemy turn resolves instantly during pick()

    def draw(self, surf):
        surf.fill((22, 20, 38))
        pygame.draw.rect(surf, (34, 30, 54), (0, 0, WIDTH // 2, HEIGHT))
        draw_text(surf, "YOUR PARTY", 18, (150, 158, 190), (WIDTH // 4, 12), align="center")
        for i, h in enumerate(self.heroes):
            y = 60 + i * 150
            pygame.draw.rect(surf, (30, 36, 62), (30, y, WIDTH // 2 - 60, 130),
                             border_radius=10)
            draw_text(surf, h["name"], 22, (255, 208, 74), (46, y + 10), bold=True)
            draw_health_bar(surf, 46, y + 42, 320, 18, h["hp"] / h["max_hp"], fg=(90, 220, 120))
            draw_text(surf, f"HP {h['hp']}/{h['max_hp']}", 13, (255, 255, 255), (46, y + 64))
            draw_health_bar(surf, 46, y + 82, 320, 14, h["mp"] / h["max_mp"], fg=(100, 160, 255))
            draw_text(surf, f"MP {h['mp']}/{h['max_mp']}", 12, (220, 224, 240), (46, y + 100))
            if h["shield"]:
                draw_text(surf, f"🛡 {h['shield']}", 16, (140, 230, 255), (WIDTH // 2 - 46, y + 10),
                          align="topright")
        draw_text(surf, "ENEMIES", 18, (150, 158, 190), (WIDTH * 3 // 4, 12), align="center")
        for i, e in enumerate(self.enemies):
            y = 60 + i * 92
            pygame.draw.rect(surf, (48, 26, 34), (WIDTH // 2 + 30, y, WIDTH // 2 - 60, 76),
                             border_radius=10)
            draw_text(surf, e["name"], 20, (255, 130, 130), (WIDTH // 2 + 46, y + 8), bold=True)
            draw_health_bar(surf, WIDTH // 2 + 46, y + 36, 280, 16, e["hp"] / e["max_hp"],
                            fg=(255, 110, 110))
            draw_text(surf, f"{e['hp']}", 13, (255, 255, 255), (WIDTH // 2 + 46, y + 54))
        if self.phase == "select":
            hero = self.heroes[self.hero_idx]
            bar = pygame.Rect(0, HEIGHT - 130, WIDTH, 130)
            pygame.draw.rect(surf, (16, 18, 34), bar)
            pygame.draw.rect(surf, (255, 208, 74), bar, 2)
            draw_text(surf, f"{hero['name']}'s action:", 20, (255, 208, 74),
                      (bar.x + 16, bar.y + 8), bold=True)
            for i, opt in enumerate(self.options()):
                x = 16 + (i % 4) * 235
                y = bar.y + 44 + (i // 4) * 40
                sel = i == self.sel
                pygame.draw.rect(surf, (255, 208, 74) if sel else (40, 46, 78),
                                 (x, y, 220, 34), border_radius=6)
                draw_text(surf, opt, 17, (20, 20, 34) if sel else (230, 233, 248),
                          (x + 10, y + 17), align="midleft")
        if self.phase == "camp":
            self.menu.draw(surf)
        if self.over:
            self.menu.draw(surf)
        for i, line in enumerate(self.log[:4]):
            draw_text(surf, line, 14, (200, 204, 224), (16, HEIGHT - 168 - i * 18))
        draw_text(surf, f"Wave {self.wave}/{FINAL_WAVE}   XP {self.xp}   Gold {self.gold}",
                  15, (255, 255, 255), (WIDTH // 2, 40), align="center")


if __name__ == "__main__":
    # Allow running this file directly: python games/turn_rpg.py
    from games.engine import App
    App(Game).run()
