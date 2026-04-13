import mysql.connector
import hashlib
import json
from database import get_connection
from game import Game
from board import Board, RED, YELLOW

# -----------------------------
# HASH
# -----------------------------
def hash_partie(coups):
    s = ''.join(map(str, coups))
    return hashlib.md5(s.encode()).hexdigest()

def hash_partie_miroir(coups, cols):
    miroir = [cols - 1 - c for c in coups]
    s = ''.join(map(str, miroir))
    return hashlib.md5(s.encode()).hexdigest()

def hash_situation(plateau):
    s = json.dumps(plateau, sort_keys=True)
    return hashlib.md5(s.encode()).hexdigest()

# -----------------------------
# INSERTION PARTIE
# -----------------------------
def insert_partie(mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_p, source="local", confiance=1):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO partie (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_partie, source, confiance)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_p, source, confiance))
        conn.commit()
        return cur.lastrowid
    finally:
        if conn:
            conn.close()

# -----------------------------
# INSERTION COUPS
# -----------------------------
def insert_coups(partie_id, coups, starting_color):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        couleur = starting_color

        for i, col in enumerate(coups, start=1):
            cur.execute("""
                INSERT INTO coup (partie_id, numero, couleur, colonne)
                VALUES (%s,%s,%s,%s)
            """, (partie_id, i, couleur, col))
            couleur = "JAUNE" if couleur == "ROUGE" else "ROUGE"

        conn.commit()
    finally:
        if conn:
            conn.close()

# -----------------------------
# INSERTION SITUATIONS
# -----------------------------
def insert_situations(partie_id, situations):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for i, plateau in enumerate(situations, start=1):
            cur.execute("""
                INSERT IGNORE INTO situation (partie_id, coup_numero, plateau, hash_situation)
                VALUES (%s,%s,%s,%s)
            """, (partie_id, i, json.dumps(plateau), hash_situation(plateau)))

        conn.commit()
    finally:
        if conn:
            conn.close()

# -----------------------------
# RECUPERATION PARTIES
# -----------------------------
def get_parties():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM partie ORDER BY id DESC")
        return cur.fetchall()
    finally:
        if conn:
            conn.close()

