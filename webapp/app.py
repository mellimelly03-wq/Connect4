from flask import Flask, render_template, request, jsonify, session

import sys

import os

import json

import uuid

import copy



BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SITE_DIR = os.path.abspath(os.path.dirname(__file__))

sys.path = [p for p in sys.path if os.path.abspath(p) != SITE_DIR and p != '']

sys.path.insert(0, BASE_DIR)



from board import Board, RED, YELLOW

from game import Game

from game_repository import save_game_from_board, get_parties, get_situations, load_game

from ai_bdd import AIBaseDeDonnees

from minmax import MiniMaxAI



app = Flask(__name__)

app.secret_key = "connect4-secret-key-2024"



with open(os.path.join(BASE_DIR, "config.json"), "r") as f:

    cfg = json.load(f)["config"]



ROWS = cfg["rows"]

COLS = cfg["cols"]



OPENING_BOOK = {

    "": 3,

    "3": 3,

}



sessions = {}



def get_session_id():

    if 'sid' not in session:

        session['sid'] = str(uuid.uuid4())

    return session['sid']



def get_game_state():

    sid = get_session_id()

    if sid not in sessions:

        sessions[sid] = {

            'board': Board(ROWS, COLS),

            'game': None

        }

    return sessions[sid]



def predict_outcome(board, current_player, depth=7):
    import copy
    b = copy.deepcopy(board)
    opp = YELLOW if current_player == RED else RED

    def col_order():
        center = b.cols // 2
        return sorted(
            [c for c in range(b.cols) if not b.is_column_full(c)],
            key=lambda c: abs(c - center)
        )

    def minimax(player, depth_left, alpha, beta, moves_made):
        cols = col_order()
        if not cols or b.is_full():
            return 0, moves_made

        nxt = opp if player == current_player else current_player

        if player == current_player:  # MAX
            best_score, best_moves = -float('inf'), moves_made
            for col in cols:
                b.drop_piece(col, player)
                # On vérifie JUSTE APRÈS avoir posé la pièce
                if b.check_winner(player):
                    b.undo()
                    return 10000 - moves_made, moves_made + 1
                if depth_left == 0:
                    b.undo()
                    continue
                score, nm = minimax(nxt, depth_left - 1, alpha, beta, moves_made + 1)
                b.undo()
                if score > best_score:
                    best_score, best_moves = score, nm
                alpha = max(alpha, best_score)
                if beta <= alpha:
                    break
            return best_score, best_moves

        else:  # MIN
            best_score, best_moves = float('inf'), moves_made
            for col in cols:
                b.drop_piece(col, player)
                if b.check_winner(player):
                    b.undo()
                    return -(10000 - moves_made), moves_made + 1
                if depth_left == 0:
                    b.undo()
                    continue
                score, nm = minimax(nxt, depth_left - 1, alpha, beta, moves_made + 1)
                b.undo()
                if score < best_score:
                    best_score, best_moves = score, nm
                beta = min(beta, best_score)
                if beta <= alpha:
                    break
            return best_score, best_moves

    score, nb_coups = minimax(current_player, depth, -float('inf'), float('inf'), 0)

    if score > 0:
        return ("ROUGE" if current_player == RED else "JAUNE"), nb_coups
    elif score < 0:
        return ("ROUGE" if opp == RED else "JAUNE"), nb_coups
    else:
        return None



@app.route("/")

def index():

    state = get_game_state()

    grid = state['board'].grid

    game = state['game']

    resumed = game is not None and not game.game_over

    mode = game.mode if game else None

    human_color = getattr(game, 'human_color', RED) if game else RED

    ai_type = getattr(game, 'ai_type', 'minimax') if game else 'minimax'

    depth = game.ai.depth if (game and hasattr(game, 'ai') and hasattr(game.ai, 'depth')) else 4

    return render_template(

        "game.html",

        rows=ROWS,

        cols=COLS,

        grid=grid,

        resumed=resumed,

        mode=mode,

        human_color=human_color,

        ai_type=ai_type,

        depth=depth

    )



@app.route("/start", methods=["POST"])

def start():

    state = get_game_state()

    data = request.json

    mode = data["mode"]

    ai_type = data["ai_type"]

    depth = int(data["depth"])

    starting = int(data["starting"])



    state['board'] = Board(ROWS, COLS)

    state['game'] = Game(state['board'], starting, mode)

    state['game'].ai_type = ai_type

    state['game'].human_color = starting



    if ai_type == "minimax":

        state['game'].ai.depth = depth

    elif ai_type == "bdd":

        state['game'].ai_bdd = AIBaseDeDonnees(couleur="JAUNE" if starting == 1 else "ROUGE")



    return jsonify({"grid": state['board'].grid})



