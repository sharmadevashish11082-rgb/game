"""Freebuff Arcade — 21 playable games in one Python app.

Run `python play_games.py` from the project root. Each game in this package
subclasses engine.Game and is listed in GAME_CLASSES, which the launcher shows
in its grid menu.
"""
from . import (pacman, rpg, turn_rpg, tower_defense, bullet_hell, galaga,
               topdown_racing, lane_racer, zombie_survival, platform_shooter,
               fighting, beatemup, dungeon, sokoban, chess, card_battle,
               civ, rts, tycoon, farming, survival)

GAME_CLASSES = [
    pacman.Game,          # 👻 Pac-Man style maze chase
    rpg.Game,             # 🧙 Top-down quest RPG
    turn_rpg.Game,        # ⚔️ Turn-based RPG battles
    tower_defense.Game,   # 🏰 Tower defense
    bullet_hell.Game,     # 🚀 Bullet-hell shooter
    galaga.Game,          # 🛸 Galaga-style arcade shooter
    topdown_racing.Game,  # 🏎️ Top-down circuit racing
    lane_racer.Game,      # 🏁 Lane-dodging highway racer
    zombie_survival.Game, # 🧟 Top-down zombie wave survival
    platform_shooter.Game,  # 🔫 Side-scrolling run & gun
    fighting.Game,        # 🥷 1v1 fighting game
    beatemup.Game,        # ⚔️ Beat-'em-up brawler
    dungeon.Game,         # 🗺️ Roguelike dungeon crawler
    sokoban.Game,         # 🧩 Sokoban box puzzles
    chess.Game,           # ♟️ Full chess with AI
    card_battle.Game,     # 🃏 Card battle game
    civ.Game,             # 🌎 Civilization-style strategy
    rts.Game,             # 🏰 Real-time strategy
    tycoon.Game,          # 💰 Theme-park tycoon
    farming.Game,         # 🌾 Farming simulator
    survival.Game,        # 🏝️ Wilderness survival
]
