import tkinter as tk
import json
from tkinter import messagebox
from board import Board, RED, YELLOW
from game import Game
from minmax import MiniMaxAI
from game_repository import save_game_from_board, get_parties

CELL = 55

class Connect4UI:
    def __init__(self, root):
        self.root = root
        self.root.title("Connect4")

        # Charger config
        with open("config.json", "r") as f:
            cfg = json.load(f)["config"]

        self.rows     = cfg["rows"]
        self.cols     = cfg["cols"]
        self.starting = RED if cfg["starting_color"] == "RED" else YELLOW

        self.board = Board(self.rows, self.cols)
        self.game  = None

        # Label info
        self.label = tk.Label(root, text="Choisis un mode")
        self.label.pack()

        # Boutons de jeu
        frame = tk.Frame(root)
        frame.pack()

        tk.Button(frame, text="2 Joueurs",
                  command=lambda: self.start("2players")).pack(side=tk.LEFT)
        tk.Button(frame, text="Humain vs Robot",
                  command=lambda: self.start("human_vs_ai")).pack(side=tk.LEFT)
        tk.Button(frame, text="Robot vs Robot",
                  command=lambda: self.start("ai_vs_ai")).pack(side=tk.LEFT)
        tk.Button(frame, text="Undo",    command=self.undo).pack(side=tk.LEFT)
        tk.Button(frame, text="Restart", command=self.restart).pack(side=tk.LEFT)
        tk.Button(frame, text="Save",    command=self.save).pack(side=tk.LEFT)
        tk.Button(frame, text="Pause",   command=self.pause).pack(side=tk.LEFT)
        tk.Button(frame, text="Resume",  command=self.resume).pack(side=tk.LEFT)

        # ── Boutons IA ──────────────────────────────────────
        frame2 = tk.Frame(root)
        frame2.pack(pady=4)

        tk.Button(frame2, text="IA Aléatoire",
                  command=lambda: self.start("human_vs_ai", "random"),
                  bg="#d0d0ff").pack(side=tk.LEFT, padx=3)

        tk.Button(frame2, text="IA MiniMax",
                  command=lambda: self.start("human_vs_ai", "minimax"),
                  bg="#ffd0a0").pack(side=tk.LEFT, padx=3)

        tk.Button(frame2, text="🧠 IA Base de Données",
                  command=lambda: self.start("human_vs_ai", "bdd"),
                  bg="#a0ffa0").pack(side=tk.LEFT, padx=3)   # ← NOUVEAU
        # ────────────────────────────────────────────────────

        # Réglage profondeur MiniMax
        depth_frame = tk.Frame(root)
        depth_frame.pack(pady=5)
        tk.Label(depth_frame, text="Profondeur MiniMax :").pack(side=tk.LEFT, padx=5)
        self.depth_var = tk.IntVar(value=3)
        tk.OptionMenu(depth_frame, self.depth_var, 1, 2, 3, 4, 5, 6).pack(side=tk.LEFT)
        tk.Button(depth_frame, text="Appliquer", command=self.update_depth).pack(side=tk.LEFT)

        # Liste des parties sauvegardées
        self.saved_listbox = tk.Listbox(root, height=5)
        self.saved_listbox.pack()
        self.saved_listbox.bind("<<ListboxSelect>>", self.load_selected_game)

        # Canvas plateau
        self.canvas = tk.Canvas(root,
                                width=self.cols * CELL,
                                height=self.rows * CELL + 20,
                                bg="blue")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.click)

        self.update_saved_list()

    # ── Démarrer une partie ──────────────────────────────────
    def start(self, mode, ai_type="random"):
        self.board.reset()
        self.game          = Game(self.board, self.starting, mode)
        self.game.ai_type  = ai_type

        if ai_type == "minimax":
            self.game.ai.depth = self.depth_var.get()

        # La couleur de l'IA BDD dépend de qui commence
        # Si le joueur humain est ROUGE (starting), l'IA joue JAUNE
        self.game.ai_bdd.couleur = "JAUNE" if self.starting == RED else "ROUGE"

        self.draw()
        self.update_label()

        if mode == "ai_vs_ai" or (mode == "human_vs_ai" and self.game.current_player != self.starting):
            self.root.after(300, self.ai_play)

    # ── Undo ────────────────────────────────────────────────
    def undo(self):
        if self.game:
            self.game.undo()
            self.draw()
            self.update_label()

    # ── Restart ─────────────────────────────────────────────
    def restart(self):
        if self.game:
            self.game.restart()
            self.draw()
            self.update_label()

    # ── Save ────────────────────────────────────────────────
    def save(self):
        if not self.game:
            return
        result = save_game_from_board(self.game)
        if result is None:
            return
        if result["status"] == "OK":
            self.update_saved_list()
            messagebox.showinfo("Sauvegarde",
                f"✅ Partie enregistrée (ID {result['partie_id']})")
        elif result["status"] == "EXISTE":
            messagebox.showwarning("Doublon",
                f"⚠️ Doublon/symétrie de la partie ID {result['partie_id']}")

    # ── Pause / Resume ───────────────────────────────────────
    def pause(self):
        if self.game:
            self.game.pause()
            self.label.config(text="⏸ Partie en pause")

    def resume(self):
        if self.game:
            self.game.resume()
            self.update_label()
            if self.game.mode == "ai_vs_ai" or (
                self.game.mode == "human_vs_ai" and
                self.game.current_player != self.starting
            ):
                self.root.after(300, self.ai_play)

    # ── Charger une partie depuis la listbox ─────────────────
    def load_selected_game(self, event):
        selection = self.saved_listbox.curselection()
        if selection:
            index    = selection[0]
            parties  = get_parties()
            partie_id = parties[index]["id"]
            from game_repository import load_game
            game = load_game(partie_id)
            if game:
                self.game  = game
                self.board = game.board
                self.draw()
                self.update_label()
                self.label.config(text=f"✅ Partie ID {partie_id} chargée")
            else:
                self.label.config(text=f"⚠️ Impossible de charger {partie_id}")

    # ── Clic sur le plateau ──────────────────────────────────
    def click(self, event):
        if not self.game or self.game.game_over or self.game.paused:
            return
        if self.game.mode != "2players" and self.game.current_player != self.starting:
            return

        col = event.x // CELL
        if self.board.is_column_full(col):
            self.label.config(text="Colonne pleine !")
            return

        self.game.play_turn(col)
        self.draw()
        if not self.board.winning_cells and self.board.is_full():
            self.game.game_over = True
        self.update_label()

        if (self.game.mode == "human_vs_ai" and
                self.game.current_player != self.starting and
                not self.game.game_over):
            self.root.after(300, self.ai_play)

    # ── IA joue ──────────────────────────────────────────────
    def ai_play(self):
        if not self.game or self.game.game_over or self.game.paused:
            return

        # Afficher le nom de l'IA en cours
        noms = {"random": "Aléatoire", "minimax": "MiniMax", "bdd": "Base de Données"}
        self.label.config(text=f"🤖 {noms.get(self.game.ai_type, '')} réfléchit...")
        self.root.update()

        col = self.game.ai_move()

        if col is None:
            self.label.config(text="Match nul !")
            self.game.game_over = True
            return

        self.game.play_turn(col)
        self.draw()
        if not self.board.winning_cells and self.board.is_full():
            self.game.game_over = True
        self.update_label()

        # Afficher scores MiniMax
        if self.game.ai_type == "minimax" and self.game.ai.scores:
            for c, score in self.game.ai.scores:
                x = c * CELL + CELL // 2
                y = self.rows * CELL + 10
                self.canvas.create_text(x, y, text=str(score),
                                        fill="white", font=("Arial", 12, "bold"))

        if self.game.mode == "ai_vs_ai" and not self.game.game_over:
            self.root.after(300, self.ai_play)
        elif (self.game.mode == "human_vs_ai" and
              self.game.current_player != self.starting and
              not self.game.game_over):
            self.root.after(300, self.ai_play)

    # ── Dessin du plateau ────────────────────────────────────
    def draw(self):
        self.canvas.delete("all")
        for r in range(self.rows):
            for c in range(self.cols):
                x1, y1 = c * CELL,        r * CELL
                x2, y2 = x1 + CELL,       y1 + CELL
                color   = "white"
                if self.board.grid[r][c] == RED:
                    color = "red"
                elif self.board.grid[r][c] == YELLOW:
                    color = "yellow"
                outline = "green" if (r, c) in self.board.winning_cells else "black"
                self.canvas.create_oval(x1+5, y1+5, x2-5, y2-5,
                                        fill=color, outline=outline, width=3)

        if self.game and self.game.ai_type == "minimax" and self.game.ai.scores:
            for col, score in self.game.ai.scores:
                x = col * CELL + CELL // 2
                y = self.rows * CELL + 10
                self.canvas.create_text(x, y, text=str(score),
                                        fill="white", font=("Arial", 12, "bold"))

    # ── Label ────────────────────────────────────────────────
    def update_label(self):
        if not self.game:
            return
        if self.game.game_over:
            if self.board.check_winner(RED):
                self.label.config(text="🔴 Victoire Rouge !")
            elif self.board.check_winner(YELLOW):
                self.label.config(text="🟡 Victoire Jaune !")
            elif self.board.is_full():
                self.label.config(text="Match nul !")
            else:
                self.label.config(text="Partie terminée")
        else:
            self.label.config(
                text="Tour 🔴 Rouge" if self.game.current_player == RED else "Tour 🟡 Jaune"
            )

    # ── Liste parties sauvegardées ───────────────────────────
    def update_saved_list(self):
        self.saved_listbox.delete(0, tk.END)
        for p in get_parties():
            self.saved_listbox.insert(
                tk.END,
                f"ID:{p['id']} - {p['mode']} - {p['statut']}"
            )

    # ── Profondeur MiniMax ───────────────────────────────────
    def update_depth(self):
        if self.game and self.game.ai_type == "minimax":
            self.game.ai.depth = self.depth_var.get()
            self.label.config(text=f"Profondeur : {self.depth_var.get()}")