@app.route("/move", methods=["POST"])

def move():

    state = get_game_state()

    game = state['game']

    board = state['board']



    if not game or game.game_over or game.paused:

        return jsonify({"error": "invalid"})



    col = int(request.json["col"])

    if board.is_column_full(col):

        return jsonify({"error": "full", "grid": board.grid})



    winner = game.play_turn(col)



    if winner or game.game_over:

        return jsonify({

            "grid": board.grid,

            "winner": winner,

            "scores": [],

            "winning_cells": board.winning_cells,

            "draw": board.is_full(),

            "ai_pending": False

        })



    if game.mode == "human_vs_ai" and not game.game_over:

        return jsonify({

            "grid": board.grid,

            "winner": None,

            "scores": [],

            "winning_cells": [],

            "draw": False,

            "ai_pending": True

        })



    return jsonify({

        "grid": board.grid,

        "winner": winner,

        "scores": [],

        "winning_cells": board.winning_cells,

        "draw": board.is_full(),

        "ai_pending": False

    })



@app.route("/ai_move", methods=["POST"])

def ai_move():

    state = get_game_state()

    game = state['game']

    board = state['board']



    if not game or game.game_over or game.paused:

        return jsonify({"error": "invalid"})



    col, scores = get_ai_move_for(game)

    winner = game.play_turn(col)



    return jsonify({

        "grid": board.grid,

        "winner": winner,

        "scores": scores if game.ai_type == "minimax" else [],

        "winning_cells": board.winning_cells,

        "draw": board.is_full()

    })



@app.route("/undo", methods=["POST"])

def undo():

    state = get_game_state()

    if state['game']:

        state['game'].undo()

    return jsonify({"grid": state['board'].grid})



@app.route("/restart", methods=["POST"])

def restart():

    state = get_game_state()

    if state['game']:

        state['game'].restart()

    return jsonify({"grid": state['board'].grid})



@app.route("/pause", methods=["POST"])

def pause():

    state = get_game_state()

    if state['game']:

        state['game'].pause()

    return jsonify({"status": "paused"})



@app.route("/resume", methods=["POST"])

def resume():

    state = get_game_state()

    if state['game']:

        state['game'].resume()

    return jsonify({"status": "resumed"})



@app.route("/save", methods=["POST"])

def save():

    state = get_game_state()

    if state['game']:

        return jsonify(save_game_from_board(state['game']))

    return jsonify({"error": "no_game"})



@app.route("/ai_suggest", methods=["POST"])

def ai_suggest():

    state = get_game_state()

    if not state['game']:

        return jsonify({"col": None})

    col, _ = get_ai_move_for(state['game'])

    return jsonify({"col": col})



@app.route("/predict", methods=["POST"])
def predict():
    state = get_game_state()
    game = state['game']
    board = state['board']

    if not game or game.game_over:
        return jsonify({"prediction": None})

    result = predict_outcome(board, game.current_player, depth=7)

    if result:
        color_name = "ROUGE 🔴" if result[0] == "ROUGE" else "JAUNE 🟡"
        return jsonify({
            "prediction": f"{color_name} gagne dans {result[1]} coup{'s' if result[1] > 1 else ''} (jeu optimal)"
        })
    else:
        return jsonify({"prediction": "Aucun gagnant détecté — partie équilibrée"})


@app.route("/paint", methods=["POST"])

def paint():

    state = get_game_state()

    data = request.json

    row = int(data["row"])

    col = int(data["col"])

    color = int(data["color"])



    state['board'].grid[row][col] = color



    red_count = sum(state['board'].grid[r][c] == RED for r in range(ROWS) for c in range(COLS))

    yellow_count = sum(state['board'].grid[r][c] == YELLOW for r in range(ROWS) for c in range(COLS))



    if red_count == yellow_count:

        next_player = "ROUGE"

        next_color = "red"

    elif red_count > yellow_count:

        next_player = "JAUNE"

        next_color = "yellow"

    else:

        next_player = "ROUGE"

        next_color = "red"



    return jsonify({

        "grid": state['board'].grid,

        "next_player": next_player,

        "next_color": next_color,

        "red_count": red_count,

        "yellow_count": yellow_count

    })



@app.route("/start_from_paint", methods=["POST"])

