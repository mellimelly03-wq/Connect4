import time
import threading
import tkinter as tk
from tkinter import ttk
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

from board import Board, RED, YELLOW
from minmax import MiniMaxAI
from ai_bdd import AIBaseDeDonnees

# CONFIG
NB_ROWS, NB_COLS = 9, 9
FIREFOX_PATH = r"C:\Users\Melissa\AppData\Local\Mozilla Firefox\firefox.exe"


class PuppeteerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BGA BOT - BDD vs MINIMAX")
        self.root.geometry("400x500")

        self.driver = None
        self.stop_event = threading.Event()
        self.last_move_time = 0

        # UI
        tk.Label(root, text="🤖 SÉLECTION DE L'IA", font=("Arial", 14, "bold")).pack(pady=15)

        self.mode_ia = tk.StringVar(value="MINIMAX")
        ttk.Radiobutton(root, text="Mode Minimax (Calcul pur)", variable=self.mode_ia, value="MINIMAX").pack(anchor="w", padx=50)
        ttk.Radiobutton(root, text="Mode BDD (SQL + Fallback)", variable=self.mode_ia, value="BDD").pack(anchor="w", padx=50)

        tk.Label(root, text="\nProfondeur (si Minimax):").pack()
        self.depth_scale = tk.Scale(root, from_=3, to=8, orient="horizontal")
        self.depth_scale.set(5)
        self.depth_scale.pack()

        self.status = tk.StringVar(value="Statut: Prêt")
        tk.Label(root, textvariable=self.status, fg="blue").pack(pady=20)

        tk.Button(root, text="LANCER FIREFOX", bg="orange", command=self.open_ff).pack(fill="x", padx=50, pady=5)
        self.btn_go = tk.Button(root, text="▶ DÉMARRER L'IA", bg="green", fg="white",
                                state="disabled", command=self.start)
        self.btn_go.pack(fill="x", padx=50, pady=5)
        tk.Button(root, text="⏹ ARRÊTER", bg="red", fg="white", command=self.stop).pack(fill="x", padx=50, pady=5)

    def open_ff(self):
        opts = Options()
        opts.binary_location = FIREFOX_PATH
        self.driver = Firefox(options=opts)
        self.driver.get("https://boardgamearena.com")
        self.btn_go.config(state="normal")

    def start(self):
        self.stop_event.clear()
        threading.Thread(target=self.loop, daemon=True).start()
        self.status.set("Statut: IA en marche...")

    def stop(self):
        self.stop_event.set()
        self.status.set("Statut: IA arrêtée")

    # ─────────────────────────────────────────────
    # FIX 1 : vérifier que c'est vraiment notre tour
    # ─────────────────────────────────────────────
    def is_my_turn(self):
        try:
            # Méthode principale : panneau du joueur courant marqué "active"
            active = self.driver.find_elements(
                By.CSS_SELECTOR, ".current-player-board.active-player"
            )
            if active:
                return True

            # Méthode de secours : texte du titre de statut BGA
            titles = self.driver.find_elements(By.CSS_SELECTOR, "#pagemaintitletext")
            if titles:
                txt = titles[0].text.lower()
                if "your turn" in txt or "votre tour" in txt:
                    return True
                if "must play" in txt or "doit jouer" in txt:
                    return False

            # Dernier recours : présence de coups possibles
            possible = self.driver.find_elements(By.CSS_SELECTOR, ".possibleMove")
            return len(possible) > 0

        except:
            return False

    # ─────────────────────────────────────────────
    # FIX 2 : reconstruire board.history depuis BGA
    # ─────────────────────────────────────────────
    def build_board_with_history(self):
        """
        Relit la grille BGA et rejoue tous les coups via drop_piece()
        pour que board.history soit rempli correctement.
        C'est ce que AIBaseDeDonnees utilise pour interroger la BDD.

        Stratégie de reconstruction de l'ordre :
        - Dans chaque colonne, les pions du bas ont été joués avant ceux du haut.
        - On trie tous les pions par (rang_dans_colonne, colonne) pour approcher
          l'ordre chronologique réel, puis on les rejoue en alternant les couleurs.
        """
        discs = self.driver.execute_script("""
            let out = [];
            document.querySelectorAll('.disc').forEach(d => {
                let parts = d.parentElement.id.split('_');
                out.push({
                    c: parseInt(parts[1]) - 1,
                    r: parseInt(parts[2]) - 1,
                    color: d.className.includes('ff0000') ? 1 : 2
                });
            });
            return out;
        """)

        if not discs:
            return Board(NB_ROWS, NB_COLS)

        # Calcul du rang de chaque pion dans sa colonne (0 = le plus bas = joué en 1er)
        col_counter = {}
        # Trier par row décroissant = le plus bas d'abord
        discs_sorted = sorted(discs, key=lambda d: -d['r'])
        ordered = []
        for d in discs_sorted:
            rank = col_counter.get(d['c'], 0)
            col_counter[d['c']] = rank + 1
            ordered.append({'c': d['c'], 'color': d['color'], 'rank': rank})

        # Tri global par rang puis colonne pour approcher l'ordre chronologique
        ordered.sort(key=lambda d: (d['rank'], d['c']))

        # Rejouer tous les coups pour peupler board.history
        b = Board(NB_ROWS, NB_COLS)
        for d in ordered:
            try:
                b.drop_piece(d['c'], d['color'])
            except Exception:
                pass  # colonne pleine ou état incohérent

        coups = [col for (_, col, _) in b.history]
        print(f"[BOT] board.history reconstruit ({len(coups)} coups) : {coups}")
        return b

    # ─────────────────────────────────────────────
    # BOUCLE PRINCIPALE
    # ─────────────────────────────────────────────
    def loop(self):
        # Détection couleur du joueur
        ma_couleur = YELLOW
        try:
            p = self.driver.find_element(By.CSS_SELECTOR, ".current-player-board")
            if "ff0000" in p.get_attribute("innerHTML").lower():
                ma_couleur = RED
        except:
            pass

        couleur_nom = "ROUGE" if ma_couleur == RED else "JAUNE"
        print(f"[BOT] Couleur détectée : {couleur_nom}")

        while not self.stop_event.is_set():
            try:
                possible_moves = self.driver.find_elements(By.CSS_SELECTOR, ".possibleMove")

                # FIX 1 : double vérification du tour avant tout
                if len(possible_moves) == 0 or not self.is_my_turn():
                    time.sleep(1)
                    continue

                # Anti-spam : délai minimum entre deux coups
                now = time.time()
                if now - self.last_move_time < 2.5:
                    time.sleep(0.5)
                    continue

                # FIX 2 : board avec history correct pour la BDD
                b = self.build_board_with_history()

                col = None

                if self.mode_ia.get() == "BDD":
                    ia = AIBaseDeDonnees(couleur=couleur_nom)
                    col = ia.choisir_coup(b)
                    print(f"[BOT] BDD choisit colonne : {col}")
                else:
                    ia = MiniMaxAI(depth=self.depth_scale.get())
                    col = ia.choose_move(b, ma_couleur)
                    print(f"[BOT] Minimax choisit colonne : {col}")

                if col is not None:
                    target = self.driver.find_element(
                        By.CSS_SELECTOR, f"[id^='square_{col + 1}_'].possibleMove"
                    )
                    self.driver.execute_script("arguments[0].click();", target)
                    self.last_move_time = time.time()
                    print(f"[BOT] Clic colonne {col + 1}")
                    time.sleep(2)

            except Exception as e:
                print(f"[BOT] Erreur : {e}")

            time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    app = PuppeteerApp(root)
    root.mainloop()