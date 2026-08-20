"""Turbo Circuit — top-down circuit racing against AI opponents."""
import math
import random

import pygame

try:
    from .engine import (Game, draw_text, WIDTH, HEIGHT, clamp, distance, lerp,
                         car_dynamics)
except ImportError:  # allow direct run: python games/topdown_racing.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import (Game, draw_text, WIDTH, HEIGHT, clamp, distance, lerp,
                              car_dynamics)

TRACK = [(120, 130), (400, 100), (760, 115), (880, 270), (835, 430),
         (590, 545), (300, 560), (120, 470), (70, 300)]
TRACK_W = 130
LAPS = 3
AI_COLORS = [(255, 90, 90), (90, 220, 120), (255, 190, 80)]
PLAYER_COLOR = (90, 150, 255)


def seg_len(a, b):
    return distance(*a, *b)


def closest_point(px, py, a, b):
    abx, aby = b[0] - a[0], b[1] - a[1]
    denom = abx * abx + aby * aby
    t = ((px - a[0]) * abx + (py - a[1]) * aby) / denom if denom else 0.0
    t = clamp(t, 0.0, 1.0)
    qx, qy = a[0] + abx * t, a[1] + aby * t
    return qx, qy, t, distance(px, py, qx, qy)


def nearest_track(px, py):
    best, best_i, best_t = 1e18, 0, 0.0
    for i in range(len(TRACK) - 1):
        qx, qy, t, d = closest_point(px, py, TRACK[i], TRACK[i + 1])
        if d < best:
            best, best_i, best_t = d, i, t
    return best_i, best_t, best


class Car:
    def __init__(self, x, y, angle, color, player=False):
        self.x, self.y, self.angle = x, y, angle
        self.speed = 0.0
        self.color = color
        self.player = player
        self.lap = 1
        self.finished = False
        self.finish_pos = 99
        self.target_i = 2
        self.wobble = random.uniform(0, 6)

    def update(self, dt, accel, steer):
        # Real car: the engine makes force from a power curve (P/v), air drag
        # grows with v², rolling resistance is constant, so a top speed
        # emerges instead of being hard-capped. Tuned so the player's car
        # tops out near 330 px/s — roughly 280 km/h on the HUD scale.
        throttle = max(0.0, accel)
        brake = max(0.0, -accel)
        self.speed = car_dynamics(self.speed, throttle, brake, dt,
                                  power=62000.0, mass=1.0, drag_coef=0.00173,
                                  roll=30.0, traction=720.0, brake_force=520.0)
        _, _, off = nearest_track(self.x, self.y)
        if off > TRACK_W / 2:            # grass: heavy drag, no grip
            self.speed *= (1 - 2.2 * dt)
        self.speed = clamp(self.speed, -80, 345)
        # Grip-limited cornering: real cars understeer hard at speed.
        v_frac = clamp(abs(self.speed) / 345, 0.0, 1.0)
        turn = steer * 3.1 * (1.0 - 0.55 * v_frac) * dt * max(0.25, v_frac)
        self.angle += turn
        self.x += math.cos(self.angle) * self.speed * dt
        self.y += math.sin(self.angle) * self.speed * dt
        if off > TRACK_W / 2 + 36:      # hard wall: push back onto track
            i, t, _ = nearest_track(self.x, self.y)
            qx, qy, _, _ = closest_point(self.x, self.y, TRACK[i], TRACK[i + 1])
            self.x = lerp(self.x, qx, 0.5)
            self.y = lerp(self.y, qy, 0.5)

    def ai_steer(self, dt):
        tx, ty = TRACK[self.target_i]
        if distance(self.x, self.y, tx, ty) < 70:
            self.target_i = (self.target_i + 1) % (len(TRACK) - 1)
            tx, ty = TRACK[self.target_i]
        want = math.atan2(ty - self.y, tx - self.x)
        diff = (want - self.angle + math.pi) % (2 * math.pi) - math.pi
        steer = clamp(diff * 1.6, -1, 1)
        accel = 0.9 if abs(diff) < 1.4 else -0.3
        self.wobble += dt * 3
        steer += math.sin(self.wobble) * 0.05
        return accel, steer

    def rank_key(self):
        return (self.lap, self.speed, self.finished)


