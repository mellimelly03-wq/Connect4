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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO partie (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_partie, source, confiance)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (mode, ai_type, statut, nb_rows, nb_cols, starting_color, hash_p, source, confiance))
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid
# -----------------------------
# INSERTION COUPS
# -----------------------------
def insert_coups(partie_id, coups, starting_color):
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
    conn.close()

# -----------------------------
# INSERTION SITUATIONS
# -----------------------------
def insert_situations(partie_id, situations):
    conn = get_connection()
    cur = conn.cursor()

    for i, plateau in enumerate(situations, start=1):
        cur.execute("""
            INSERT IGNORE INTO situation (partie_id, coup_numero, plateau, hash_situation)
            VALUES (%s,%s,%s,%s)
        """, (partie_id, i, json.dumps(plateau), hash_situation(plateau)))

    conn.commit()
    conn.close()

# -----------------------------
# RECUPERATION PARTIES
# -----------------------------
def get_parties():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM partie ORDER BY id DESC")
    res = cur.fetchall()
    conn.close()
    return res

# -----------------------------
# RECUPERATION SITUATIONS
# -----------------------------
def get_situations(partie_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT coup_numero, plateau
        FROM situation
        WHERE partie_id = %s
        ORDER BY coup_numero
    """, (partie_id,))
    res = cur.fetchall()
    conn.close()
    return res

# -----------------------------
# RECUPERATION PARTIES SYMETRIQUES
# -----------------------------
def get_symmetriques(partie_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # récupérer le nombre de colonnes
    cur.execute("SELECT nb_cols FROM partie WHERE id=%s", (partie_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return []

    cols = row["nb_cols"]

    # récupérer les coups de la partie
    cur.execute("""
        SELECT colonne
        FROM coup
        WHERE partie_id=%s
        ORDER BY numero
    """, (partie_id,))
    coups = [r["colonne"] for r in cur.fetchall()]

    if not coups:
        conn.close()
        return []

    # hash miroir
    h_miroir = hash_partie_miroir(coups, cols)

    # chercher les parties correspondantes
    cur.execute("""
        SELECT *
        FROM partie
        WHERE hash_partie=%s
          AND id != %s
    """, (h_miroir, partie_id))

    sym_list = cur.fetchall()
    conn.close()
    return sym_list


# -----------------------------
# SAUVEGARDE PARTIE (CORRIGÉE)
# -----------------------------
def save_game_from_board(game, source="local"):
    coups = [c for _, c, _ in game.board.history]
    rows = game.board.rows
    cols = game.board.cols
    starting_color = "ROUGE" if game.starting_player == RED else "JAUNE"

    h_normal = hash_partie(coups)
    h_miroir = hash_partie_miroir(coups, cols)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM partie WHERE hash_partie=%s OR hash_partie=%s",
        (h_normal, h_miroir)
    )
    existing = cur.fetchone()
    conn.close()

    # ⛔ Partie identique OU symétrique
    if existing:
        return {
            "status": "EXISTE",
            "partie_id": existing[0]
        }

    # Statut
    if game.board.check_winner(RED):
        statut = "TERMINE_ROUGE"
    elif game.board.check_winner(YELLOW):
        statut = "TERMINE_JAUNE"
    elif game.board.is_full():
        statut = "TERMINE_NUL"
    else:
        statut = "EN_COURS"

    pid = insert_partie(
        game.mode,
        game.ai_type,
        statut,
        rows,
        cols,
        starting_color,
        h_normal
    )

    insert_coups(pid, coups, starting_color)

    # Génération des situations
    plateau = [[0]*cols for _ in range(rows)]
    situations = []
    current = RED if starting_color == "ROUGE" else YELLOW

    for col in coups:
        for r in range(rows-1, -1, -1):
            if plateau[r][col] == 0:
                plateau[r][col] = current
                break
        situations.append([row[:] for row in plateau])
        current = YELLOW if current == RED else RED

    insert_situations(pid, situations)

    return {
        "status": "OK",
        "partie_id": pid
    }

# -----------------------------
# CHARGEMENT PARTIE
# -----------------------------
def load_game(partie_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM partie WHERE id=%s", (partie_id,))
    partie = cur.fetchone()
    if not partie:
        conn.close()
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
    conn.close()

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

# -----------------------------
# SYMÉTRIE VISUELLE (NON ENREGISTRÉE)
# -----------------------------
def mirror_board(grid):
    return [list(reversed(row)) for row in grid]


def get_situations_miroir(partie_id):
    """
    Retourne les situations miroir d'une partie (sans les enregistrer)
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # récupérer les infos de la partie
    cur.execute("SELECT nb_cols FROM partie WHERE id=%s", (partie_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return []

    cols = row["nb_cols"]

    # récupérer les situations normales
    cur.execute("""
        SELECT plateau
        FROM situation
        WHERE partie_id=%s
        ORDER BY coup_numero
    """, (partie_id,))
    situations = cur.fetchall()
    conn.close()

    if not situations:
        return []

    # créer les situations miroir
    miroir = []
    for s in situations:
        grid = json.loads(s["plateau"])
        grid_miroir = [list(reversed(row)) for row in grid]
        miroir.append(grid_miroir)

    return miroir

