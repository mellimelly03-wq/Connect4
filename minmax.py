from board import RED, YELLOW
class MiniMaxAI:
    def __init__(self, depth):
        self.depth = depth
        self.scores = []

    # ---------- SCORING D'UNE FENÊTRE ----------
    def score_window(self, window):
        score = 0
        if window.count(YELLOW) == 4:
            score += 1000
        elif window.count(YELLOW) == 3 and window.count(0) == 1:
            score += 50
        elif window.count(YELLOW) == 2 and window.count(0) == 2:
            score += 10

        if window.count(RED) == 3 and window.count(0) == 1:
            score -= 80
        elif window.count(RED) == 4:
            score -= 1000

        return score

    # ---------- EVALUATION DU PLATEAU ----------
    def evaluate(self, board):
        score = 0

        # Bonus centre
        center_col = board.cols // 2
        center_count = [board.grid[r][center_col] for r in range(board.rows)].count(YELLOW)
        score += center_count * 6

        # Horizontal
        for r in range(board.rows):
            for c in range(board.cols - 3):
                window = [board.grid[r][c+i] for i in range(4)]
                score += self.score_window(window)

        # Vertical
        for c in range(board.cols):
            for r in range(board.rows - 3):
                window = [board.grid[r+i][c] for i in range(4)]
                score += self.score_window(window)

        # Diagonale \
        for r in range(board.rows - 3):
            for c in range(board.cols - 3):
                window = [board.grid[r+i][c+i] for i in range(4)]
                score += self.score_window(window)

        # Diagonale /
        for r in range(3, board.rows):
            for c in range(board.cols - 3):
                window = [board.grid[r-i][c+i] for i in range(4)]
                score += self.score_window(window)

        return score

    # ---------- MINIMAX ----------
    def minimax(self, board, depth, is_max):
        if depth == 0 or board.is_full():
            return self.evaluate(board)

        if is_max:
            best = -10**9
            for col in range(board.cols):
                if not board.is_column_full(col):
                    board.drop_piece(col, YELLOW)
                    val = self.minimax(board, depth-1, False)
                    board.undo()
                    best = max(best, val)
            return best
        else:
            best = 10**9
            for col in range(board.cols):
                if not board.is_column_full(col):
                    board.drop_piece(col, RED)
                    val = self.minimax(board, depth-1, True)
                    board.undo()
                    best = min(best, val)
            return best

    # ---------- CHOIX DU COUP ----------
    def choose_move(self, board):
        best_score = -10**9
        best_col = None
        self.scores = []

        for col in range(board.cols):
            if not board.is_column_full(col):
                board.drop_piece(col, YELLOW)
                score = self.minimax(board, self.depth - 1, False)
                board.undo()

                self.scores.append((col, score))

                if score > best_score:
                    best_score = score
                    best_col = col

        return best_col