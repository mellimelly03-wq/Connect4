import tkinter as tk
from tkinter import ttk, messagebox
import time
import traceback
import logging
import hashlib
import re
import json

from selenium.webdriver import Firefox
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from database import get_connection

# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    filename="bga.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# ==============================
# CONFIG
# ==============================
CONFIANCE_BGA = 4
NB_ROWS       = 9
NB_COLS       = 9

# ==============================
# NETTOYAGE BDD AU DÉMARRAGE
# ==============================
def nettoyer_parties_vides():
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            DELETE FROM partie
            WHERE source LIKE 'bga_%'
            AND id NOT IN (SELECT DISTINCT partie_id FROM coup)
        """)
        nb = cur.rowcount
        conn.commit()
        conn.close()
        if nb > 0:
            logging.info(f"Nettoyage : {nb} partie(s) BGA vide(s) supprimée(s)")
    except Exception:
        logging.warning(f"Nettoyage BDD : {traceback.format_exc()}")


# ==============================
# HASH
# ==============================
def hash_coups(coups):
    return hashlib.md5(''.join(map(str, coups)).encode()).hexdigest()

def hash_miroir(coups, nb_cols=NB_COLS):
    return hashlib.md5(''.join(map(str, [nb_cols - 1 - c for c in coups])).encode()).hexdigest()


# ==============================
# SAUVEGARDE EN BASE
# ==============================
def sauvegarder_partie(table_id, coups):
    """
    Insère la partie BGA + génère les situations coup par coup.
    confiance = 4 (vrais joueurs BGA)
    """
    conn = get_connection()
    cur  = conn.cursor()

    # 1. Déjà enregistrée ?
    cur.execute("SELECT id FROM partie WHERE source = %s", (f"bga_{table_id}",))
    existant = cur.fetchone()
    if existant:
        conn.close()
        return f"⚠️ Doublon de #{existant[0]}"

    # 2. Partie sans coups = abandonnée
    if not coups:
        conn.close()
        return "⏭️ Ignorée (partie incomplète)"

    h  = hash_coups(coups)
    hm = hash_miroir(coups)

    # 3. Doublon par hash
    cur.execute(
        "SELECT id FROM partie WHERE hash_partie = %s OR hash_partie = %s",
        (h, hm)
    )
    existant = cur.fetchone()
    if existant:
        conn.close()
        return f"⚠️ Symétrie/doublon de #{existant[0]}"

    # 4. Insertion de la partie
    cur.execute("""
        INSERT INTO partie
            (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_partie, source, confiance)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, ("bga", "humain", "TERMINE", NB_ROWS, NB_COLS, "ROUGE", h, f"bga_{table_id}", CONFIANCE_BGA))
    conn.commit()
    pid = cur.lastrowid

    # 5. Insertion coups + situations
    plateau = [[0] * NB_COLS for _ in range(NB_ROWS)]
    couleur = "ROUGE"

    for i, col in enumerate(coups, start=1):
        # Coup
        cur.execute(
            "INSERT INTO coup (partie_id, numero, couleur, colonne) VALUES (%s,%s,%s,%s)",
            (pid, i, couleur, col)
        )

        # Mettre à jour le plateau
        for r in range(NB_ROWS - 1, -1, -1):
            if plateau[r][col] == 0:
                plateau[r][col] = 1 if couleur == "ROUGE" else 2
                break

        # Situation
        plateau_json = json.dumps(plateau)
        hash_sit     = hashlib.md5(plateau_json.encode()).hexdigest()
        cur.execute("""
            INSERT IGNORE INTO situation (partie_id, coup_numero, plateau, hash_situation)
            VALUES (%s, %s, %s, %s)
        """, (pid, i, plateau_json, hash_sit))

        couleur = "JAUNE" if couleur == "ROUGE" else "ROUGE"

    conn.commit()
    conn.close()
    logging.info(f"Partie bga_{table_id} sauvegardée → id {pid}, {len(coups)} coups")
    return f"✅ Sauvegardée (ID #{pid})"


