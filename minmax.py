from board import RED, YELLOW


class MiniMaxAI:
    def __init__(self, depth=5):
        self.depth = depth
        self.my_color = YELLOW
        self.opp_color = RED

    # ─────────────────────────────────────────────
    # SCORE D'UNE FENÊTRE DE 4 CASES
    # ─────────────────────────────────────────────
    def score_window(self, window, color):
        opp = RED if color == YELLOW else YELLOW
        score = 0

        my_count  = window.count(color)
        opp_count = window.count(opp)
        empty     = window.count(0)

        # Si les deux joueurs ont des pions dans la fenêtre → fenêtre morte
        if my_count > 0 and opp_count > 0:
            return 0

        # Attaque
        if my_count == 4:
            score += 1_000_000
        elif my_count == 3 and empty == 1:
            score += 5_000
        elif my_count == 2 and empty == 2:
            score += 500
        elif my_count == 1 and empty == 3:
            score += 50

        # Défense — valeurs augmentées pour être plus agressif défensivement
        if opp_count == 4:
            score -= 1_000_000
        elif opp_count == 3 and empty == 1:
            score -= 500_000
        elif opp_count == 2 and empty == 2:
            score -= 10_000   # était -2000, trop faible
        elif opp_count == 1 and empty == 3:
            score -= 200

        return score

    # ─────────────────────────────────────────────
    # ÉVALUATION STATIQUE DU PLATEAU
    # ─────────────────────────────────────────────
    def evaluate(self, board):
        score = 0

        # Bonus centre — colonnes proches du centre valent plus
        center_col = board.cols // 2
        for r in range(board.rows):
            for c in range(board.cols):
                dist = abs(c - center_col)
                bonus = max(0, 3 - dist) * 10
                if board.grid[r][c] == self.my_color:
                    score += bonus
                elif board.grid[r][c] == self.opp_color:
                    score -= bonus

        # Évaluation des deux couleurs dans toutes les directions
        for color, sign in [(self.my_color, 1), (self.opp_color, -1)]:
            # Horizontal
            for r in range(board.rows):
                for c in range(board.cols - 3):
                    window = [board.grid[r][c + i] for i in range(4)]
                    score += sign * self.score_window(window, color)

            # Vertical
            for c in range(board.cols):
                for r in range(board.rows - 3):
                    window = [board.grid[r + i][c] for i in range(4)]
                    score += sign * self.score_window(window, color)

            # Diagonale ↘
            for r in range(board.rows - 3):
                for c in range(board.cols - 3):
                    window = [board.grid[r + i][c + i] for i in range(4)]
                    score += sign * self.score_window(window, color)

            # Diagonale ↗
            for r in range(3, board.rows):
                for c in range(board.cols - 3):
                    window = [board.grid[r - i][c + i] for i in range(4)]
                    score += sign * self.score_window(window, color)

        return score

    # ─────────────────────────────────────────────
    # MINIMAX AVEC ÉLAGAGE ALPHA-BÊTA
    # ─────────────────────────────────────────────
    def minimax(self, board, depth, alpha, beta, is_max):
        if board.check_winner(self.my_color):  return  2_000_000 + depth
        if board.check_winner(self.opp_color): return -2_000_000 - depth
        if board.is_full() or depth == 0:      return self.evaluate(board)

        valid_cols = self.ordered_cols(board)

        if is_max:
            value = -float('inf')
            for col in valid_cols:
                board.drop_piece(col, self.my_color)
                value = max(value, self.minimax(board, depth - 1, alpha, beta, False))
                board.undo()
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = float('inf')
            for col in valid_cols:
                board.drop_piece(col, self.opp_color)
                value = min(value, self.minimax(board, depth - 1, alpha, beta, True))
                board.undo()
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    # ─────────────────────────────────────────────
    # COLONNES TRIÉES (centre en priorité)
    # ─────────────────────────────────────────────
    def ordered_cols(self, board):
        center = board.cols // 2
        cols = [c for c in range(board.cols) if not board.is_column_full(c)]
        cols.sort(key=lambda c: abs(c - center))
        return cols

    # ─────────────────────────────────────────────
    # CHOIX DU COUP
    # ─────────────────────────────────────────────
    def choose_move(self, board, color):
        self.my_color  = color
        self.opp_color = RED if color == YELLOW else YELLOW

        self.scores = [None] * board.cols
        valid_cols  = self.ordered_cols(board)

        if not valid_cols:
            return None

        # Étape 1 : victoire immédiate pour MOI
        for col in valid_cols:
            board.drop_piece(col, self.my_color)
            if board.check_winner(self.my_color):
                board.undo()
                print(f"[MINIMAX] Victoire immédiate → col {col}")
                return col
            board.undo()

        # Étape 2 : bloquer victoire immédiate adverse
        for col in valid_cols:
            board.drop_piece(col, self.opp_color)
            if board.check_winner(self.opp_color):
                board.undo()
                print(f"[MINIMAX] Blocage immédiat → col {col}")
                return col
            board.undo()

        # Étape 3 : minimax complet
        best_col   = None
        best_score = -float('inf')

        for col in valid_cols:
            board.drop_piece(col, self.my_color)
            score = self.minimax(board, self.depth - 1, -float('inf'), float('inf'), False)
            board.undo()

            self.scores[col] = score
            print(f"[MINIMAX] col {col} → score {score}")

            if score > best_score:
                best_score = score
                best_col   = col

        return best_col if best_col is not None else valid_cols[0]