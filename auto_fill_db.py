import random
import json
from board import Board, RED, YELLOW
from game import Game
from game_repository import save_game_from_board
from database import get_connection

# ==============================
# CONFIG
# ==============================
NB_PARTIES_A_INSERER = 100
MAX_TENTATIVES = 5000
MIN_COUPS = 8
MAX_COUPS = 30
# ==============================
# Charger config.json
# ==============================
with open("config.json", "r") as f:
    cfg = json.load(f)["config"]

ROWS = cfg["rows"]
COLS = cfg["cols"]
STARTING_COLOR = cfg["starting_color"]

START_PLAYER = RED if STARTING_COLOR.upper() == "RED" else YELLOW


# ==============================
# Générer une partie aléatoire
# ==============================
def generate_random_game():
    board = Board(ROWS, COLS)
    game = Game(board, START_PLAYER, "2players")

    nb_moves = random.randint(MIN_COUPS, MAX_COUPS)

    for _ in range(nb_moves):
        valid_cols = [c for c in range(COLS) if not board.is_column_full(c)]
        if not valid_cols:
            break

        col = random.choice(valid_cols)
        game.play_turn(col)

        if board.check_winner(RED) or board.check_winner(YELLOW):
            break

    return game


# ==============================
# Mettre à jour source = "auto_fill"
# ==============================
def set_source_auto_fill(partie_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE partie SET source=%s WHERE id=%s", ("auto_fill", partie_id))
    conn.commit()
    conn.close()


# ==============================
# MAIN
# ==============================
def main():
    inserted = 0
    duplicates = 0
    attempts = 0

    while inserted < NB_PARTIES_A_INSERER and attempts < MAX_TENTATIVES:
        attempts += 1

        game = generate_random_game()
        result = save_game_from_board(game)

        if result["status"] == "OK":
            inserted += 1
            set_source_auto_fill(result["partie_id"])
            print(f"✅ Partie insérée : ID {result['partie_id']}")

        elif result["status"] == "EXISTE":
            duplicates += 1

    print("\n==============================")
    print("📌 Résumé auto_fill_db.py")
    print("==============================")
    print(f"Tentatives totales : {attempts}")
    print(f"Nouvelles parties  : {inserted}")
    print(f"Doublons détectés  : {duplicates}")
    print("==============================\n")

    if inserted < NB_PARTIES_A_INSERER:
        print("⚠️ Attention : pas assez de nouvelles parties trouvées.")
        print("👉 Augmente MAX_TENTATIVES ou change MIN/MAX_COUPS.")


if __name__ == "__main__":
    main()
