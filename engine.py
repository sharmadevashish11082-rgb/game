"""Shared framework for the Freebuff Arcade games.

Everything here is plain pygame; games import helpers from this module so they
stay small and consistent. Each game subclasses engine.Game and is registered
in games/__init__.py.
"""
from __future__ import annotations

import math
import random

import pygame

WIDTH, HEIGHT = 960, 640
FPS = 60

_FONT_CACHE: dict = {}
_FONT_NAMES = "consolas,dejavusansmono,couriernew,menlo,monospace,arial"


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = pygame.font.SysFont(_FONT_NAMES, size, bold=bold)
        _FONT_CACHE[key] = f
    return f


def draw_text(surf, text, size, color, pos, align="topleft", bold=False,
              outline=0, outline_color=(8, 8, 18), max_width=None):
    f = font(size, bold)
    while max_width and f.size(text)[0] > max_width and size > 9:
        size -= 1
        f = font(size, bold)
    base = f.render(text, True, color)
    rect = base.get_rect(**{align: pos})
    if outline:
        shadow = f.render(text, True, outline_color)
        for dx in (-1, 1):
            for dy in (-1, 1):
                surf.blit(shadow, rect.move(dx * outline, dy * outline))
    surf.blit(base, rect)
    return rect


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def distance(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def angle_to(ax, ay, bx, by):
    return math.atan2(by - ay, bx - ax)


def draw_health_bar(surf, x, y, w, h, ratio, fg=(96, 220, 120), bg=(30, 30, 44),
                    label=None):
    pygame.draw.rect(surf, bg, (x, y, w, h), border_radius=3)
    ratio = clamp(ratio, 0.0, 1.0)
    if ratio > 0:
        pygame.draw.rect(surf, fg, (x, y, int(w * ratio), h), border_radius=3)
    pygame.draw.rect(surf, (10, 10, 18), (x, y, w, h), 1, border_radius=3)
    if label:
        draw_text(surf, label, 13, (255, 255, 255), (x + w // 2, y + h // 2 - 1),
                  align="center")


# --------------------------------------------------------------------------
# Real-world physics helpers.
#
# All games share the same physical model: forces act on velocities and
# velocities act on positions. Constants below are in game units (px/s), but
# several games scale them from SI units so the numbers mean something real:
#
#   PX_PER_M  — 40 px tile ≈ 0.6 m (the platformer scale).
#   G_EARTH   — 9.81 m/s² gravity.
#   AIR_DENS  — 1.225 kg/m³ at sea level (for drag).
# --------------------------------------------------------------------------

G_EARTH = 9.81          # m/s²
AIR_DENS = 1.225        # kg/m³ at sea level
PX_PER_M = 40.0 / 0.6   # pixels per metre at the 0.6 m/tile scale


def sign(v):
    return (v > 0) - (v < 0)


def mps_to_px(v_mps):
    """Metres/second → px/s at the 0.6 m/tile scale."""
    return v_mps * PX_PER_M


def px_to_mps(v_px):
    """px/s → metres/second."""
    return v_px / PX_PER_M


def px_to_kmh(v_px):
    """px/s → km/h at the 0.6 m/tile scale."""
    return px_to_mps(v_px) * 3.6


def apply_drag(v, drag, dt):
    """Exponential drag: v *= exp(-drag * dt). Real fluids do this."""
    return v * math.exp(-drag * dt)


def gravity_accel(v, g, dt, terminal=None):
    """Integrate a constant acceleration (e.g. gravity) toward a terminal
    velocity, the way falling objects actually stop accelerating."""
    v += g * dt
    if terminal is not None:
        if g > 0:
            v = min(v, terminal)
        else:
            v = max(v, -terminal)
    return v


def bounce(v, restitution=0.6):
    """Reflect a velocity component, losing energy per real collisions."""
    return -v * restitution


def elastic_1d(m1, v1, m2, v2):
    """Perfectly elastic 1-D collision — returns the new (v1, v2)."""
    if m1 + m2 == 0:
        return v1, v2
    nv1 = ((m1 - m2) * v1 + 2 * m2 * v2) / (m1 + m2)
    nv2 = ((m2 - m1) * v2 + 2 * m1 * v1) / (m1 + m2)
    return nv1, nv2


def car_dynamics(v, throttle=0.0, brake=0.0, dt=1.0 / 60, power=62000.0,
                 mass=1.0, drag_coef=0.00173, roll=30.0, traction=720.0,
                 brake_force=520.0):
    """Real car acceleration from an engine power curve.

    Drive force is capped at `traction` at low speed (tyres would slip), then
    falls off as P/v, exactly like a real drivetrain. Air drag is quadratic
    (½·ρ·Cd·A·v²) and rolling resistance is roughly constant, so a top speed
    emerges from power vs. drag instead of a hard cap:

        v_top = (P / drag_coef)^(1/3)

    Defaults are tuned so v_top ≈ 330 px/s (a fast race car on the screen
    scale). Returns the new speed.
    """
    if throttle > 0:
        drive = min(power / max(v, 1.0), traction)
        a = (drive - drag_coef * v * abs(v) - roll * sign(v)) / mass
    else:
        a = -(drag_coef * v * abs(v) + roll * sign(v)) / mass
    if brake > 0:
        a -= brake_force * brake / mass
    return v + a * dt


def jump_cut(vy, rising_cut=0.45):
    """Real jump physics: letting go of the jump button mid-rise cuts the
    upward velocity, so short taps make short hops."""
    return vy * rising_cut if vy < 0 else vy


class Timer:
    """Countdown timer measured in seconds."""

    def __init__(self, duration):
        self.duration = duration
        self.t = duration

    def tick(self, dt):
        self.t -= dt

    def reset(self, duration=None):
        self.t = duration if duration is not None else self.duration

    @property
    def done(self):
        return self.t <= 0

    @property
    def frac(self):
        return clamp(self.t / self.duration, 0.0, 1.0) if self.duration else 0.0


class Particles:
    def __init__(self):
        self.items = []

    def burst(self, x, y, color, n=14, speed=150, life=0.6, size=4, up=False):
        for _ in range(n):
            if up:
                a = math.radians(random.uniform(200, 340))
            else:
                a = math.radians(random.uniform(0, 360))
            s = random.uniform(speed * 0.25, speed)
            self.items.append([x, y, math.cos(a) * s, math.sin(a) * s,
                               life, life, random.uniform(size * 0.5, size), color])

    def update(self, dt):
        keep = []
        for p in self.items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.90
            p[3] *= 0.90
            p[4] -= dt
            if p[4] > 0:
                keep.append(p)
        self.items = keep

    def draw(self, surf):
        for x, y, _, _, life, total, size, col in self.items:
            k = max(0.15, life / total)
            c = tuple(int(ch * k) for ch in col)
            pygame.draw.circle(surf, c, (int(x), int(y)), max(1, int(size)))


class Button:
    def __init__(self, rect, label, size=22, color=(54, 62, 96),
                 hover=(255, 196, 74)):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.size = size
        self.color = color
        self.hover_color = hover
        self.hovered = False

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos)):
            return True
        return False

    def draw(self, surf):
        pygame.draw.rect(surf, self.hover_color if self.hovered else self.color,
                         self.rect, border_radius=8)
        pygame.draw.rect(surf, (235, 240, 255), self.rect, 2, border_radius=8)
        draw_text(surf, self.label, self.size, (250, 250, 255), self.rect.center,
                  align="center")