def start_from_paint():

    state = get_game_state()

    data = request.json

    mode = data["mode"]

    ai_type = data.get("ai_type", "minimax")

    depth = int(data.get("depth", 4))

    human_color_str = data.get("human_color", "rouge")

    human_color = RED if human_color_str == "rouge" else YELLOW



    grid = state['board'].grid



    red_count = sum(grid[r][c] == RED for r in range(ROWS) for c in range(COLS))

    yellow_count = sum(grid[r][c] == YELLOW for r in range(ROWS) for c in range(COLS))

    starting = RED if red_count == yellow_count else YELLOW



    ordered_history = []

    pieces_par_col = {}

    for c in range(COLS):

        pieces = []

        for r in range(ROWS - 1, -1, -1):

            if grid[r][c] != 0:

                pieces.append((r, c, grid[r][c]))

        pieces_par_col[c] = pieces



    max_height = max((len(v) for v in pieces_par_col.values()), default=0)

    for layer in range(max_height):

        for c in range(COLS):

            if layer < len(pieces_par_col[c]):

                ordered_history.append(pieces_par_col[c][layer])



    state['board'].history = ordered_history



    state['game'] = Game(state['board'], starting, mode)

    state['game'].ai_type = ai_type

    state['game'].current_player = starting

    state['game'].human_color = human_color



    if ai_type == "minimax":

        state['game'].ai.depth = depth

    elif ai_type == "bdd":

        ai_color = "JAUNE" if human_color == RED else "ROUGE"

        state['game'].ai_bdd = AIBaseDeDonnees(couleur=ai_color)



    next_player_str = "ROUGE" if starting == RED else "JAUNE"

    ai_pending = mode == "human_vs_ai" and starting != human_color



    return jsonify({

        "grid": state['board'].grid,

        "next_player": next_player_str,

        "ai_pending": ai_pending

    })



@app.route("/switch_control", methods=["POST"])

def switch_control():

    state = get_game_state()

    game = state['game']

    if not game:

        return jsonify({"error": "no_game"})



    data = request.json

    new_mode = data["mode"]

    new_ai_type = data.get("ai_type", game.ai_type)

    new_depth = int(data.get("depth", 4))

    human_color_str = data.get("human_color", "rouge")

    human_color = RED if human_color_str == "rouge" else YELLOW



    game.mode = new_mode

    game.ai_type = new_ai_type

    game.human_color = human_color



    if new_ai_type == "minimax" and hasattr(game, 'ai'):

        game.ai.depth = new_depth

    elif new_ai_type == "bdd":

        ai_color = "JAUNE" if human_color == RED else "ROUGE"

        game.ai_bdd = AIBaseDeDonnees(couleur=ai_color)



    ai_pending = new_mode == "human_vs_ai" and game.current_player != human_color



    return jsonify({

        "ok": True,

        "mode": new_mode,

        "human_color": human_color_str,

        "ai_pending": ai_pending

    })



@app.route("/get_grid")

def get_grid():

    state = get_game_state()

    game = state['game']

    ai_turn = False

    if game and game.mode == "human_vs_ai" and not game.game_over:

        ai_turn = game.current_player != game.human_color

    return jsonify({

        "grid": state['board'].grid,

        "ai_turn": ai_turn

    })



@app.route("/historique")

def historique():

    parties = get_parties()

    return render_template("historique.html", parties=parties)



@app.route("/replay/<int:partie_id>")

def replay(partie_id):

    situations = get_situations(partie_id)

    plateaux = [json.loads(s['plateau']) for s in situations]

    return jsonify(plateaux)



@app.route("/reprendre/<int:partie_id>", methods=["POST"])

def reprendre(partie_id):

    state = get_game_state()

    state['game'] = load_game(partie_id)

    state['board'] = state['game'].board

    return jsonify({"ok": True})



def get_ai_move_for(game):

    coups = [col for (_, col, _) in game.board.history]

    key = ''.join(map(str, coups))

    if key in OPENING_BOOK and game.ai_type == "minimax":

        col = OPENING_BOOK[key]

        if not game.board.is_column_full(col):

            return col, []



    if game.ai_type == "random":

        col = game.random_move()

        return col, []

    elif game.ai_type == "bdd":

        col = game.ai_bdd.choisir_coup(game.board)

        return col, []

    else:

        ai_color = game.current_player

        col = game.ai.choose_move(game.board, ai_color)



        scores = []

        if hasattr(game.ai, 'scores') and game.ai.scores:

            for c, s in enumerate(game.ai.scores):

                if s is not None:

                    scores.append((c, s))



        return col, scores



if __name__ == "__main__":

    app.run(host="0.0.0.0", port=10000, debug=True)