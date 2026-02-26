import tkinter as tk
from tkinter import ttk, messagebox
import time
import traceback
import logging
import hashlib
import re

from selenium.webdriver import Firefox
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

from database import get_connection


# =============================
# LOGGING
# =============================
logging.basicConfig(
    filename="bga.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)


# =============================
# NETTOYAGE BDD AU DEMARRAGE
# Supprime les parties BGA sans coups (evite les faux positifs doublon)
# =============================
def nettoyer_parties_vides():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM partie
            WHERE source LIKE 'bga_%'
            AND id NOT IN (SELECT DISTINCT partie_id FROM coup)
        """)
        nb = cur.rowcount
        conn.commit()
        conn.close()
        if nb > 0:
            logging.info(f"Nettoyage : {nb} partie(s) BGA vide(s) supprimee(s)")
    except Exception:
        logging.warning(f"Nettoyage BDD : {traceback.format_exc()}")


# =============================
# FONCTIONS BDD
# =============================
def hash_coups(coups):
    return hashlib.md5(''.join(map(str, coups)).encode()).hexdigest()


def hash_miroir(coups, nb_cols=9):
    return hashlib.md5(''.join(map(str, [nb_cols - 1 - c for c in coups])).encode()).hexdigest()


def sauvegarder_partie(table_id, coups):
    """
    Insere la partie en BDD si elle n'est pas un doublon ou une symetrie.
    Retourne un message de statut affiche dans le tableau.

    Ordre de verification :
      1. La table BGA est-elle deja en base (source bga_XXXXX) ?
         -> Doublon/symetrie de #ID
      2. Les coups sont-ils vides (partie incomplete) ?
         -> Ignoree (partie incomplete)
      3. Hash normal ou miroir deja present (doublon/symetrie par hash) ?
         -> Doublon/symetrie de #ID
      4. Sinon -> insertion et Sauvegardee
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Deja enregistree via source BGA
    cur.execute("SELECT id FROM partie WHERE source = %s", (f"bga_{table_id}",))
    existant_source = cur.fetchone()
    if existant_source:
        conn.close()
        return f"\u26a0\ufe0f Doublon/symetrie de #{existant_source[0]}"

    # 2. Partie sans coups = abandonnee ou incomplete
    if not coups:
        conn.close()
        return "\u23ed\ufe0f Ignoree (partie incomplete ou abandonnee)"

    h = hash_coups(coups)
    hm = hash_miroir(coups)

    # 3. Doublon exact ou symetrique via hash
    cur.execute(
        "SELECT id FROM partie WHERE hash_partie = %s OR hash_partie = %s",
        (h, hm)
    )
    existant = cur.fetchone()
    if existant:
        conn.close()
        return f"\u26a0\ufe0f Doublon/symetrie de #{existant[0]}"

    # 4. Insertion de la partie
    cur.execute("""
        INSERT INTO partie (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_partie, source, confiance)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, ("bga", "humain", "TERMINE", 6, 9, "ROUGE", h, f"bga_{table_id}", 1))
    conn.commit()
    pid = cur.lastrowid

    # Insertion des coups
    couleur = "ROUGE"
    for i, col in enumerate(coups, start=1):
        cur.execute(
            "INSERT INTO coup (partie_id, numero, couleur, colonne) VALUES (%s,%s,%s,%s)",
            (pid, i, couleur, col)
        )
        couleur = "JAUNE" if couleur == "ROUGE" else "ROUGE"

    conn.commit()
    conn.close()
    logging.info(f"Partie bga_{table_id} sauvegardee -> id {pid}, {len(coups)} coups")
    return f"\u2705 Sauvegardee (ID #{pid})"


# =============================
# EXTRACTION DES COUPS
# =============================
def extraire_coups_depuis_page(driver, table_id):
    """
    Visite la page de la partie et extrait les coups.

    Strategie :
      1. Charge la page table?table=XXXXX
      2. Tente de cliquer sur "Revoir la partie" (pages recentes BGA)
      3. Lit #gamelogs (recentes), sinon body.text entier (anciennes)
      4. Extrait les coups via patterns multilingues (base 1 -> base 0)
    """
    try:
        driver.get(f"https://boardgamearena.com/table?table={table_id}")
        time.sleep(3)

        # Cliquer sur "Revoir la partie" pour acceder au replay
        try:
            btn_replay = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    '//a[contains(text(),"Revoir") or contains(text(),"Review") or contains(text(),"Replay")]'
                ))
            )
            btn_replay.click()
            time.sleep(3)
        except Exception:
            pass  # Bouton absent -> on essaie quand meme de lire les coups

        # Lire le texte : #gamelogs en priorite, sinon body complet
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.find_element(By.ID, "gamelogs").text.strip() != ""
            )
            texte = driver.find_element(By.ID, "gamelogs").text
        except Exception:
            # Page ancienne BGA sans #gamelogs -> lire le body entier
            texte = driver.find_element(By.TAG_NAME, "body").text

        # Patterns multilingues BGA (base 1 -> base 0)
        patterns = [
            r'place un pion dans la colonne (\d+)',   # francais
            r'plays in column (\d+)',                  # anglais
            r'speelt in kolom (\d+)',                  # neerlandais
            r'spielt in Spalte (\d+)',                 # allemand
            r'juega en la columna (\d+)',              # espagnol
            r'gioca nella colonna (\d+)',              # italien
            r'jogar na coluna (\d+)',                  # portugais
        ]

        coups = []
        for pattern in patterns:
            matches = re.findall(pattern, texte, re.IGNORECASE)
            if matches:
                coups = [int(c) - 1 for c in matches]
                break

        logging.info(f"Table {table_id} : {len(coups)} coups extraits")
        return coups

    except Exception:
        logging.warning(f"Table {table_id} : extraction echouee\n{traceback.format_exc()}")
        return []


# =============================
# INTERFACE TKINTER
# =============================
class BGAApp:

    def __init__(self, root):
        self.root = root
        self.root.title("BGA - Puissance 4 Scraper")
        self.root.geometry("950x620")
        self.driver = None
        self.connected = False

        # Nettoyer les parties vides au demarrage
        nettoyer_parties_vides()

        # =============================
        # UI
        # =============================
        self.status = tk.StringVar(value="Statut : Deconnecte")
        self.status_label = tk.Label(root, textvariable=self.status, fg="red", font=("Arial", 12))
        self.status_label.pack(pady=10)

        self.connect_btn = tk.Button(root, text="Connecter a BGA", command=self.connect, width=25)
        self.connect_btn.pack(pady=5)

        frame = tk.Frame(root)
        frame.pack(pady=10)
        tk.Label(frame, text="ID Joueur :").pack(side=tk.LEFT)
        self.player_entry = tk.Entry(frame, width=20)
        self.player_entry.pack(side=tk.LEFT, padx=10)
        self.player_entry.insert(0, "97047639")

        self.scrute_btn = tk.Button(
            root,
            text="Scruter les parties Puissance 4",
            command=self.scrute_tables,
            state=tk.DISABLED,
            width=35
        )
        self.scrute_btn.pack(pady=10)

        # Tableau des resultats
        self.tree = ttk.Treeview(
            root,
            columns=("table", "game", "players", "bdd"),
            show="headings"
        )
        self.tree.heading("table",   text="Table ID")
        self.tree.heading("game",    text="Jeu")
        self.tree.heading("players", text="Joueurs")
        self.tree.heading("bdd",     text="Statut BDD")

        self.tree.column("table",   width=100, anchor="center")
        self.tree.column("game",    width=110, anchor="center")
        self.tree.column("players", width=280, anchor="w")
        self.tree.column("bdd",     width=340, anchor="w")

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.disconnect_btn = tk.Button(root, text="Deconnecter", command=self.disconnect, width=25)
        self.disconnect_btn.pack(pady=5)

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # =============================
    # CONNEXION MANUELLE
    # =============================
    def connect(self):
        try:
            self.status.set("Statut : Lancement de Firefox...")
            self.status_label.config(fg="orange")
            self.root.update()

            options = Options()
            options.binary_location = r"C:\Users\Melissa\AppData\Local\Mozilla Firefox\firefox.exe"
            options.headless = False

            service = Service(GeckoDriverManager().install())
            self.driver = Firefox(service=service, options=options)
            self.driver.set_window_size(1200, 800)

            self.driver.get("https://boardgamearena.com")
            time.sleep(5)

            messagebox.showinfo(
                "Connexion BGA",
                "Connecte-toi MANUELLEMENT a Board Game Arena.\n\n"
                "Une fois connecte, clique sur OK."
            )

            WebDriverWait(self.driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".bga-player-avatar, .player-name"))
            )

            self.connected = True
            self.status.set("Statut : Connecte")
            self.status_label.config(fg="green")
            self.scrute_btn.config(state=tk.NORMAL)

        except Exception:
            logging.error(traceback.format_exc())
            messagebox.showerror("Erreur", "Connexion echouee")
            self.disconnect()

    # =============================
    # SCRUTER LES PARTIES
    # =============================
    def scrute_tables(self):
        try:
            if not self.connected:
                return

            player_id = self.player_entry.get().strip()
            self.tree.delete(*self.tree.get_children())

            self.status.set("Statut : Chargement de l'historique...")
            self.status_label.config(fg="orange")
            self.root.update()

            # Etape 1 : charger la page historique et scroller
            self.driver.get(f"https://boardgamearena.com/gamestats?player={player_id}")
            time.sleep(4)
            for _ in range(8):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

            # Etape 2 : collecter les liens de tables Puissance 4
            liens = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/table?table="]')
            ids_vus = set()
            parties_p4 = []

            for lien in liens:
                try:
                    href = lien.get_attribute("href") or ""
                    if "table=" not in href:
                        continue
                    table_id = href.split("table=")[1].split("&")[0]
                    if table_id in ids_vus:
                        continue
                    ids_vus.add(table_id)

                    # Remonter au <tr> parent pour lire le texte de la ligne
                    parent = lien
                    for _ in range(10):
                        parent = parent.find_element(By.XPATH, "..")
                        if parent.tag_name == "tr":
                            break

                    texte_ligne = parent.text
                    if "Puissance" not in texte_ligne and "Connect Four" not in texte_ligne:
                        continue

                    # Extraire les noms des joueurs
                    joueurs = [
                        a.text.strip()
                        for a in parent.find_elements(By.CSS_SELECTOR, 'a[href*="/player"]')
                        if a.text.strip()
                    ]
                    joueurs_str = ", ".join(joueurs) if joueurs else "Inconnus"
                    parties_p4.append((table_id, joueurs_str))

                except Exception:
                    continue

            if not parties_p4:
                self.tree.insert("", "end", values=("-", "-", "Aucune partie Puissance 4 trouvee", "-"))
                self.status.set("Statut : Aucune partie trouvee")
                self.status_label.config(fg="red")
                return

            # Etape 3 : visiter chaque partie, extraire les coups, sauvegarder
            for i, (table_id, joueurs_str) in enumerate(parties_p4):
                self.status.set(f"Statut : {i+1}/{len(parties_p4)} - table {table_id}...")
                self.root.update()

                coups = extraire_coups_depuis_page(self.driver, table_id)
                statut_bdd = sauvegarder_partie(table_id, coups)

                self.tree.insert("", "end", values=(table_id, "Puissance 4", joueurs_str, statut_bdd))
                self.root.update()

            self.status.set(f"Statut : Termine - {len(parties_p4)} partie(s) traitee(s)")
            self.status_label.config(fg="green")

        except Exception:
            logging.error(traceback.format_exc())
            messagebox.showerror("Erreur", "Erreur lors de la scrutation.\nConsulte bga.log")

    # =============================
    # DECONNEXION
    # =============================
    def disconnect(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

        self.connected = False
        self.scrute_btn.config(state=tk.DISABLED)
        self.status.set("Statut : Deconnecte")
        self.status_label.config(fg="red")

    def on_close(self):
        self.disconnect()
        self.root.destroy()


# =============================
# MAIN
# =============================
if __name__ == "__main__":
    root = tk.Tk()
    app = BGAApp(root)
    root.mainloop()