import tkinter as tk
import json
from tkinter import messagebox, filedialog
from game_repository import (
    get_parties,
    get_situations,
    get_symmetriques,
    get_situations_miroir
)
from game_importer import import_txt_file

CELL = 60


class Connect4Viewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Connect4 Viewer")

        self.partie_id = None
        self.situations = []
        self.index = 0
        self.parties = []

        # ===== LABEL =====
        self.label = tk.Label(root, text="Sélectionner une partie")
        self.label.pack()

        # ===== BOUTONS =====
        frame = tk.Frame(root)
        frame.pack()

        tk.Button(frame, text="<< Précédent", command=self.prev_situation).pack(side=tk.LEFT)
        tk.Button(frame, text="Suivant >>", command=self.next_situation).pack(side=tk.LEFT)
        tk.Button(frame, text="Voir symétriques", command=self.show_symmetriques).pack(side=tk.LEFT)
        tk.Button(frame, text="Importer fichier txt", command=self.import_file_gui).pack(side=tk.LEFT)

        # ===== LISTBOX =====
        self.listbox = tk.Listbox(root, height=6)
        self.listbox.pack()
        self.listbox.bind("<<ListboxSelect>>", self.load_selected_partie)

        # ===== CANVAS (COMME TON UI) =====
        self.canvas = tk.Canvas(root, bg="blue")
        self.canvas.pack()

        self.update_parties_list()

    # ---------- LISTE ----------
    def update_parties_list(self):
        self.listbox.delete(0, tk.END)
        self.parties = get_parties()

        for p in self.parties:
            self.listbox.insert(
                tk.END,
                f"ID:{p['id']} - {p['mode']} - {p['statut']}"
            )

        self.label.config(text="Liste complète des parties")

    # ---------- CHARGEMENT ----------
    def load_selected_partie(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return

        index = selection[0]
        partie = self.parties[index]
        self.partie_id = partie['id']

        situations_db = get_situations(self.partie_id)
        self.situations = [json.loads(s['plateau']) for s in situations_db]
        self.index = 0

        if not self.situations:
            self.label.config(text="Aucune situation")
            return

        self.draw()
        self.update_label()

    # ---------- DESSIN (STRUCTURE IDENTIQUE A TON UI) ----------
    def draw(self):
        self.canvas.delete("all")

        if not self.situations:
            return

        plateau = self.situations[self.index]

        rows = len(plateau)
        cols = len(plateau[0])

        # Ajuster la taille EXACTE comme ton UI
        self.canvas.config(
            width=cols * CELL,
            height=rows * CELL
        )

        for r in range(rows):
            for c in range(cols):
                x1, y1 = c * CELL, r * CELL
                x2, y2 = x1 + CELL, y1 + CELL

                color = "white"
                if plateau[r][c] == 1:
                    color = "red"
                elif plateau[r][c] == 2:
                    color = "yellow"

                self.canvas.create_oval(
                    x1 + 5, y1 + 5,
                    x2 - 5, y2 - 5,
                    fill=color,
                    outline="black",
                    width=3
                )

    # ---------- NAVIGATION ----------
    def prev_situation(self):
        if self.index > 0:
            self.index -= 1
            self.draw()
            self.update_label()

    def next_situation(self):
        if self.index < len(self.situations) - 1:
            self.index += 1
            self.draw()
            self.update_label()

    # ---------- LABEL ----------
    def update_label(self):
        self.label.config(
            text=f"Partie ID {self.partie_id} - Coup {self.index + 1}/{len(self.situations)}"
        )

    # ---------- SYMETRIE ----------
    def show_symmetriques(self):
        if not self.partie_id:
            messagebox.showwarning("Attention", "Aucune partie sélectionnée")
            return

        sym_list = get_symmetriques(self.partie_id)

        if sym_list:
            self.parties = sym_list
            self.listbox.delete(0, tk.END)

            for p in sym_list:
                self.listbox.insert(
                    tk.END,
                    f"SYM ID:{p['id']} - {p['mode']} - {p['statut']}"
                )

            self.label.config(text="Parties symétriques")
            return

        miroir = get_situations_miroir(self.partie_id)

        if miroir:
            self.situations = miroir
            self.index = 0
            self.draw()
            self.label.config(text="Affichage symétrie calculée")

    # ---------- IMPORT ----------
    def import_file_gui(self):
        file_path = filedialog.askopenfilename(
            title="Sélectionner un fichier txt",
            filetypes=(("Fichiers texte", "*.txt"),)
        )

        if not file_path:
            return

        try:
            pid = import_txt_file(file_path)
            messagebox.showinfo("Succès", f"Partie importée ID {pid}")
            self.update_parties_list()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    Connect4Viewer(root)
    root.mainloop()