class Menu:
    """Generic pause / game-over overlay with a selectable option list."""

    def __init__(self, title, options, subtitle=None, title_color=(255, 208, 74)):
        self.title = title
        self.options = list(options)
        self.subtitle = subtitle
        self.selected = 0
        self.title_color = title_color

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.selected
        return None

    def draw(self, surf):
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 180))
        surf.blit(veil, (0, 0))
        cy = int(HEIGHT * 0.30)
        draw_text(surf, self.title, 46, self.title_color, (WIDTH // 2, cy),
                  align="center", outline=2)
        if self.subtitle:
            draw_text(surf, self.subtitle, 20, (215, 220, 235), (WIDTH // 2, cy + 48),
                      align="center")
        for i, opt in enumerate(self.options):
            y = cy + 96 + i * 42
            color = (255, 208, 74) if i == self.selected else (225, 228, 240)
            mark = "▶ " if i == self.selected else "   "
            draw_text(surf, mark + opt, 26, color, (WIDTH // 2, y), align="center",
                      outline=1)


class Game:
    name = "Game"
    emoji = "🎮"
    tagline = ""
    controls = "ESC: back to menu"

    def __init__(self, app):
        self.app = app
        self.menu = None

    def on_enter(self):
        pass

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.quit_to_menu()

    def update(self, dt):
        pass

    def draw(self, surf):
        pass

    def held(self, *keys):
        ks = pygame.key.get_pressed()
        return any(ks[k] for k in keys)

    def show_menu(self, title, options, subtitle=None, title_color=(255, 208, 74)):
        self.menu = Menu(title, options, subtitle, title_color)

    def menu_choice(self, event):
        if self.menu is not None:
            choice = self.menu.handle(event)
            if choice is not None:
                self.menu = None
                return choice
        return None


class App:
    def __init__(self, menu_cls):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Freebuff Arcade")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game = None
        self.menu_cls = menu_cls
        self.set_game(menu_cls(self))

    def set_game(self, game):
        self.game = game
        game.app = self
        game.on_enter()

    def quit_to_menu(self):
        if self.menu_cls is not None:
            self.set_game(self.menu_cls(self))
        else:
            self.running = False

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif self.game is not None:
                    self.game.handle_event(event)
            if self.game is not None:
                self.game.update(dt)
                self.game.draw(self.screen)
            pygame.display.flip()
        pygame.quit()