# ==============================
# EXTRACTION DES COUPS
# ==============================
def extraire_coups(driver, table_id):
    try:
        driver.get(f"https://boardgamearena.com/table?table={table_id}")
        time.sleep(4)

        # Cliquer sur "Revoir la partie"
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH,
                    '//*[contains(text(),"Revoir") or contains(text(),"Review") or contains(text(),"Replay")]'
                ))
            )
            btn.click()
            time.sleep(5)
        except Exception:
            logging.warning(f"Table {table_id} : bouton Revoir introuvable")
            return []

        # Lire #gamelogs
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.find_element(By.ID, "gamelogs").text.strip() != ""
            )
            texte = driver.find_element(By.ID, "gamelogs").text
        except Exception:
            logging.warning(f"Table {table_id} : #gamelogs vide ou absent")
            return []

        # Patterns multilingues (base 1 → base 0)
        patterns = [
            r'place un pion dans la colonne (\d+)',
            r'plays in column (\d+)',
            r'speelt in kolom (\d+)',
            r'spielt in Spalte (\d+)',
            r'juega en la columna (\d+)',
            r'gioca nella colonna (\d+)',
            r'jogar na coluna (\d+)',
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
        logging.warning(f"Table {table_id} : extraction échouée\n{traceback.format_exc()}")
        return []


# ==============================
# INTERFACE TKINTER
# ==============================
class BGAApp:

    def __init__(self, root):
        self.root = root
        self.root.title("BGA - Puissance 4 Scraper")
        self.root.geometry("980x650")
        self.driver    = None
        self.connected = False

        nettoyer_parties_vides()

        self.status = tk.StringVar(value="Statut : Déconnecté")
        self.status_label = tk.Label(root, textvariable=self.status, fg="red", font=("Arial", 12))
        self.status_label.pack(pady=8)

        self.connect_btn = tk.Button(root, text="🔌 Connecter à BGA",
                                     command=self.connect, width=28)
        self.connect_btn.pack(pady=5)

        frame = tk.Frame(root)
        frame.pack(pady=8)
        tk.Label(frame, text="ID Joueur BGA :").pack(side=tk.LEFT)
        self.player_entry = tk.Entry(frame, width=20)
        self.player_entry.pack(side=tk.LEFT, padx=8)
        self.player_entry.insert(0, "97047639")

        self.scrute_btn = tk.Button(
            root,
            text="🔍 Scruter les parties Puissance 4",
            command=self.scrute_tables,
            state=tk.DISABLED,
            width=35
        )
        self.scrute_btn.pack(pady=8)

        self.tree = ttk.Treeview(
            root,
            columns=("table", "joueurs", "coups", "bdd"),
            show="headings"
        )
        self.tree.heading("table",   text="Table ID")
        self.tree.heading("joueurs", text="Joueurs")
        self.tree.heading("coups",   text="Nb Coups")
        self.tree.heading("bdd",     text="Statut BDD")
        self.tree.column("table",   width=90,  anchor="center")
        self.tree.column("joueurs", width=260, anchor="w")
        self.tree.column("coups",   width=80,  anchor="center")
        self.tree.column("bdd",     width=320, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.resume_label = tk.Label(root, text="", font=("Arial", 10))
        self.resume_label.pack(pady=4)

        tk.Button(root, text="🔴 Déconnecter",
                  command=self.disconnect, width=25).pack(pady=5)

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ==============================
    # CONNEXION MANUELLE
    # ==============================
    def connect(self):
        try:
            self.status.set("Statut : Lancement de Firefox...")
            self.status_label.config(fg="orange")
            self.root.update()

            options = Options()
            options.headless = False
            service = Service("geckodriver.exe")
            options.binary_location = r"C:\Users\Melissa\AppData\Local\Mozilla Firefox\firefox.exe"
            self.driver = Firefox(service=service, options=options)
            self.driver.set_window_size(1200, 800)
            self.driver.get("https://boardgamearena.com")
            time.sleep(3)

            messagebox.showinfo(
                "Connexion BGA",
                "1. Connecte-toi MANUELLEMENT à Board Game Arena dans Firefox.\n"
                "2. Une fois connecté (tu vois ton pseudo en haut à droite),\n"
                "   clique sur OK ici."
            )

            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".bga-player-avatar, .player-name, #account_menu")
                )
            )

            self.connected = True
            self.status.set("Statut : ✅ Connecté à BGA")
            self.status_label.config(fg="green")
            self.scrute_btn.config(state=tk.NORMAL)
            logging.info("Connexion BGA réussie")

        except Exception:
            logging.error(traceback.format_exc())
            messagebox.showerror("Erreur", "Connexion échouée.\nConsulte bga.log")
            self.disconnect()

    # ==============================
    # SCRUTER LES PARTIES
    # ==============================
    def scrute_tables(self):
        try:
            if not self.connected:
                return

            player_id = self.player_entry.get().strip()
            self.tree.delete(*self.tree.get_children())
            self.resume_label.config(text="")
            self.status.set("Statut : Chargement de l'historique...")
            self.status_label.config(fg="orange")
            self.root.update()

            self.driver.get(f"https://boardgamearena.com/gamestats?player={player_id}")
            time.sleep(4)

            for _ in range(10):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

            liens   = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/table?table="]')
            ids_vus = set()
            parties = []

            for lien in liens:
                try:
                    href = lien.get_attribute("href") or ""
                    if "table=" not in href:
                        continue
                    table_id = href.split("table=")[1].split("&")[0]
                    if table_id in ids_vus:
                        continue
                    ids_vus.add(table_id)

                    parent = lien
                    for _ in range(10):
                        parent = parent.find_element(By.XPATH, "..")
                        if parent.tag_name == "tr":
                            break

                    texte_ligne = parent.text
                    if "Puissance" not in texte_ligne and "Connect" not in texte_ligne:
                        continue

                    joueurs = [
                        a.text.strip()
                        for a in parent.find_elements(By.CSS_SELECTOR, 'a[href*="/player"]')
                        if a.text.strip()
                    ]
                    joueurs_str = ", ".join(joueurs) if joueurs else "Inconnus"
                    parties.append((table_id, joueurs_str))

                except Exception:
                    continue

            if not parties:
                self.tree.insert("", "end",
                    values=("-", "Aucune partie Puissance 4 trouvée", "-", "-"))
                self.status.set("Statut : Aucune partie trouvée")
                self.status_label.config(fg="red")
                return

            nb_ok = nb_doublon = nb_ignore = 0

            for i, (table_id, joueurs_str) in enumerate(parties):
                self.status.set(f"Statut : {i+1}/{len(parties)} — table {table_id}...")
                self.root.update()

                coups      = extraire_coups(self.driver, table_id)
                statut_bdd = sauvegarder_partie(table_id, coups)

                if "✅" in statut_bdd:
                    nb_ok += 1
                elif "⚠️" in statut_bdd:
                    nb_doublon += 1
                else:
                    nb_ignore += 1

                self.tree.insert("", "end", values=(
                    table_id, joueurs_str, len(coups), statut_bdd
                ))
                self.root.update()

            resume = f"✅ {nb_ok} sauvegardées | ⚠️ {nb_doublon} doublons | ⏭️ {nb_ignore} ignorées"
            self.resume_label.config(text=resume)
            self.status.set(f"Statut : Terminé — {len(parties)} parties traitées")
            self.status_label.config(fg="green")
            logging.info(f"Scraping terminé : {resume}")

        except Exception:
            logging.error(traceback.format_exc())
            messagebox.showerror("Erreur", "Erreur lors du scraping.\nConsulte bga.log")

    # ==============================
    # DÉCONNEXION
    # ==============================
    def disconnect(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        self.connected = False
        self.scrute_btn.config(state=tk.DISABLED)
        self.status.set("Statut : Déconnecté")
        self.status_label.config(fg="red")

    def on_close(self):
        self.disconnect()
        self.root.destroy()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    root = tk.Tk()
    app  = BGAApp(root)
    root.mainloop()