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
NB_ROWS, NB_COLS    = 9, 9
FIREFOX_PATH        = r"C:\Users\Melissa\AppData\Local\Mozilla Firefox\firefox.exe"

POLL_INTERVAL       = 0.8    # délai entre deux vérifications du tour
STABLE_INTERVAL     = 0.35   # délai entre deux lectures de grille
STABLE_READS        = 2      # lectures identiques pour valider la grille
MAX_WAIT_DISC       = 20.0   # timeout max pour attendre le pion adverse (augmenté)
MAX_RETRIES         = 3      # nombre max de tentatives de clic sur une colonne


class PuppeteerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BGA BOT - BDD vs MINIMAX")
        self.root.geometry("400x560")

        self.driver       = None
        self.stop_event   = threading.Event()
        self._last_click_col = None   # dernière colonne cliquée
        self._click_count    = 0      # nb de fois qu'on a cliqué cette colonne

        tk.Label(root, text="🤖 SÉLECTION DE L'IA", font=("Arial", 14, "bold")).pack(pady=15)

        self.mode_ia = tk.StringVar(value="MINIMAX")
        ttk.Radiobutton(root, text="Mode Minimax (Calcul pur)",
                        variable=self.mode_ia, value="MINIMAX").pack(anchor="w", padx=50)
        ttk.Radiobutton(root, text="Mode BDD (SQL + Fallback)",
                        variable=self.mode_ia, value="BDD").pack(anchor="w", padx=50)

        tk.Label(root, text="\nProfondeur (si Minimax):").pack()
        self.depth_scale = tk.Scale(root, from_=3, to=8, orient="horizontal")
        self.depth_scale.set(6)
        self.depth_scale.pack()

        self.status     = tk.StringVar(value="Statut: Prêt")
        self.info_label = tk.StringVar(value="")
        tk.Label(root, textvariable=self.status,     fg="blue").pack(pady=6)
        tk.Label(root, textvariable=self.info_label, fg="gray",
                 font=("Arial", 9)).pack()

        tk.Button(root, text="LANCER FIREFOX", bg="orange",
                  command=self.open_ff).pack(fill="x", padx=50, pady=5)
        self.btn_go = tk.Button(root, text="▶ DÉMARRER L'IA", bg="green",
                                fg="white", state="disabled", command=self.start)
        self.btn_go.pack(fill="x", padx=50, pady=5)
        tk.Button(root, text="⏹ ARRÊTER", bg="red", fg="white",
                  command=self.stop).pack(fill="x", padx=50, pady=5)

    # ── UI thread-safe ───────────────────────────
    def _ui(self, var, text):
        self.root.after(0, lambda: var.set(text))

    def open_ff(self):
        opts = Options()
        opts.binary_location = FIREFOX_PATH
        self.driver = Firefox(options=opts)
        self.driver.get("https://boardgamearena.com")
        self.btn_go.config(state="normal")

    def start(self):
        self.stop_event.clear()
        self._last_click_col = None
        self._click_count    = 0
        threading.Thread(target=self.loop, daemon=True).start()
        self._ui(self.status, "Statut: IA en marche...")

    def stop(self):
        self.stop_event.set()
        self._ui(self.status, "Statut: arrêtée")

    # ── Lecture des disques ──────────────────────
    def _read_discs(self):
        return self.driver.execute_script("""
            let out = [];
            document.querySelectorAll('.disc').forEach(d => {
                let p = d.parentElement.id.split('_');
                if (p.length >= 3) {
                    let c = parseInt(p[1]) - 1;
                    let r = parseInt(p[2]) - 1;
                    if (!isNaN(c) && !isNaN(r) && c >= 0 && r >= 0)
                        out.push({ c, r, color: d.className.includes('ff0000') ? 1 : 2 });
                }
            });
            return out;
        """)

    def _count_discs(self):
        return len(self._read_discs())

    def _wait_stable(self, max_wait=5.0):
        """Attend une grille stable (STABLE_READS lectures identiques)."""
        prev, count, waited = None, 0, 0.0
        while waited < max_wait:
            try:
                discs = self._read_discs()
                snap  = frozenset((d['c'], d['r'], d['color']) for d in discs)
                if snap == prev:
                    count += 1
                    if count >= STABLE_READS:
                        return discs
                else:
                    count, prev = 0, snap
            except Exception as e:
                print(f"[BOT] lecture: {e}")
            time.sleep(STABLE_INTERVAL)
            waited += STABLE_INTERVAL
        return self._read_discs()

    # ── Attendre que l'adversaire ait joué ───────
    def _wait_for_opponent(self, nb_discs_avant):
        """
        Attend que le nombre total de pions soit >= nb_discs_avant + 2.
        (notre pion + le pion adverse)
        Retourne le nouveau nombre de disques, ou -1 si timeout/stop.
        """
        target = nb_discs_avant + 2
        waited = 0.0
        self._ui(self.status, f"Statut: attente adversaire ({nb_discs_avant+1}→{target} pions)...")

        while waited < MAX_WAIT_DISC:
            if self.stop_event.is_set():
                return -1
            try:
                n = self._count_discs()
                self._ui(self.info_label, f"Pions: {n} / attendu: {target}")

                if n >= target:
                    # Laisser la grille se stabiliser
                    self._wait_stable(max_wait=1.5)
                    return n

                # Si après 8 secondes on n'a même pas notre propre pion,
                # le clic a peut-être raté → on signale un problème
                if waited > 8.0 and n < nb_discs_avant + 1:
                    print(f"[BOT] Notre pion n'est pas apparu après 8s, clic raté ?")
                    return -2  # code spécial : clic raté

            except Exception as e:
                print(f"[BOT] wait_opponent: {e}")

            time.sleep(0.5)
            waited += 0.5

        # Timeout : partie peut-être terminée
        print("[BOT] Timeout attente adversaire — partie terminée ?")
        return -1

    # ── Détection du tour ────────────────────────
    def _is_my_turn(self):
        try:
            for pat in ["merci de patienter", "please wait",
                        "n'est pas votre tour", "is not your turn",
                        "must play", "doit jouer"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, "#pagemaintitletext")
                if els and pat in els[0].text.lower():
                    self._ui(self.status, "Statut: tour adversaire")
                    return False

            possible = self.driver.find_elements(By.CSS_SELECTOR, ".possibleMove")
            if not possible:
                self._ui(self.status, "Statut: attente BGA...")
                return False

            self._ui(self.status, "Statut: MON TOUR ✓")
            return True
        except:
            return False

    # ── Construction du board ────────────────────
    def _board_minimax(self, discs):
        b = Board(NB_ROWS, NB_COLS)
        for d in discs:
            if 0 <= d['r'] < NB_ROWS and 0 <= d['c'] < NB_COLS:
                b.grid[d['r']][d['c']] = d['color']
        self._ui(self.info_label, f"Grille: {len(discs)} pions")
        return b

    def _board_bdd(self, discs):
        if not discs:
            return Board(NB_ROWS, NB_COLS)
        col_counter = {}
        ordered = []
        for d in sorted(discs, key=lambda x: -x['r']):
            rank = col_counter.get(d['c'], 0)
            col_counter[d['c']] = rank + 1
            ordered.append({**d, 'rank': rank})
        ordered.sort(key=lambda x: (x['rank'], x['c']))
        b = Board(NB_ROWS, NB_COLS)
        for d in ordered:
            try:
                b.drop_piece(d['c'], d['color'])
            except Exception:
                pass
        coups = [c for (_, c, _) in b.history]
        print(f"[BOT] History BDD ({len(coups)}): {coups}")
        return b

    # ── Clic sur une colonne ─────────────────────
    def _click_col(self, col):
        """
        Cherche les cases jouables et clique sur celle de la colonne voulue.
        Retourne True si le clic a eu lieu, False sinon.
        """
        targets = self.driver.find_elements(By.CSS_SELECTOR, ".possibleMove")
        col_targets = [t for t in targets
                       if f"_{col + 1}_" in (t.get_attribute("id") or "")]

        if not col_targets:
            print(f"[BOT] Col {col+1} indisponible")
            return False

        self.driver.execute_script("arguments[0].click();", col_targets[0])
        print(f"[BOT] Clic col {col+1}")
        return True

    # ── Boucle principale ────────────────────────
    def loop(self):
        # Détection couleur
        ma_couleur = YELLOW
        try:
            p = self.driver.find_element(By.CSS_SELECTOR, ".current-player-board")
            if "ff0000" in p.get_attribute("innerHTML").lower():
                ma_couleur = RED
        except:
            pass
        couleur_nom = "ROUGE" if ma_couleur == RED else "JAUNE"
        print(f"[BOT] Couleur: {couleur_nom}")

        nb_discs_au_clic = -1  # nombre de pions au moment de notre dernier clic

        while not self.stop_event.is_set():
            try:
                # ── Garde anti-rebouclage ─────────────────────────────────────
                # Si on vient de cliquer, on vérifie que l'adversaire a bien joué
                # avant de lancer un nouveau calcul
                if nb_discs_au_clic >= 0:
                    n = self._count_discs()
                    if n < nb_discs_au_clic + 2:
                        # Notre pion est peut-être là (+1) mais pas encore l'adversaire
                        # On attend sans recalculer
                        time.sleep(POLL_INTERVAL)
                        continue
                    else:
                        # Adversaire a joué → on reset le garde
                        nb_discs_au_clic = -1

                # 1. Attendre notre tour
                if not self._is_my_turn():
                    time.sleep(POLL_INTERVAL)
                    continue

                # 2. Lire grille stable
                self._ui(self.status, "Statut: lecture grille...")
                discs = self._wait_stable()
                nb_avant = len(discs)

                # 3. Re-vérifier le tour
                if not self._is_my_turn():
                    time.sleep(POLL_INTERVAL)
                    continue

                # 4. Construire board + calculer coup
                self._ui(self.status, "Statut: calcul IA...")
                col = None

                if self.mode_ia.get() == "BDD":
                    b   = self._board_bdd(discs)
                    ia  = AIBaseDeDonnees(couleur=couleur_nom)
                    col = ia.choisir_coup(b)
                    print(f"[BOT] BDD → col {col}")
                else:
                    b   = self._board_minimax(discs)
                    ia  = MiniMaxAI(depth=self.depth_scale.get())
                    col = ia.choose_move(b, ma_couleur)
                    print(f"[BOT] Minimax → col {col}")

                if col is None:
                    self._ui(self.status, "Statut: aucun coup trouvé")
                    time.sleep(1)
                    continue

                # 5. Vérification finale avant clic
                if not self._is_my_turn():
                    time.sleep(POLL_INTERVAL)
                    continue

                # 6. Tentative de clic (avec retry sur colonne adjacente si bloqué)
                clique = False
                cols_a_essayer = [col]

                # Si la colonne est bloquée, essayer les voisines par ordre de proximité
                center = NB_COLS // 2
                for delta in range(1, NB_COLS):
                    for signe in [1, -1]:
                        c = col + delta * signe
                        if 0 <= c < NB_COLS and c not in cols_a_essayer:
                            cols_a_essayer.append(c)

                for c_try in cols_a_essayer:
                    if self._click_col(c_try):
                        clique = True
                        nb_discs_au_clic = nb_avant
                        break
                    time.sleep(0.3)

                if not clique:
                    print("[BOT] Aucune colonne disponible, on attend...")
                    time.sleep(1)
                    continue

                # 7. Attendre que l'adversaire joue
                result = self._wait_for_opponent(nb_avant)

                if result == -1:
                    # Timeout → partie peut-être finie, on reset le garde
                    nb_discs_au_clic = -1
                    self._ui(self.status, "Statut: attente fin de partie...")
                    time.sleep(2)
                    continue
                elif result == -2:
                    # Clic raté → on réessaie au prochain tour
                    nb_discs_au_clic = -1
                    print("[BOT] Clic raté détecté, on réessaie")
                    time.sleep(0.5)
                    continue
                else:
                    print(f"[BOT] Reprise ({result} pions)")

            except Exception as e:
                print(f"[BOT] Erreur: {e}")
                nb_discs_au_clic = -1
                time.sleep(1)

            time.sleep(0.3)


if __name__ == "__main__":
    root = tk.Tk()
    app = PuppeteerApp(root)
    root.mainloop()