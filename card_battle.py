"""Arcane Duel — a card battle game: build mana, play cards, outlast the AI."""
import random

import pygame

try:
    from .engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, Button
except ImportError:  # allow direct run: python games/card_battle.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, draw_health_bar, WIDTH, HEIGHT, Button

CARDS = {
    "strike": dict(name="Strike", cost=1, kind="dmg", val=6, color=(255, 150, 90)),
    "heavy":  dict(name="Heavy Blow", cost=2, kind="dmg", val=11, color=(255, 120, 120)),
    "fire":   dict(name="Fireball", cost=3, kind="dmg", val=16, color=(255, 90, 60)),
    "heal":   dict(name="Heal", cost=2, kind="heal", val=10, color=(120, 220, 120)),
    "shield": dict(name="Barrier", cost=2, kind="shield", val=10, color=(120, 190, 255)),
    "poison": dict(name="Venom", cost=2, kind="poison", val=3, color=(160, 120, 255)),
    "drain":  dict(name="Drain", cost=3, kind="drain", val=9, color=(90, 220, 200)),
    "cleave": dict(name="Cleave", cost=4, kind="dmg", val=22, color=(255, 180, 60)),
}
DECK_POOL = ["strike"] * 5 + ["heavy"] * 3 + ["fire"] * 2 + ["heal"] * 3 + \
            ["shield"] * 2 + ["poison"] * 2 + ["drain"] * 2 + ["cleave"] * 1
ENEMY_DECK = ["strike"] * 4 + ["fire"] * 3 + ["heal"] * 3 + ["shield"] * 2 + ["heavy"] * 3
MAX_HP = 30
HAND_MAX = 5