# -----------------------------
# RECUPERATION SITUATIONS
# -----------------------------
def get_situations(partie_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT coup_numero, plateau
            FROM situation
            WHERE partie_id = %s
            ORDER BY coup_numero
        """, (partie_id,))
        return cur.fetchall()
    finally:
        if conn:
            conn.close()

# -----------------------------
# RECUPERATION PARTIES SYMETRIQUES
# -----------------------------
def get_symmetriques(partie_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT nb_cols FROM partie WHERE id=%s", (partie_id,))
        row = cur.fetchone()
        if not row:
            return []

        cols = row["nb_cols"]

        cur.execute("""
            SELECT colonne
            FROM coup
            WHERE partie_id=%s
            ORDER BY numero
        """, (partie_id,))
        coups = [r["colonne"] for r in cur.fetchall()]

        if not coups:
            return []

        h_miroir = hash_partie_miroir(coups, cols)

        cur.execute("""
            SELECT *
            FROM partie
            WHERE hash_partie=%s
              AND id != %s
        """, (h_miroir, partie_id))

        return cur.fetchall()
    finally:
        if conn:
            conn.close()


# -----------------------------
# SAUVEGARDE PARTIE — UNE SEULE CONNEXION
# -----------------------------
def save_game_from_board(game, source="local"):
    coups = [c for _, c, _ in game.board.history]
    rows = game.board.rows
    cols = game.board.cols
    starting_color = "ROUGE" if game.starting_player == RED else "JAUNE"

    h_normal = hash_partie(coups)
    h_miroir = hash_partie_miroir(coups, cols)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # ── FIX : vérification doublon uniquement sur la même source ──
        # On vérifie le hash exact (h_normal) toutes sources confondues
        # pour éviter les vrais doublons, mais le hash miroir uniquement
        # pour la même source afin de ne pas bloquer les parties locales
        # qui matchent des parties d'entraînement symétriques.
        cur.execute(
            "SELECT id FROM partie WHERE hash_partie = %s",
            (h_normal,)
        )
        existing = cur.fetchone()
        if not existing:
            cur.execute(
                "SELECT id FROM partie WHERE hash_partie = %s AND source = %s",
                (h_miroir, source)
            )
            existing = cur.fetchone()

        if existing:
            return {"status": "EXISTE", "partie_id": existing[0]}

        # 2. Statut
        if game.board.check_winner(RED):
            statut = "TERMINE_ROUGE"
        elif game.board.check_winner(YELLOW):
            statut = "TERMINE_JAUNE"
        elif game.board.is_full():
            statut = "TERMINE_NUL"
        else:
            statut = "EN_COURS"

        # 3. Insert partie
        cur.execute("""
            INSERT INTO partie (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_partie, source, confiance)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (game.mode, game.ai_type, statut, rows, cols, starting_color, h_normal, source, 1))
        pid = cur.lastrowid

        # 4. Insert coups
        couleur = starting_color
        for i, col in enumerate(coups, start=1):
            cur.execute("""
                INSERT INTO coup (partie_id, numero, couleur, colonne)
                VALUES (%s,%s,%s,%s)
            """, (pid, i, couleur, col))
            couleur = "JAUNE" if couleur == "ROUGE" else "ROUGE"

        # 5. Insert situations
        plateau = [[0] * cols for _ in range(rows)]
        current = RED if starting_color == "ROUGE" else YELLOW
        for num, col in enumerate(coups, start=1):
            for r in range(rows - 1, -1, -1):
                if plateau[r][col] == 0:
                    plateau[r][col] = current
                    break
            plateau_snap = [row[:] for row in plateau]
            cur.execute("""
                INSERT IGNORE INTO situation (partie_id, coup_numero, plateau, hash_situation)
                VALUES (%s,%s,%s,%s)
            """, (pid, num, json.dumps(plateau_snap), hash_situation(plateau_snap)))
            current = YELLOW if current == RED else RED

        conn.commit()
        return {"status": "OK", "partie_id": pid}

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[SAVE] Erreur : {e}")
        return {"status": "ERREUR", "detail": str(e)}
    finally:
        if conn:
            conn.close()

# -----------------------------
# CHARGEMENT PARTIE
# -----------------------------
def load_game(partie_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM partie WHERE id=%s", (partie_id,))
        partie = cur.fetchone()
        if not partie:
            return None

        rows = partie['nb_rows']
        cols = partie['nb_cols']
        starting_color = RED if partie['starting_color'] == "ROUGE" else YELLOW

        board = Board(rows, cols)
        game = Game(board, starting_color, partie['mode'])
        game.ai_type = partie['ai_type']

        cur.execute("""
            SELECT plateau
            FROM situation
            WHERE partie_id=%s
            ORDER BY coup_numero
        """, (partie_id,))
        situations = cur.fetchall()

        if situations:
            board.grid = json.loads(situations[-1]['plateau'])

        board.history = [
            (r, c, board.grid[r][c])
            for r in range(rows)
            for c in range(cols)
            if board.grid[r][c] != 0
        ]

        game.current_player = (
            starting_color
            if len(board.history) % 2 == 0
            else (YELLOW if starting_color == RED else RED)
        )

        game.game_over = partie['statut'] != "EN_COURS"
        return game
    finally:
        if conn:
            conn.close()

# -----------------------------
# SYMÉTRIE VISUELLE (NON ENREGISTRÉE)
# -----------------------------
def mirror_board(grid):
    return [list(reversed(row)) for row in grid]


def get_situations_miroir(partie_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT nb_cols FROM partie WHERE id=%s", (partie_id,))
        row = cur.fetchone()
        if not row:
            return []

        cur.execute("""
            SELECT plateau
            FROM situation
            WHERE partie_id=%s
            ORDER BY coup_numero
        """, (partie_id,))
        situations = cur.fetchall()

        if not situations:
            return []

        return [
            [list(reversed(r)) for r in json.loads(s["plateau"])]
            for s in situations
        ]
    finally:
        if conn:
            conn.close()