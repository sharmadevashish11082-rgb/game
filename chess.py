"""Grand Chess — full chess rules, local 2P or vs a minimax AI."""
import copy
import random

import pygame

try:
    from .engine import Game, draw_text, WIDTH, HEIGHT
except ImportError:  # allow direct run: python games/chess.py
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from games.engine import Game, draw_text, WIDTH, HEIGHT

SQ = 64
BOARD_X = (WIDTH - 8 * SQ) // 2
BOARD_Y = 36
VALS = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}
UNICODE = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙"}


class Board:
    def __init__(self):
        self.grid = [list("rnbqkbnr"), ["p"] * 8, ["."] * 8, ["."] * 8,
                     ["."] * 8, ["."] * 8, ["P"] * 8, list("RNBQKBNR")]
        self.turn = "w"
        self.en_passant = None
        self.rights = {"K": True, "Q": True, "k": True, "q": True}
        self.history = []
        # FIDE draw-rule bookkeeping: halfmove clock (plies since the last
        # pawn move or capture) and how many times each position has appeared.
        self.halfmove = 0
        # FIDE Art. 9.2 counts the initial position as its first occurrence.
        self.pos_seen = {self.position_key(): 1}
        self.draw_reason = None

    def position_key(self):
        """Canonical key for threefold repetition: pieces, side to move,
        castling rights and the en-passant target square."""
        return (tuple("".join(r) for r in self.grid), self.turn,
                tuple(self.rights[k] for k in "KQkq"), self.en_passant)

    def insufficient_material(self):
        """True when checkmate is impossible by any sequence of legal moves
        (FIDE Art. 5.2.2): K vs K, K+minor vs K, K+B vs K+B on same colour."""
        pieces = [p for row in self.grid for p in row if p != "."]
        for p in pieces:
            if p.upper() in "PRQ":
                return False
        minors = [p for p in pieces if p.upper() in "NB"]
        if len(minors) <= 1:
            return True
        if all(p.upper() == "B" for p in minors):
            colours = {(r + c) % 2 for r in range(8) for c in range(8)
                       if self.grid[r][c].upper() == "B"}
            if len(colours) == 1:
                return True
        return False

    def color(self, r, c):
        p = self.grid[r][c]
        return None if p == "." else ("w" if p.isupper() else "b")

    def king_pos(self, color):
        for r in range(8):
            for c in range(8):
                p = self.grid[r][c]
                if p != "." and p.upper() == "K" and self.color(r, c) == color:
                    return r, c
        return None

    def in_bounds(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def attacked(self, r, c, by):
        for rr in range(8):
            for cc in range(8):
                if self.color(rr, cc) != by:
                    continue
                p = self.grid[rr][cc]
                if p.upper() == "P":
                    d = -1 if by == "w" else 1
                    if (rr + d, cc - 1) == (r, c) or (rr + d, cc + 1) == (r, c):
                        return True
                elif p.upper() == "N":
                    for dr, dc in ((2, 1), (2, -1), (-2, 1), (-2, -1),
                                   (1, 2), (1, -2), (-1, 2), (-1, -2)):
                        if (rr + dr, cc + dc) == (r, c):
                            return True
                elif p.upper() == "K":
                    if abs(rr - r) <= 1 and abs(cc - c) <= 1:
                        return True
                else:
                    dirs = {"R": ((1, 0), (-1, 0), (0, 1), (0, -1)),
                            "B": ((1, 1), (1, -1), (-1, 1), (-1, -1)),
                            "Q": ((1, 0), (-1, 0), (0, 1), (0, -1),
                                  (1, 1), (1, -1), (-1, 1), (-1, -1))}[p.upper()]
                    for dr, dc in dirs:
                        rr2, cc2 = rr + dr, cc + dc
                        while self.in_bounds(rr2, cc2):
                            if (rr2, cc2) == (r, c):
                                return True
                            if self.grid[rr2][cc2] != ".":
                                break
                            rr2 += dr
                            cc2 += dc
        return False

    def in_check(self, color):
        kp = self.king_pos(color)
        if kp is None:
            return False
        return self.attacked(*kp, "b" if color == "w" else "w")

    def pseudo_moves(self, r, c):
        p = self.grid[r][c]
        if p == ".":
            return []
        col = self.color(r, c)
        up = -1 if col == "w" else 1
        U = p.upper()
        moves = []
        if U == "P":
            sr = 6 if col == "w" else 1
            if self.in_bounds(r + up, c) and self.grid[r + up][c] == ".":
                moves.append((r, c, r + up, c))
                if r == sr and self.grid[r + 2 * up][c] == ".":
                    moves.append((r, c, r + 2 * up, c))
            for dc in (-1, 1):
                nr, nc = r + up, c + dc
                if self.in_bounds(nr, nc):
                    if self.color(nr, nc) == ("b" if col == "w" else "w"):
                        moves.append((r, c, nr, nc))
                    elif (nr, nc) == self.en_passant:
                        moves.append((r, c, nr, nc, "ep"))
        elif U == "N":
            for dr, dc in ((2, 1), (2, -1), (-2, 1), (-2, -1),
                           (1, 2), (1, -2), (-1, 2), (-1, -2)):
                nr, nc = r + dr, c + dc
                if self.in_bounds(nr, nc) and self.color(nr, nc) != col:
                    moves.append((r, c, nr, nc))
        elif U == "K":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if self.in_bounds(nr, nc) and self.color(nr, nc) != col:
                        moves.append((r, c, nr, nc))
            if (col == "w" and r == 7) or (col == "b" and r == 0):
                enemy = "b" if col == "w" else "w"
                rook = "R" if col == "w" else "r"
                if self.rights.get("K" if col == "w" else "k") and \
                        self.grid[r][5] == "." and self.grid[r][6] == "." and \
                        self.grid[r][7] == rook and not self.attacked(r, 4, enemy) and \
                        not self.attacked(r, 5, enemy) and not self.attacked(r, 6, enemy):
                    moves.append((r, c, r, 6))
                if self.rights.get("Q" if col == "w" else "q") and \
                        self.grid[r][3] == "." and self.grid[r][2] == "." and \
                        self.grid[r][1] == "." and self.grid[r][0] == rook and \
                        not self.attacked(r, 4, enemy) and not self.attacked(r, 3, enemy) and \
                        not self.attacked(r, 2, enemy):
                    moves.append((r, c, r, 2))
        elif U in "RBQ":
            dirs = {"R": ((1, 0), (-1, 0), (0, 1), (0, -1)),
                    "B": ((1, 1), (1, -1), (-1, 1), (-1, -1)),
                    "Q": ((1, 0), (-1, 0), (0, 1), (0, -1),
                          (1, 1), (1, -1), (-1, 1), (-1, -1))}[U]
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                while self.in_bounds(nr, nc):
                    if self.grid[nr][nc] == ".":
                        moves.append((r, c, nr, nc))
                    else:
                        if self.color(nr, nc) != col:
                            moves.append((r, c, nr, nc))
                        break
                    nr += dr
                    nc += dc
        out = []
        for m in moves:
            if m[2] in (0, 7) and U == "P":
                for promo in "QRBN":
                    out.append(m[:4] + (promo,))
            else:
                out.append(m)
        return out

    def legal_moves(self, r, c):
        col = self.color(r, c)
        out = []
        for m in self.pseudo_moves(r, c):
            b2 = self.apply(m, dry=True)
            if b2 and not b2.in_check(col):
                out.append(m)
        return out

    def all_legal(self, color):
        out = []
        for r in range(8):
            for c in range(8):
                if self.color(r, c) == color:
                    out += self.legal_moves(r, c)
        return out

    def clone(self):
        b = Board.__new__(Board)
        b.grid = [list(row) for row in self.grid]
        b.turn = self.turn
        b.en_passant = self.en_passant
        b.rights = dict(self.rights)
        b.history = []
        b.halfmove = self.halfmove
        b.pos_seen = dict(self.pos_seen)
        b.draw_reason = None
        return b

    def apply(self, m, dry=True):
        if dry:
            b = self.clone()
            b.make_move(m)
            return b
        self.make_move(m)
        return self

    def make_move(self, m):
        r, c, nr, nc = m[:4]
        tag = m[4] if len(m) > 4 else None
        piece = self.grid[r][c]
        captured = self.grid[nr][nc]
        ep_pawn = None
        if tag == "ep":
            captured = self.grid[r][nc]
            ep_pawn = (r, nc)
        # Snapshot everything undo() needs BEFORE mutating any state.
        prev_ep = self.en_passant
        prev_rights = dict(self.rights)
        prev_half = self.halfmove
        prev_key = self.position_key()
        prev_count = self.pos_seen.get(prev_key, 0)
        self.grid[r][c] = "."
        self.grid[nr][nc] = piece
        if tag and tag in "QRBN":
            self.grid[nr][nc] = tag if piece.isupper() else tag.lower()
        if piece.upper() == "K" and abs(nc - c) == 2:
            if nc > c:
                self.grid[r][5], self.grid[r][7] = self.grid[r][7], "."
            else:
                self.grid[r][3], self.grid[r][0] = self.grid[r][0], "."
        self.history.append((m, captured, ep_pawn, prev_ep, prev_rights,
                             prev_half, prev_key, prev_count))
        self.turn = "b" if self.turn == "w" else "w"
        self.en_passant = None
        if piece.upper() == "P" and abs(nr - r) == 2:
            self.en_passant = ((r + nr) // 2, c)
        if piece.upper() == "K":
            if piece.isupper():
                self.rights["K"] = self.rights["Q"] = False
            else:
                self.rights["k"] = self.rights["q"] = False
        if piece.upper() == "R":
            self._rook_moved(r, c, piece.isupper())
        if captured != "." and captured.upper() == "R":
            self._rook_taken(nr, nc, captured.isupper())
        # FIDE Art. 9.3: the halfmove clock resets on pawn moves and captures.
        if piece.upper() == "P" or captured != ".":
            self.halfmove = 0
        else:
            self.halfmove = prev_half + 1
        key = self.position_key()
        self.pos_seen[key] = self.pos_seen.get(key, 0) + 1

    def _rook_moved(self, r, c, white):
        if white:
            if (r, c) == (7, 0):
                self.rights["Q"] = False
            elif (r, c) == (7, 7):
                self.rights["K"] = False
        else:
            if (r, c) == (0, 0):
                self.rights["q"] = False
            elif (r, c) == (0, 7):
                self.rights["k"] = False

    def _rook_taken(self, r, c, white):
        if white:
            if (r, c) == (7, 0):
                self.rights["Q"] = False
            elif (r, c) == (7, 7):
                self.rights["K"] = False
        else:
            if (r, c) == (0, 0):
                self.rights["q"] = False
            elif (r, c) == (0, 7):
                self.rights["k"] = False

    def undo(self):
        if not self.history:
            return
        # The position this move *created* is the state as it stands right now
        # (pieces moved, turn flipped). Capture it before restoring anything.
        after_key = self.position_key()
        (m, captured, ep_pawn, prev_ep, prev_rights, prev_half,
         prev_key, prev_count) = self.history.pop()
        r, c, nr, nc = m[:4]
        tag = m[4] if len(m) > 4 else None
        piece = self.grid[nr][nc]
        if piece.upper() == "K" and abs(nc - c) == 2:
            rook = "R" if piece.isupper() else "r"
            if nc > c:
                self.grid[r][7] = rook
                self.grid[r][5] = "."
            else:
                self.grid[r][0] = rook
                self.grid[r][3] = "."
        if tag and tag in "QRBN":
            self.grid[r][c] = "P" if piece.isupper() else "p"
        else:
            self.grid[r][c] = piece
        self.grid[nr][nc] = captured
        if ep_pawn:
            self.grid[ep_pawn[0]][ep_pawn[1]] = "p" if piece.isupper() else "P"
        # Undo the repetition bookkeeping: leave the position we just left.
        if self.pos_seen.get(after_key, 0) <= 1:
            self.pos_seen.pop(after_key, None)
        else:
            self.pos_seen[after_key] -= 1
        self.pos_seen[prev_key] = prev_count
        self.halfmove = prev_half
        self.en_passant = prev_ep
        self.rights = prev_rights
        self.turn = "b" if self.turn == "w" else "w"

    def status(self):
        """Game state per FIDE: ok / check / checkmate / draw (with reason)."""
        moves = self.all_legal(self.turn)
        if not moves:
            if self.in_check(self.turn):
                return "checkmate"
            self.draw_reason = "stalemate — no legal moves"
            return "draw"
        # FIDE Art. 9.3: 50 moves by each side without a pawn move or capture.
        if self.halfmove >= 100:
            self.draw_reason = "fifty-move rule — 50 moves without a pawn move or capture"
            return "draw"
        # FIDE Art. 9.2: the same position for the third time.
        if self.pos_seen.get(self.position_key(), 0) >= 3:
            self.draw_reason = "threefold repetition"
            return "draw"
        # FIDE Art. 5.2.2: checkmate is impossible.
        if self.insufficient_material():
            self.draw_reason = "insufficient material — mate is impossible"
            return "draw"
        return "check" if self.in_check(self.turn) else "ok"


def evaluate(b):
    s = 0
    for r in range(8):
        for c in range(8):
            p = b.grid[r][c]
            if p == ".":
                continue
            v = VALS[p.upper()]
            if p.isupper():
                s += v
            else:
                s -= v
    return s


def minimax(b, depth, alpha, beta, maximizing):
    moves = b.all_legal(b.turn)
    if not moves:
        if b.in_check(b.turn):
            return -99999 if maximizing else 99999
        return 0
    if depth == 0:
        return evaluate(b)
    if maximizing:
        best = -1e9
        for m in moves:
            nb = b.apply(m, dry=True)
            score = minimax(nb, depth - 1, alpha, beta, False)
            best = max(best, score)
            alpha = max(alpha, score)
            if beta <= alpha:
                break
        return best
    else:
        best = 1e9
        for m in moves:
            nb = b.apply(m, dry=True)
            score = minimax(nb, depth - 1, alpha, beta, True)
            best = min(best, score)
            beta = min(beta, score)
            if beta <= alpha:
                break
        return best


def ai_move(b, depth=2):
    moves = b.all_legal(b.turn)
    if not moves:
        return None
    random.shuffle(moves)
    best_m, best_s = None, -1e9
    for m in moves:
        nb = b.apply(m, dry=True)
        s = minimax(nb, depth - 1, -1e9, 1e9, False)
        if s > best_s:
            best_s, best_m = s, m
    return best_m


class Game(Game):
    name = "Grand Chess"
    emoji = "♟️"
    tagline = "Full chess rules. Play a friend or the engine."
    controls = "Click to move · U undo · R new game · ESC menu"

    def __init__(self, app):
        super().__init__(app)
        self.reset()

    def reset(self):
        self.board = Board()
        self.selected = None
        self.targets = []
        self.ai_color = None
        self.mode = "menu"
        self.show_menu("CHESS", ["Play vs CPU (White)", "Play vs CPU (Black)",
                                 "Two Players", "Main Menu"])
        self.last_move = None
        self.status = "ok"
        self.winner = None
        self.promo = None
        self.move_log = []

    def handle_event(self, event):
        super().handle_event(event)
        if self.mode == "menu":
            choice = self.menu_choice(event)
            if choice == 0:
                self.ai_color = "b"
                self.mode = "play"
            elif choice == 1:
                self.ai_color = "w"
                self.mode = "play"
                self.ai_think()
            elif choice == 2:
                self.ai_color = None
                self.mode = "play"
            elif choice == 3:
                self.app.quit_to_menu()
            return
        if self.promo:
            choice = self.menu_choice(event)
            if choice is not None:
                promo = "QRBN"[choice]
                self.board.make_move(self.promo + (promo,))
                self.promo = None
                self.selected = None
                self.targets = []
                self.after_move()
            return
        if self.winner:
            choice = self.menu_choice(event)
            if choice == 0:
                self.reset()
            elif choice == 1:
                self.app.quit_to_menu()
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_u:
                self.board.undo()
                self.board.undo()
                self.selected = None
                self.last_move = None
                self.status = self.board.status()
            elif event.key == pygame.K_r:
                self.reset()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(event.pos)

    def click(self, pos):
        bx, by = BOARD_X, BOARD_Y
        if not (bx <= pos[0] < bx + 8 * SQ and by <= pos[1] < by + 8 * SQ):
            return
        c = (pos[0] - bx) // SQ
        r = (pos[1] - by) // SQ
        human = self.ai_color != self.board.turn
        if not human:
            return
        if self.selected:
            for m in self.targets:
                if (m[2], m[3]) == (r, c):
                    self.try_move(m)
                    return
            self.selected = None
            self.targets = []
        if self.board.color(r, c) == self.board.turn:
            self.selected = (r, c)
            self.targets = self.board.legal_moves(r, c)

    def try_move(self, m):
        r, c, nr, nc = m[:4]
        if self.board.grid[r][c].upper() == "P" and nr in (0, 7):
            self.promo = m[:4]
            self.show_menu("PROMOTE TO", ["Queen", "Rook", "Bishop", "Knight"])
            return
        self.board.make_move(m)
        self.after_move()

    def after_move(self):
        self.last_move = self.board.history[-1][0] if self.board.history else None
        self.status = self.board.status()
        if self.status in ("checkmate", "draw"):
            if self.status == "checkmate":
                winner = "White" if self.board.turn == "b" else "Black"
                self.winner = winner
                self.show_menu(f"CHECKMATE — {winner} wins!",
                               ["New Game", "Main Menu"])
            else:
                self.winner = "Draw"
                self.show_menu(f"DRAW — {self.board.draw_reason}",
                               ["New Game", "Main Menu"],
                               title_color=(150, 220, 255))
        elif self.ai_color and self.ai_color == self.board.turn and not self.winner:
            self.ai_think()

    def ai_think(self):
        m = ai_move(self.board, depth=2)
        if m:
            self.board.make_move(m)
            self.after_move()

    def update(self, dt):
        pass

    def draw(self, surf):
        surf.fill((24, 26, 40))
        draw_text(surf, "GRAND CHESS", 24, (255, 208, 74), (WIDTH // 2, 8),
                  align="center", bold=True)
        for r in range(8):
            for c in range(8):
                rect = pygame.Rect(BOARD_X + c * SQ, BOARD_Y + r * SQ, SQ, SQ)
                col = (235, 225, 200) if (r + c) % 2 == 0 else (120, 96, 74)
                if self.selected == (r, c):
                    col = (255, 224, 120)
                elif self.last_move and ((r, c) == (self.last_move[0], self.last_move[1]) or
                                         (r, c) == (self.last_move[2], self.last_move[3])):
                    col = (255, 214, 130) if (r + c) % 2 == 0 else (190, 150, 80)
                pygame.draw.rect(surf, col, rect)
                if self.board.in_check(self.board.turn):
                    kp = self.board.king_pos(self.board.turn)
                    if kp and kp == (r, c):
                        pygame.draw.rect(surf, (255, 90, 90), rect)
                p = self.board.grid[r][c]
                if p != ".":
                    white = p.isupper()
                    ch = UNICODE[p.upper()]
                    color = (250, 250, 250) if white else (30, 30, 40)
                    draw_text(surf, ch, 42, color, rect.center, align="center",
                              outline=0)
        for m in self.targets:
            tr, tc = m[2], m[3]
            cx = BOARD_X + tc * SQ + SQ // 2
            cy = BOARD_Y + tr * SQ + SQ // 2
            if self.board.grid[tr][tc] == ".":
                pygame.draw.circle(surf, (60, 60, 80), (cx, cy), 8, 2)
            else:
                pygame.draw.circle(surf, (255, 120, 90), (cx, cy), SQ // 2, 3)
        if self.selected:
            pygame.draw.rect(surf, (255, 208, 74),
                             (BOARD_X + self.selected[1] * SQ,
                              BOARD_Y + self.selected[0] * SQ, SQ, SQ), 3)
        pygame.draw.rect(surf, (90, 96, 130), (BOARD_X, BOARD_Y, 8 * SQ, 8 * SQ), 3)

        labels = ""
        if self.ai_color:
            labels = f"You: {'White' if self.ai_color == 'b' else 'Black'}   "
        labels += f"Turn: {'White' if self.board.turn == 'w' else 'Black'}"
        draw_text(surf, labels, 16, (220, 224, 240), (14, HEIGHT - 30))
        if self.status == "check":
            draw_text(surf, "CHECK!", 22, (255, 120, 90), (WIDTH - 14, HEIGHT - 30),
                      align="topright", bold=True)
        draw_text(surf, "U undo · R new game", 13, (140, 146, 175),
                  (WIDTH // 2, HEIGHT - 12), align="center")
        if self.mode == "menu":
            self.menu.draw(surf)
        elif self.promo:
            self.menu.draw(surf)
        elif self.winner:
            self.menu.draw(surf)


if __name__ == "__main__":
    # Allow running this file directly: python games/chess.py
    from games.engine import App
    App(Game).run()
