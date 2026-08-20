"""Highway Rush — a vertical lane-dodging racer."""
import random

import pygame

try:
    from .engine import Game, draw_text, WIDTH, HEIGHT, clamp, car_dynamics
except ImportError:  # allow direct run: python games/lane_racer.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, WIDTH, HEIGHT, clamp, car_dynamics

# Screen-scale conversions so the HUD reads real-ish values: the car tops out
# near 620 px/s, which we display as ~260 km/h, and 8.6 px ≈ 1 m of road.
KMH_PER_PX = 0.42
METRES_PER_PX = 1 / 8.6

LANES = 3
ROAD_W = 320
ROAD_X = (WIDTH - ROAD_W) // 2
LANE_X = [ROAD_X + 60, ROAD_X + 160, ROAD_X + 260]
CAR_COLORS = [(220, 90, 90), (120, 200, 255), (255, 200, 90), (160, 120, 255),
              (120, 220, 140), (240, 150, 90)]


class Obstacle:
    def __init__(self, lane, y, speed, color):
        self.lane = lane
        self.y = y
        self.speed = speed
        self.color = color

    def update(self, dt):
        self.y += self.speed * dt

    def rect(self):
        return pygame.Rect(LANE_X[self.lane] - 20, int(self.y) - 30, 40, 60)


class Game(Game):
    name = "Highway Rush"
    emoji = "🏁"
    tagline = "Dodge the traffic. Don't slow down."
    controls = "←→ move lanes · ↑ speed up · ↓ slow · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.lane = 1
        self.score = 0
        self.dist = 0.0
        self.speed = 260.0
        self.obstacles = []
        self.spawn_t = 1.1
        self.over = False
        self.t = 0.0
        self.shake = 0.0

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
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.lane = max(0, self.lane - 1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.lane = min(2, self.lane + 1)

    def update(self, dt):
        self.t += dt
        if self.over:
            return
        # Real drivetrain: throttle follows a power curve, braking is strong,
        # coasting loses speed to aero drag and rolling resistance. Top speed
        # (~620 px/s) emerges from power vs. drag, like a real engine.
        throttle = 1.0 if self.held(pygame.K_UP, pygame.K_w) else 0.0
        brake = 1.0 if self.held(pygame.K_DOWN, pygame.K_s) else 0.0
        self.speed = car_dynamics(self.speed, throttle, brake, dt,
                                  power=62000.0, mass=1.0, drag_coef=0.00026,
                                  roll=40.0, traction=900.0, brake_force=700.0)
        self.speed = clamp(self.speed, 60, 640)
        self.dist += self.speed * dt
        self.score = int(self.dist * METRES_PER_PX)
        self.spawn_t -= dt
        if self.spawn_t <= 0:
            self.spawn_t = max(0.35, 1.1 - self.dist / 40000)
            if random.random() < 0.35:
                lane = random.choice([l for l in range(3) if l != self.lane])
            else:
                lane = random.randrange(3)
            self.obstacles.append(Obstacle(lane, -70, self.speed * random.uniform(0.55, 0.85),
                                           random.choice(CAR_COLORS)))
        for o in self.obstacles:
            o.update(dt)
        self.obstacles = [o for o in self.obstacles if o.y < HEIGHT + 60]
        player_rect = pygame.Rect(LANE_X[self.lane] - 20, HEIGHT - 110, 40, 60)
        for o in self.obstacles:
            if player_rect.colliderect(o.rect()):
                self.over = True
                self.shake = 0.4
                self.show_menu("CRASHED!", ["Retry", "Main Menu"],
                               f"Score: {self.score} · {int(self.dist * METRES_PER_PX)} m")

    def draw(self, surf):
        surf.fill((26, 66, 34))
        for k in range(0, HEIGHT, 60):
            off = (k + self.dist * 0.6) % 120
            for i in range(4):
                pygame.draw.circle(surf, (40, 92, 44), (20 + i * 300, int((k + off) % HEIGHT)), 16)
                pygame.draw.circle(surf, (40, 92, 44), (WIDTH - 20 - i * 300, int((k + off) % HEIGHT)), 16)
        pygame.draw.rect(surf, (46, 46, 52), (ROAD_X, 0, ROAD_W, HEIGHT))
        for x in (ROAD_X + 100, ROAD_X + 220):
            dash = self.dist * 1.0
            for k in range(-40, HEIGHT + 40, 70):
                y = (k + dash) % (HEIGHT + 40) - 20
                pygame.draw.rect(surf, (240, 240, 245), (x, int(y), 5, 36))
        pygame.draw.rect(surf, (255, 255, 255), (ROAD_X, 0, 6, HEIGHT))
        pygame.draw.rect(surf, (255, 255, 255), (ROAD_X + ROAD_W - 6, 0, 6, HEIGHT))
        for o in self.obstacles:
            rect = o.rect()
            pygame.draw.rect(surf, o.color, rect, border_radius=10)
            pygame.draw.rect(surf, (255, 240, 160), (rect.x + 4, rect.y + 4, 8, 6), border_radius=2)
            pygame.draw.rect(surf, (255, 120, 120), (rect.x + 28, rect.y + 4, 8, 6), border_radius=2)
            pygame.draw.rect(surf, (30, 30, 40), (rect.x + 4, rect.bottom - 8, 10, 4))
            pygame.draw.rect(surf, (30, 30, 40), (rect.x + 26, rect.bottom - 8, 10, 4))
        pr = pygame.Rect(LANE_X[self.lane] - 20, HEIGHT - 110, 40, 60)
        pygame.draw.rect(surf, (90, 150, 255), pr, border_radius=10)
        pygame.draw.rect(surf, (220, 235, 255), (pr.x + 8, pr.y + 6, 24, 14), border_radius=4)
        pygame.draw.rect(surf, (255, 240, 160), (pr.x + 4, pr.y + 30, 10, 8), border_radius=2)
        pygame.draw.rect(surf, (255, 120, 120), (pr.x + 26, pr.y + 30, 10, 8), border_radius=2)
        draw_text(surf, f"SCORE {self.score}", 26, (255, 255, 255), (14, 10), bold=True)
        draw_text(surf, f"{int(self.speed * KMH_PER_PX)} km/h", 18, (255, 208, 74), (14, 44))
        draw_text(surf, f"{int(self.dist * METRES_PER_PX)} m", 16, (170, 176, 205), (14, 72))
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/lane_racer.py
    from games.engine import App
    App(Game).run()
