from board import Board, RED, YELLOW
from game import Game
from game_repository import save_game_from_board
import os

def import_txt_file(filename, mode="2players", ai_type=None, rows=8, cols=9, starting_color="ROUGE"):
    """
    Importe un fichier txt dont le NOM contient la suite des coups
    ex: 131313.txt
    """

    # ---------- récupérer les coups depuis le NOM du fichier ----------
    name = os.path.basename(filename)
    name = os.path.splitext(name)[0]  # enlever .txt

    try:
        # IMPORTANT : colonnes commencent à 1 → on convertit en index 0
        coups = [int(c) - 1 for c in name]
    except ValueError:
        raise Exception("Nom de fichier invalide (ex: 131313.txt)")

    # ---------- créer une partie en mémoire ----------
    board = Board(rows, cols)
    starting = RED if starting_color.upper() == "ROUGE" else YELLOW
    game = Game(board, starting, mode)
    game.ai_type = ai_type

    # ---------- rejouer les coups ----------
    for col in coups:
        if col < 0 or col >= cols:
            raise Exception(f"Colonne invalide : {col+1}")

        if board.is_column_full(col):
            raise Exception(f"Colonne pleine : {col+1}")

        game.play_turn(col)

        if board.check_winner(RED) or board.check_winner(YELLOW):
            break

    # ---------- sauvegarde via le repository ----------
    result = save_game_from_board(game)

    if result["status"] == "EXISTE":
        raise Exception(
            f"⚠️ Partie identique ou symétrique déjà existante (ID {result['partie_id']})"
        )

    return result["partie_id"]
