"""Street Brawl — a beat-'em-up: clear waves of thugs, then the boss."""
import random

import pygame

try:
    from .engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                         clamp)
except ImportError:  # allow direct run: python games/beatemup.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, draw_health_bar, Particles, WIDTH, HEIGHT,
                              clamp)

GROUND_Y = HEIGHT - 96
WAVE_COUNT = [4, 5, 7, 1]  # boss on wave 4


class Fighter:
    def __init__(self, x, color, hp, dmg, name=""):
        self.x, self.y = float(x), float(GROUND_Y)
        self.vx, self.vy = 0.0, 0.0
        self.facing = -1
        self.hp = hp
        self.max_hp = hp
        self.dmg = dmg
        self.color = color
        self.name = name
        self.hitstun = 0.0
        self.attack = None
        self.cd = 0.0
        self.on_ground = True
        self.flash = 0.0

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)
        if self.hitstun > 0:
            self.hitstun -= dt
            self.vx *= (1 - 8 * dt)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 1600 * dt
        if self.y >= GROUND_Y:
            self.y = GROUND_Y
            self.vy = 0.0
            self.on_ground = True
        self.x = clamp(self.x, 30, WIDTH - 30)
        if self.attack:
            self.attack["t"] += dt
            if self.attack["t"] > 0.3:
                self.attack = None
        self.cd = max(0.0, self.cd - dt)

    def try_hit(self, other):
        if not self.attack:
            return False
        spec = self.attack
        if spec["active"] and abs(other.x - self.x) < spec["range"] and \
                (other.x - self.x) * self.facing >= -10 and abs(other.y - self.y) < 80:
            if other.hitstun <= 0:
                other.hitstun = 0.3
                other.hp -= self.dmg * spec["mult"]
                other.vx = self.facing * 140
                if spec["mult"] >= 1.5:
                    other.vy = min(other.vy, -90)    # heavy hits launch
                other.flash = 0.12
                self.vx -= self.facing * 30          # recoil pushes the hitter
                self.attack["active"] = False
                return True
        return False

    def punch(self, mult=1.0):
        if self.cd > 0 or self.hitstun > 0:
            return False
        self.attack = dict(range=58, mult=mult, active=True, t=0.0)
        self.cd = 0.28
        return True


