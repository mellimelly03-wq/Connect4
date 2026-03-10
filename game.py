import random
import copy
import json
from board import RED, YELLOW
from minmax import MiniMaxAI
from ai_bdd import AIBaseDeDonnees   # ← nouvelle IA

class Game:
    def __init__(self, board, starting_player, mode):
        self.board          = board
        self.starting_player = starting_player
        self.current_player  = starting_player
        self.mode            = mode   # "2players", "human_vs_ai", "ai_vs_ai"
        self.game_over       = False
        self.paused          = False
        self.ai_type = "random"
        self.ai      = MiniMaxAI(depth=3)
        # ← IA base de données
        # JAUNE par défaut (l'IA joue jaune)
        self.ai_bdd  = AIBaseDeDonnees(couleur="JAUNE")
        self.game_index  = 1
        self.saved_games = []
        try:
            with open("saved_games.json", "r") as f:
                self.saved_games = json.load(f)
        except Exception:
            self.saved_games = []
            
    def restart(self):
        self.board.reset()
        self.current_player = self.starting_player
        self.game_over      = False
        self.game_index    += 1

    def switch_player(self):
        self.current_player = YELLOW if self.current_player == RED else RED

    def play_turn(self, col):
        if self.game_over or self.paused:
            return None
        if self.board.is_column_full(col):
            return None
        self.board.drop_piece(col, self.current_player)
        if self.board.check_winner(self.current_player):
            self.game_over = True
            return self.current_player
        self.switch_player()
        return None
    
    def undo(self):
        if not self.board.history:
            return
        self.board.undo()
        self.switch_player()
        self.game_over = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def random_move(self):
        valides = [c for c in range(self.board.cols) if not self.board.is_column_full(c)]
        return random.choice(valides) if valides else None
    
    def save_game(self):
        state = {
            "grid":           copy.deepcopy(self.board.grid),
            "history":        copy.deepcopy(self.board.history),
            "current_player": self.current_player,
            "winner":         self.game_over
        }
        self.saved_games.append(state)
        with open("saved_games.json", "w") as f:
            json.dump(self.saved_games, f)

    def load_game(self, index):
        if index < 0 or index >= len(self.saved_games):
            return
        state = self.saved_games[index]
        self.board.grid          = copy.deepcopy(state["grid"])
        self.board.history       = copy.deepcopy(state["history"])
        self.current_player      = state["current_player"]
        self.game_over           = state["winner"]
        self.board.winning_cells = []
        
    def ai_move(self):
        if self.ai_type == "random":
            return self.random_move()
        elif self.ai_type == "minimax":
            return self.ai.choose_move(self.board)
        elif self.ai_type == "bdd":                        # ← nouveau
            return self.ai_bdd.choisir_coup(self.board)