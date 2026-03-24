from board import RED, YELLOW

class MiniMaxAI:
    def __init__(self, depth=5): # Profondeur 5 recommandée pour le 9x9
        self.depth = depth
        self.my_color = YELLOW
        self.opp_color = RED

    def score_window(self, window, color):
        opp = RED if color == YELLOW else YELLOW
        score = 0
        
        # --- ATTAQUE ---
        if window.count(color) == 4:
            return 1000000 # Victoire immédiate
        elif window.count(color) == 3 and window.count(0) == 1:
            score += 5000
        elif window.count(color) == 2 and window.count(0) == 2:
            score += 500

        # --- DÉFENSE (Priorité de survie) ---
        if window.count(opp) == 3 and window.count(0) == 1:
            score -= 80000  # Bloquer 3 pions adverses est plus important que tout
        elif window.count(opp) == 2 and window.count(0) == 2:
            score -= 1000
            
        return score

    def evaluate(self, board):
        score = 0
        # Bonus centre (Col 5 sur un plateau de 9)
        center_col = board.cols // 2
        center_array = [board.grid[r][center_col] for r in range(board.rows)]
        score += center_array.count(self.my_color) * 100
        score -= center_array.count(self.opp_color) * 100

        # On score toutes les directions
        # Horizontal
        for r in range(board.rows):
            for c in range(board.cols - 3):
                window = [board.grid[r][c+i] for i in range(4)]
                score += self.score_window(window, self.my_color)
        # Vertical
        for c in range(board.cols):
            for r in range(board.rows - 3):
                window = [board.grid[r+i][c] for i in range(4)]
                score += self.score_window(window, self.my_color)
        # Diagonale \
        for r in range(board.rows - 3):
            for c in range(board.cols - 3):
                window = [board.grid[r+i][c+i] for i in range(4)]
                score += self.score_window(window, self.my_color)
        # Diagonale /
        for r in range(3, board.rows):
            for c in range(board.cols - 3):
                window = [board.grid[r-i][c+i] for i in range(4)]
                score += self.score_window(window, self.my_color)
        return score

    def minimax(self, board, depth, alpha, beta, is_max):
        # Vérification rapide des victoires
        if board.check_winner(self.my_color): return 2000000 + depth
        if board.check_winner(self.opp_color): return -2000000 - depth
        if board.is_full() or depth == 0: return self.evaluate(board)

        valid_cols = self.ordered_cols(board)
        if is_max:
            value = -float('inf')
            for col in valid_cols:
                board.drop_piece(col, self.my_color)
                value = max(value, self.minimax(board, depth-1, alpha, beta, False))
                board.undo()
                alpha = max(alpha, value)
                if alpha >= beta: break # Élagage
            return value
        else:
            value = float('inf')
            for col in valid_cols:
                board.drop_piece(col, self.opp_color)
                value = min(value, self.minimax(board, depth-1, alpha, beta, True))
                board.undo()
                beta = min(beta, value)
                if alpha >= beta: break # Élagage
            return value

    def ordered_cols(self, board):
        center = board.cols // 2
        cols = [c for c in range(board.cols) if not board.is_column_full(c)]
        cols.sort(key=lambda c: abs(c - center))
        return cols

    def choose_move(self, board, color):
        self.my_color = color
        self.opp_color = RED if color == YELLOW else YELLOW
        best_col = None
        best_score = -float('inf')
        
        # --- AJOUT ICI : On réinitialise les scores ---
        self.scores = [None] * board.cols 

        valid_cols = self.ordered_cols(board)
        if not valid_cols: return None

        # 1. Vérification immédiate

        # 1.5. Bloquer victoire adverse immédiate
        for col in valid_cols:
            board.drop_piece(col, self.opp_color)
            if board.check_winner(self.opp_color):
                self.scores[col] = 999999
                board.undo()
                return col
            board.undo()


        # 2. Lancement Minimax pour chaque colonne
        for col in range(board.cols):
            if board.is_column_full(col):
                self.scores[col] = None # Colonne pleine, pas de score
                continue
                
            board.drop_piece(col, self.my_color)
            # On récupère le score du minimax
            score = self.minimax(board, self.depth - 1, -float('inf'), float('inf'), False)
            board.undo()
            
            # --- AJOUT ICI : On stocke le score pour l'affichage ---
            self.scores[col] = score 

            if score > best_score:
                best_score = score
                best_col = col

        return best_col if best_col is not None else valid_cols[0]