import random

import json

from board import Board, RED, YELLOW

from game import Game

from game_repository import save_game_from_board

from database import get_connection


# ==============================

# CONFIG

# ==============================

NB_PARTIES_ALEATOIRES = 200   # confiance = 1

NB_PARTIES_MINIMAX    = 50    # confiance = 2  (plus long à générer)

MAX_TENTATIVES        = 5000


# ==============================

# Charger config.json

# ==============================

with open("config.json", "r") as f:

    cfg = json.load(f)["config"]


ROWS  = cfg["rows"]

COLS  = cfg["cols"]

START = RED if cfg["starting_color"].upper() == "RED" else YELLOW




# ==============================

# Mettre à jour confiance + source

# ==============================

def set_source(partie_id, source, confiance):

    conn = get_connection()

    cur  = conn.cursor()

    cur.execute(

        "UPDATE partie SET source=%s, confiance=%s WHERE id=%s",

        (source, confiance, partie_id)

    )

    conn.commit()

    conn.close()




# ==============================

# Générer une partie ALÉATOIRE

# ==============================

def generer_partie_aleatoire():

    board = Board(ROWS, COLS)

    game  = Game(board, START, "ai_vs_ai")

    game.ai_type = "random"


    for _ in range(ROWS * COLS):

        valides = [c for c in range(COLS) if not board.is_column_full(c)]

        if not valides:

            break

        col = random.choice(valides)

        game.play_turn(col)

        if board.check_winner(RED) or board.check_winner(YELLOW):

            break


    return game




# ==============================

# Générer une partie MINIMAX vs ALÉATOIRE

# (minimax joue JAUNE, aléatoire joue ROUGE)

# ==============================

def generer_partie_minimax():

    board = Board(ROWS, COLS)

    game  = Game(board, START, "human_vs_ai")

    game.ai_type = "minimax"

    game.ai.depth = 3   # profondeur 3 = bon compromis vitesse/qualité


    for _ in range(ROWS * COLS):

        valides = [c for c in range(COLS) if not board.is_column_full(c)]

        if not valides:

            break


        if game.current_player == YELLOW:

            # Minimax joue

            col = game.ai.choose_move(board)

        else:

            # Aléatoire joue

            col = random.choice(valides)


        if col is None:

            break


        game.play_turn(col)

        if board.check_winner(RED) or board.check_winner(YELLOW):

            break


    return game




# ==============================

# Insérer N parties d'un type

# ==============================

def inserer_parties(nb, generateur, source, confiance, label):

    inserees  = 0

    doublons  = 0

    tentatives = 0


    print(f"\n--- {label} ---")


    while inserees < nb and tentatives < MAX_TENTATIVES:

        tentatives += 1

        game   = generateur()

        result = save_game_from_board(game, source=source)


        if result["status"] == "OK":

            set_source(result["partie_id"], source, confiance)

            inserees += 1

            print(f"  ✅ {inserees}/{nb} — ID {result['partie_id']}")

        else:

            doublons += 1


    print(f"  Tentatives : {tentatives} | Insérées : {inserees} | Doublons : {doublons}")

    return inserees




# ==============================

# MAIN

# ==============================

def main():

    print("=" * 40)

    print("   AUTO FILL BASE DE DONNÉES")

    print("=" * 40)


    total  = 0

    total += inserer_parties(

        NB_PARTIES_ALEATOIRES,

        generer_partie_aleatoire,

        source="auto_random",

        confiance=1,

        label=f"{NB_PARTIES_ALEATOIRES} parties ALÉATOIRES (confiance=1)"

    )

    total += inserer_parties(

        NB_PARTIES_MINIMAX,

        generer_partie_minimax,

        source="auto_minimax",

        confiance=2,

        label=f"{NB_PARTIES_MINIMAX} parties MINIMAX (confiance=2)"

    )


    print("\n" + "=" * 40)

    print(f"  TOTAL INSÉRÉ : {total} parties")

    print("=" * 40)




if __name__ == "__main__":

    main()