class Game(Game):
    name = "Arcane Duel"
    emoji = "🃏"
    tagline = "Mana, cards, and a smarter-than-it-looks AI."
    controls = "1-4 play card · E end turn · Click also works · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.player_hp = MAX_HP
        self.enemy_hp = MAX_HP
        self.p_shield = 0
        self.e_shield = 0
        self.mana = 2
        self.max_mana = 2
        self.e_mana = 2
        self.turn = 1
        self.p_deck = list(DECK_POOL)
        self.e_deck = list(ENEMY_DECK)
        random.shuffle(self.p_deck)
        random.shuffle(self.e_deck)
        self.p_hand = [self.p_deck.pop() for _ in range(4)]
        self.e_hand = [self.e_deck.pop() for _ in range(3)]
        self.poison = 0
        self.log = ["The duel begins. Play your cards!", ""]
        self.over = False
        self.victory = False
        self.end_btn = Button((WIDTH - 150, 86, 130, 44), "End Turn [E]", size=17)
        self.msg_t = 0.0

    def draw_hand(self, n):
        while len(self.p_hand) < HAND_MAX and self.p_deck:
            self.p_hand.append(self.p_deck.pop())
        if not self.p_hand and not self.p_deck:
            pass

    def add_log(self, text):
        self.log.insert(0, text)
        self.log = self.log[:5]

    def play(self, idx):
        if self.over or idx >= len(self.p_hand):
            return
        card = CARDS[self.p_hand[idx]]
        if card["cost"] > self.mana:
            self.add_log("Not enough mana!")
            return
        self.mana -= card["cost"]
        self.p_hand.pop(idx)
        self.resolve(card, enemy=True)
        if self.enemy_hp <= 0:
            self.finish(win=True)

    def resolve(self, card, enemy):
        kind, val = card["kind"], card["val"]
        if kind == "dmg":
            target_shield = self.e_shield if enemy else self.p_shield
            absorbed = min(target_shield, val)
            if enemy:
                self.e_shield -= absorbed
                self.enemy_hp -= val - absorbed
            else:
                self.p_shield -= absorbed
                self.player_hp -= val - absorbed
            if enemy:
                self.add_log(f"You cast {card['name']} for {val} damage!")
            else:
                self.add_log(f"Enemy casts {card['name']} for {val} damage!")
        elif kind == "heal":
            if enemy:
                self.player_hp = min(MAX_HP, self.player_hp + val)
                self.add_log(f"You heal for {val}.")
            else:
                self.enemy_hp = min(MAX_HP, self.enemy_hp + val)
                self.add_log(f"Enemy heals for {val}.")
        elif kind == "shield":
            if enemy:
                self.p_shield += val
                self.add_log(f"You raise a barrier ({self.p_shield}).")
            else:
                self.e_shield += val
                self.add_log(f"Enemy raises a barrier ({self.e_shield}).")
        elif kind == "poison":
            self.poison += val
            self.add_log(f"Enemy is poisoned ({self.poison}/turn).")
        elif kind == "drain":
            if enemy:
                self.enemy_hp -= val
                self.player_hp = min(MAX_HP, self.player_hp + val // 2)
                self.add_log(f"Drain: {val} damage, {val // 2} life.")
            else:
                self.player_hp -= val
                self.enemy_hp = min(MAX_HP, self.enemy_hp + val // 2)
                self.add_log(f"Enemy drains you for {val}.")

    def e_turn(self):
        self.e_mana += 1
        self.draw_hand(0)
        if self.e_deck:
            self.e_hand.append(self.e_deck.pop())
        if len(self.e_hand) > 5:
            self.e_hand = self.e_hand[:5]
        while True:
            affordable = [i for i, c in enumerate(self.e_hand)
                          if CARDS[c]["cost"] <= self.e_mana]
            if not affordable:
                break
            choice = None
            for i in affordable:
                c = CARDS[self.e_hand[i]]
                if self.enemy_hp < 12 and c["kind"] == "heal":
                    choice = i
                    break
            if choice is None:
                for i in affordable:
                    if CARDS[self.e_hand[i]]["kind"] == "dmg":
                        choice = i
                        break
            if choice is None:
                choice = random.choice(affordable)
            card = CARDS[self.e_hand[choice]]
            self.e_mana -= card["cost"]
            self.e_hand.pop(choice)
            self.resolve(card, enemy=False)
            if self.player_hp <= 0:
                self.finish(win=False)
                return
            if self.enemy_hp <= 0:
                self.finish(win=True)
                return
        # start player turn
        self.turn += 1
        self.max_mana = min(9, self.max_mana + 1)
        self.mana = self.max_mana
        if self.poison > 0:
            self.enemy_hp -= self.poison
            self.poison = max(0, self.poison - 1)
            self.add_log(f"Poison deals {self.poison + 1} damage.")
            if self.enemy_hp <= 0:
                self.finish(win=True)
                return
        self.draw_hand(0)

    def finish(self, win):
        self.over = True
        self.victory = win
        if win:
            self.show_menu("VICTORY!", ["Play Again", "Main Menu"],
                           f"Won on turn {self.turn}", title_color=(120, 255, 150))
        else:
            self.show_menu("DEFEAT", ["Play Again", "Main Menu"],
                           f"Survived {self.turn} turns")

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
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                             pygame.K_5):
                self.play(event.key - pygame.K_1)
            elif event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                self.e_turn()
        if self.end_btn.handle(event):
            self.e_turn()

    def update(self, dt):
        self.msg_t = max(0.0, self.msg_t - dt)

    def draw(self, surf):
        surf.fill((26, 30, 46))
        pygame.draw.rect(surf, (34, 40, 62), (0, 0, WIDTH, 70))
        pygame.draw.rect(surf, (34, 40, 62), (0, HEIGHT - 190, WIDTH, 190))
        pygame.draw.rect(surf, (255, 208, 74), (0, 70, WIDTH, 2))
        pygame.draw.rect(surf, (255, 208, 74), (0, HEIGHT - 192, WIDTH, 2))
        draw_text(surf, "ARCANE DUEL", 22, (255, 208, 74), (WIDTH // 2, 14),
                  align="center", bold=True)
        draw_text(surf, f"Turn {self.turn}", 15, (200, 204, 224), (WIDTH // 2, 44),
                  align="center")

        # enemy
        draw_text(surf, "ENEMY MAGE", 17, (255, 140, 140), (24, 84), bold=True)
        draw_health_bar(surf, 24, 108, 340, 20, self.enemy_hp / MAX_HP, fg=(255, 110, 110))
        draw_text(surf, f"{self.enemy_hp}/{MAX_HP}", 14, (255, 255, 255), (28, 132))
        if self.e_shield:
            draw_text(surf, f"🛡 {self.e_shield}", 15, (140, 220, 255), (380, 108))
        draw_text(surf, f"Mana {self.e_mana}", 14, (255, 208, 74), (380, 132))
        for i, c in enumerate(self.e_hand):
            x = 440 + i * 92
            pygame.draw.rect(surf, (90, 60, 90), (x, 88, 76, 46), border_radius=6)
            draw_text(surf, "?", 22, (220, 220, 240), (x + 38, 111), align="center")

        # player
        draw_text(surf, "YOU", 17, (150, 200, 255), (24, 190), bold=True)
        draw_health_bar(surf, 24, 214, 340, 20, self.player_hp / MAX_HP, fg=(90, 160, 255))
        draw_text(surf, f"{self.player_hp}/{MAX_HP}", 14, (255, 255, 255), (28, 238))
        if self.p_shield:
            draw_text(surf, f"🛡 {self.p_shield}", 15, (140, 220, 255), (380, 214))
        draw_text(surf, "Mana " + "◆" * self.mana + "◇" * (self.max_mana - self.mana),
                  16, (255, 208, 74), (24, 262))
        if self.poison:
            draw_text(surf, f"Poison on enemy: {self.poison}", 14, (180, 140, 255),
                      (24, 288))

        for i, cid in enumerate(self.p_hand):
            card = CARDS[cid]
            x = 40 + i * 120
            y = HEIGHT - 168
            rect = pygame.Rect(x, y, 104, 140)
            afford = card["cost"] <= self.mana
            pygame.draw.rect(surf, (28, 30, 46), rect, border_radius=10)
            pygame.draw.rect(surf, card["color"], rect, 3 if afford else 1, border_radius=10)
            if not afford:
                veil = pygame.Surface(rect.size, pygame.SRCALPHA)
                veil.fill((0, 0, 0, 130))
                surf.blit(veil, rect.topleft)
            draw_text(surf, str(card["cost"]), 18, (255, 255, 255), (x + 12, y + 8),
                      bold=True)
            pygame.draw.circle(surf, (80, 140, 255), (x + 16, y + 18), 11)
            draw_text(surf, card["name"], 14, (255, 255, 255), (x + 52, y + 44),
                      align="center", max_width=96)
            draw_text(surf, f"{card['kind']} {card['val']}", 13, (200, 204, 224),
                      (x + 52, y + 100), align="center")
            draw_text(surf, str(i + 1), 13, (150, 158, 190), (x + 90, y + 8))
        self.end_btn.draw(surf)
        for i, line in enumerate(self.log):
            draw_text(surf, line, 14, (200, 204, 224), (24, 320 - i * 18))
        if self.menu:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/card_battle.py
    from games.engine import App
    App(Game).run()
