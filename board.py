EMPTY = 0
RED = 1
YELLOW = 2

class Board:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.grid = [[EMPTY for _ in range(cols)] for _ in range(rows)]
        self.history = []
        self.winning_cells = []

    def reset(self):
        self.grid = [[EMPTY for _ in range(self.cols)] for _ in range(self.rows)]
        self.history = []
        self.winning_cells = []

    def is_column_full(self, col):
        return self.grid[0][col] != EMPTY

    def is_full(self):
        for row in self.grid:
            if EMPTY in row:
                return False
        return True

    def drop_piece(self, col, player):
        for row in range(self.rows-1, -1, -1):
            if self.grid[row][col] == EMPTY:
                self.grid[row][col] = player
                self.history.append((row, col, player))
                return

    def undo(self):
        if not self.history:
            return
        row, col, _ = self.history.pop()
        self.grid[row][col] = EMPTY
        self.winning_cells = []

    def check_winner(self, player):
        self.winning_cells = []

        # Horizontal
        for r in range(self.rows):
            for c in range(self.cols - 3):
                cells = [(r, c + i) for i in range(4)]
                if all(self.grid[x][y] == player for x, y in cells):
                    self.winning_cells = cells
                    return True

        # Vertical
        for c in range(self.cols):
            for r in range(self.rows - 3):
                cells = [(r + i, c) for i in range(4)]
                if all(self.grid[x][y] == player for x, y in cells):
                    self.winning_cells = cells
                    return True

        # Diagonal \
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
                cells = [(r + i, c + i) for i in range(4)]
                if all(self.grid[x][y] == player for x, y in cells):
                    self.winning_cells = cells
                    return True

        # Diagonal /
        for r in range(3, self.rows):
            for c in range(self.cols - 3):
                cells = [(r - i, c + i) for i in range(4)]
                if all(self.grid[x][y] == player for x, y in cells):
                    self.winning_cells = cells
                    return True

        return False
    def has_winner(self, player):
      # Horizontal
        for r in range(self.rows):
            for c in range(self.cols - 3):
                if all(self.grid[r][c+i] == player for i in range(4)):
                   return True

     # Vertical
        for c in range(self.cols):
           for r in range(self.rows - 3):
               if all(self.grid[r+i][c] == player for i in range(4)):
                return True

     # Diagonale \
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
               if all(self.grid[r+i][c+i] == player for i in range(4)):
                return True

      # Diagonale /
        for r in range(3, self.rows):
            for c in range(self.cols - 3):
                if all(self.grid[r-i][c+i] == player for i in range(4)):
                 return True

        return False