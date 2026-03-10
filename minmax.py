from board import RED, YELLOW

class MiniMaxAI:
    def __init__(self, depth=5):
        self.depth = depth
        self.scores = []

    # ---------- SCORING D'UNE FENÊTRE ----------
    def score_window(self, window, color):
        opp = RED if color == YELLOW else YELLOW
        score = 0

        if window.count(color) == 4:
            score += 100000
        elif window.count(color) == 3 and window.count(0) == 1:
            score += 100
        elif window.count(color) == 2 and window.count(0) == 2:
            score += 10

        if window.count(opp) == 3 and window.count(0) == 1:
            score -= 200  # bloquer l'adversaire est prioritaire
        elif window.count(opp) == 2 and window.count(0) == 2:
            score -= 5

        return score

    # ---------- EVALUATION DU PLATEAU ----------
    def evaluate(self, board):
        score = 0

        # Bonus centre (contrôler le centre = avantage stratégique)
        center_col = board.cols // 2
        center_array = [board.grid[r][center_col] for r in range(board.rows)]
        score += center_array.count(YELLOW) * 8

        # Bonus colonne adjacente au centre
        for offset in [1, -1]:
            col = center_col + offset
            if 0 <= col < board.cols:
                col_array = [board.grid[r][col] for r in range(board.rows)]
                score += col_array.count(YELLOW) * 4

        # Horizontal
        for r in range(board.rows):
            for c in range(board.cols - 3):
                window = [board.grid[r][c+i] for i in range(4)]
                score += self.score_window(window, YELLOW)

        # Vertical
        for c in range(board.cols):
            for r in range(board.rows - 3):
                window = [board.grid[r+i][c] for i in range(4)]
                score += self.score_window(window, YELLOW)

        # Diagonale \\
        for r in range(board.rows - 3):
            for c in range(board.cols - 3):
                window = [board.grid[r+i][c+i] for i in range(4)]
                score += self.score_window(window, YELLOW)

        # Diagonale /
        for r in range(3, board.rows):
            for c in range(board.cols - 3):
                window = [board.grid[r-i][c+i] for i in range(4)]
                score += self.score_window(window, YELLOW)

        return score

    # ---------- VICTOIRE IMMEDIATE ----------
    def is_terminal(self, board):
        return (
            board.check_winner(RED) or
            board.check_winner(YELLOW) or
            board.is_full()
        )

    # ---------- ORDRE DES COUPS (centre en premier) ----------
    def ordered_cols(self, board):
        center = board.cols // 2
        cols = [c for c in range(board.cols) if not board.is_column_full(c)]
        cols.sort(key=lambda c: abs(c - center))
        return cols

    # ---------- MINIMAX AVEC ALPHA-BETA ----------
    def minimax(self, board, depth, alpha, beta, is_max):
        # Cas terminal
        if board.check_winner(YELLOW):
            return 100000 + depth  # victoire rapide = meilleure
        if board.check_winner(RED):
            return -100000 - depth
        if board.is_full() or depth == 0:
            return self.evaluate(board)

        cols = self.ordered_cols(board)

        if is_max:
            best = -10**9
            for col in cols:
                board.drop_piece(col, YELLOW)
                val = self.minimax(board, depth-1, alpha, beta, False)
                board.undo()
                best = max(best, val)
                alpha = max(alpha, best)
                if alpha >= beta:
                    break  # élagage bêta
            return best
        else:
            best = 10**9
            for col in cols:
                board.drop_piece(col, RED)
                val = self.minimax(board, depth-1, alpha, beta, True)
                board.undo()
                best = min(best, val)
                beta = min(beta, best)
                if alpha >= beta:
                    break  # élagage alpha
            return best

    # ---------- CHOIX DU COUP ----------
    def choose_move(self, board):
        best_score = -10**9
        best_col = None
        self.scores = []

        # Victoire immédiate ?
        for col in self.ordered_cols(board):
            board.drop_piece(col, YELLOW)
            if board.check_winner(YELLOW):
                board.undo()
                self.scores = [(col, 100000)]
                return col
            board.undo()

        # Bloquer victoire adverse immédiate ?
        for col in self.ordered_cols(board):
            board.drop_piece(col, RED)
            if board.check_winner(RED):
                board.undo()
                self.scores = [(col, 99999)]
                return col
            board.undo()

        # Minimax avec alpha-bêta
        for col in self.ordered_cols(board):
            board.drop_piece(col, YELLOW)
            score = self.minimax(board, self.depth - 1, -10**9, 10**9, False)
            board.undo()
            self.scores.append((col, score))
            if score > best_score:
                best_score = score
                best_col = col

        return best_col