class Game(Game):
    name = "Street Brawl"
    emoji = "⚔️"
    tagline = "One vs the whole block. Chain your hits."
    controls = "A/D move · W jump · J punch · K kick · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.particles = Particles()
        self.reset()

    def reset(self):
        self.player = Fighter(160, (90, 150, 255), 120, 10, "You")
        self.enemies = []
        self.wave = 0
        self.spawn_q = 0
        self.spawn_t = 0.0
        self.combo = 0
        self.combo_t = 0.0
        self.score = 0
        self.banner = "WAVE 1"
        self.banner_t = 2.0
        self.over = False
        self.victory = False
        self.start_wave()

    def start_wave(self):
        self.wave += 1
        self.spawn_q = WAVE_COUNT[min(self.wave - 1, len(WAVE_COUNT) - 1)]
        self.spawn_t = 0.0
        self.banner = f"WAVE {self.wave}" + (" — BOSS!" if self.wave == len(WAVE_COUNT) else "")
        self.banner_t = 2.0

    def spawn_enemy(self):
        from_left = self.wave > 2 and random.random() < 0.3
        x = 40 if from_left else WIDTH - 40
        if self.wave == len(WAVE_COUNT):
            hp, dmg = 260, 14
            color, name = (140, 70, 200), "BRUISER"
        else:
            hp, dmg = 36 + self.wave * 10, 6 + self.wave
            color, name = (255, 90, 90), "THUG"
        e = Fighter(x, color, hp, dmg, name)
        e.facing = -1 if x > WIDTH / 2 else 1
        self.enemies.append(e)

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
                if self.player.punch(1.0):
                    self.combo += 1
                    self.combo_t = 2.0
                    self.score += 10
            elif event.key == pygame.K_k:
                if self.player.punch(1.8):
                    self.combo += 1
                    self.combo_t = 2.0
                    self.score += 15

    def update(self, dt):
        self.particles.update(dt)
        if self.over:
            return
        self.banner_t = max(0.0, self.banner_t - dt)
        self.combo_t = max(0.0, self.combo_t - dt)
        if self.combo_t <= 0:
            self.combo = 0
        p = self.player
        if self.held(pygame.K_a):
            p.vx += -460 * dt
            p.facing = -1
        if self.held(pygame.K_d):
            p.vx += 460 * dt
            p.facing = 1
        if self.held(pygame.K_w) and p.on_ground:
            p.vy = -540
            p.on_ground = False

        if self.spawn_q > 0:
            self.spawn_t -= dt
            if self.spawn_t <= 0:
                self.spawn_q -= 1
                self.spawn_t = 0.7
                self.spawn_enemy()

        for e in list(self.enemies):
            e.update(dt)
            dist = abs(e.x - p.x)
            if e.hitstun <= 0:
                if dist > 60:
                    e.vx += (120 if p.x > e.x else -120) * dt
                    e.facing = 1 if p.x > e.x else -1
                elif random.random() < dt * 1.4:
                    e.punch(1.0)
            e.try_hit(p)

        # player hits enemies
        p.update(dt)
        hit_any = False
        for e in list(self.enemies):
            if p.try_hit(e):
                hit_any = True
                self.particles.burst(e.x, e.y, (255, 200, 120), n=8, speed=110)
        if hit_any:
            pass  # combo already counted at keypress
        self.enemies = [e for e in self.enemies if e.hp > 0]
        if p.hp <= 0:
            self.over = True
            self.show_menu("KNOCKED OUT", ["Retry", "Main Menu"],
                           f"Wave {self.wave} · Score {self.score}")
            return
        if not self.enemies and self.spawn_q <= 0:
            if self.wave >= len(WAVE_COUNT):
                self.over = True
                self.victory = True
                self.show_menu("STREET CHAMPION!", ["Play Again", "Main Menu"],
                               f"Score: {self.score}", title_color=(120, 255, 150))
            else:
                self.start_wave()

    def draw(self, surf):
        surf.fill((24, 22, 34))
        for i in range(6):
            pygame.draw.rect(surf, (38 + i * 3, 30 + i * 2, 52 + i * 3), (0, i * 100, WIDTH, 100))
        for i in range(9):
            pygame.draw.rect(surf, (52 + (i % 3) * 6, 42, 60), (i * 110, 120, 60, 130))
            pygame.draw.polygon(surf, (60, 48, 70),
                                [(i * 110 - 8, 120), (i * 110 + 38, 80), (i * 110 + 84, 120)])
        pygame.draw.rect(surf, (80, 76, 68), (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        pygame.draw.rect(surf, (100, 94, 86), (0, GROUND_Y, WIDTH, 10))
        self.draw_fighter(surf, self.player)
        for e in self.enemies:
            self.draw_fighter(surf, e)
        self.particles.draw(surf)
        draw_health_bar(surf, 20, 14, 300, 20, self.player.hp / self.player.max_hp,
                        fg=(90, 160, 255))
        draw_text(surf, f"WAVE {self.wave}/{len(WAVE_COUNT)}", 20, (255, 208, 74),
                  (WIDTH - 14, 12), align="topright")
        draw_text(surf, f"SCORE {self.score}", 16, (200, 204, 224), (WIDTH - 14, 38),
                  align="topright")
        if self.combo >= 3:
            draw_text(surf, f"{self.combo} HIT COMBO!", 26, (255, 200, 80),
                      (WIDTH // 2, 60), align="center", outline=2)
        if self.banner and self.banner_t > 0:
            draw_text(surf, self.banner, 40, (255, 208, 74), (WIDTH // 2, HEIGHT // 2 - 60),
                      align="center", outline=3)
        if self.menu:
            self.menu.draw(surf)

    def draw_fighter(self, surf, f):
        x, y = int(f.x), int(f.y)
        col = (255, 255, 255) if f.flash > 0 else f.color
        pygame.draw.line(surf, (40, 44, 60), (x, y), (x - 9 * f.facing, y - 22), 6)
        pygame.draw.line(surf, (40, 44, 60), (x, y), (x + 9 * f.facing, y - 22), 6)
        big = f.name == "BRUISER"
        pygame.draw.rect(surf, col, (x - (20 if big else 15), y - (70 if big else 56),
                                     40 if big else 30, 46 if big else 36), border_radius=8)
        pygame.draw.circle(surf, (235, 210, 180), (x, y - (76 if big else 64)), 13 if big else 11)
        pygame.draw.circle(surf, (30, 30, 40), (x + 5 * f.facing, y - (78 if big else 67)), 3)
        if f.attack and f.attack["active"]:
            reach = f.attack["range"]
            pygame.draw.line(surf, (255, 220, 120), (x + 14 * f.facing, y - 44),
                             (x + f.facing * reach, y - 46), 9)
        else:
            pygame.draw.line(surf, col, (x + 12 * f.facing, y - 46),
                             (x + 20 * f.facing, y - 28), 7)
        if f.hp < f.max_hp:
            draw_health_bar(surf, x - 20, y - (86 if big else 72), 40, 5,
                            f.hp / f.max_hp, fg=(220, 90, 90))
        if f.name:
            draw_text(surf, f.name, 12, (220, 224, 240), (x, y - (98 if big else 84)),
                      align="center")


if __name__ == "__main__":
    # Allow running this file directly: python games/beatemup.py
    from games.engine import App
    App(Game).run()