class Game(Game):
    name = "Turbo Circuit"
    emoji = "🏎️"
    tagline = "Three laps. Beat the pack."
    controls = "↑ accel · ↓ brake · ←→ steer · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.sprites = {}
        self.reset()

    def reset(self):
        start = TRACK[0]
        nxt = TRACK[1]
        ang = math.atan2(nxt[1] - start[1], nxt[0] - start[0])
        self.cars = []
        for i, col in enumerate([PLAYER_COLOR] + AI_COLORS):
            back = -60 * (i + 1)
            self.cars.append(Car(start[0] - math.cos(ang) * back,
                                 start[1] - math.sin(ang) * back, ang, col,
                                 player=(i == 0)))
        self.race_over = False
        self.result_t = 0.0
        self.msg = ""
        self.msg_t = 0.0

    def handle_event(self, event):
        super().handle_event(event)
        if self.race_over:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()

    def update(self, dt):
        if self.race_over:
            return
        self.msg_t = max(0.0, self.msg_t - dt)
        for car in self.cars:
            if car.player:
                accel = (1 if self.held(pygame.K_UP, pygame.K_w) else
                         -1 if self.held(pygame.K_DOWN, pygame.K_s) else 0)
                steer = ((1 if self.held(pygame.K_RIGHT, pygame.K_d) else 0) -
                         (1 if self.held(pygame.K_LEFT, pygame.K_a) else 0))
            else:
                accel, steer = car.ai_steer(dt)
            car.update(dt, accel, steer)
            self.track_lap(car)
        if self.cars[0].finished and self.result_t <= 0:
            self.result_t = 1.0
        if self.cars[0].finished:
            self.result_t -= dt
            if self.result_t <= 0:
                self.race_over = True
                order = sorted([c for c in self.cars if c.finished],
                               key=lambda c: c.finish_pos)
                pos = self.cars[0].finish_pos
                self.show_menu("RACE COMPLETE", ["Race Again", "Main Menu"],
                               f"You finished P{pos} of {len(self.cars)}")

    def track_lap(self, car):
        i, t, _ = nearest_track(car.x, car.y)
        if not hasattr(car, "last_i"):
            car.last_i = i
        # crossed the start line forward?
        if car.last_i >= len(TRACK) - 2 and i <= 1 and car.speed > 40:
            if car.lap >= LAPS:
                if not car.finished:
                    car.finished = True
                    car.finish_pos = 1 + sum(1 for c in self.cars
                                             if c.finished and c is not car)
                    if car.player:
                        self.msg = f"P{car.finish_pos}!"
            else:
                car.lap += 1
                if car.player:
                    self.msg = f"Lap {car.lap}/{LAPS}"
                    self.msg_t = 1.5
        car.last_i = i

    def car_sprite(self, color):
        key = tuple(color)
        if key not in self.sprites:
            s = pygame.Surface((34, 24), pygame.SRCALPHA)
            pygame.draw.rect(s, color, (0, 0, 34, 24), border_radius=9)
            pygame.draw.rect(s, (235, 240, 255), (21, 4, 9, 7), border_radius=3)
            pygame.draw.rect(s, (235, 240, 255), (21, 13, 9, 7), border_radius=3)
            pygame.draw.rect(s, (255, 240, 160), (1, 4, 4, 5), border_radius=1)
            pygame.draw.rect(s, (255, 120, 120), (1, 15, 4, 5), border_radius=1)
            self.sprites[key] = s
        return self.sprites[key]

    def draw(self, surf):
        surf.fill((36, 84, 44))
        pygame.draw.rect(surf, (30, 72, 38), (0, 0, WIDTH, 26))
        pygame.draw.rect(surf, (30, 72, 38), (0, HEIGHT - 30, WIDTH, 30))
        pygame.draw.rect(surf, (30, 72, 38), (0, 0, 30, HEIGHT))
        pygame.draw.rect(surf, (30, 72, 38), (WIDTH - 30, 0, 30, HEIGHT))
        for i in range(len(TRACK) - 1):
            pygame.draw.line(surf, (66, 66, 74), TRACK[i], TRACK[i + 1], TRACK_W)
            pygame.draw.line(surf, (240, 240, 245), TRACK[i], TRACK[i + 1], 3)
        for i in range(len(TRACK) - 1):
            a, b = TRACK[i], TRACK[i + 1]
            n = max(2, int(seg_len(a, b) / 34))
            for k in range(1, n):
                t = k / n
                x = lerp(a[0], b[0], t)
                y = lerp(a[1], b[1], t)
                if int(i * 10 + k) % 2 == 0:
                    pygame.draw.circle(surf, (200, 200, 60), (int(x), int(y)), 3)
        # start line
        a, b = TRACK[0], TRACK[1]
        ax, ay = b[0] - a[0], b[1] - a[1]
        L = (ax * ax + ay * ay) ** 0.5
        px_, py_ = -ay / L * 12, ax / L * 12
        for k in range(8):
            c = (255, 255, 255) if k % 2 == 0 else (20, 20, 22)
            pygame.draw.polygon(surf, c, [(a[0] + px_ * (k / 8), a[1] + py_ * (k / 8)),
                                          (a[0] - px_ * (k / 8), a[1] - py_ * (k / 8)),
                                          (a[0] - px_ * ((k + 1) / 8), a[1] - py_ * ((k + 1) / 8)),
                                          (a[0] + px_ * ((k + 1) / 8), a[1] + py_ * ((k + 1) / 8))])
        order = sorted(self.cars, key=lambda c: (-c.lap, c.speed), reverse=True)
        for i, car in enumerate(order):
            sprite = self.car_sprite(car.color)
            rot = pygame.transform.rotate(sprite, -math.degrees(car.angle))
            rect = rot.get_rect(center=(int(car.x), int(car.y)))
            surf.blit(rot, rect)
            if car.player:
                pygame.draw.circle(surf, (255, 255, 255), (int(car.x), int(car.y)), 18, 2)

        car = self.cars[0]
        draw_text(surf, f"LAP {car.lap}/{LAPS}", 24, (255, 255, 255), (WIDTH // 2, 8),
                  align="center", outline=1)
        draw_text(surf, f"{int(car.speed * 0.85)} km/h", 18, (255, 208, 74), (14, 8))
        pos = 1 + sum(1 for c in self.cars if (c.lap, c.speed) > (car.lap, car.speed))
        draw_text(surf, f"P{pos}/{len(self.cars)}", 24, (255, 208, 74),
                  (WIDTH - 14, 8), align="topright", bold=True)
        if self.msg and self.msg_t > 0:
            draw_text(surf, self.msg, 30, (255, 208, 74), (WIDTH // 2, 90),
                      align="center", outline=2)
        if self.race_over:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/topdown_racing.py
    from games.engine import App
    App(Game).run()
