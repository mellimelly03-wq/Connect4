from flask import Flask, render_template, request, jsonify
import sys
import os
import json


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p) != SITE_DIR and p != '']
sys.path.insert(0, BASE_DIR)

from board import Board
from game import Game
from game_repository import save_game_from_board, get_parties, get_situations, load_game
from ai_bdd import AIBaseDeDonnees


app = Flask(__name__)

with open(os.path.join(BASE_DIR, "config.json"), "r") as f:
    cfg = json.load(f)["config"]

ROWS = cfg["rows"]
COLS = cfg["cols"]

board = Board(ROWS, COLS)
game = None

@app.route("/")
def index():
    grid = board.grid
    resumed = game is not None and not game.game_over
    mode = game.mode if game else None
    return render_template("game.html", rows=ROWS, cols=COLS, grid=grid, resumed=resumed, mode=mode)


@app.route("/start", methods=["POST"])
def start():
    global game, board
    data = request.json
    mode = data["mode"]
    ai_type = data["ai_type"]
    depth = int(data["depth"])
    starting = int(data["starting"])
    board.reset()
    game = Game(board, starting, mode)
    game.ai_type = ai_type
    if ai_type == "minimax":
        game.ai.depth = depth
    elif ai_type == "bdd":
        game.ai_bdd = AIBaseDeDonnees(couleur="JAUNE" if starting == 1 else "ROUGE")
    return jsonify({"grid": board.grid})


@app.route("/move", methods=["POST"])
def move():
    global game
    if not game or game.game_over or game.paused:
        return jsonify({"error": "invalid"})
    col = int(request.json["col"])
    if game.board.is_column_full(col):
        return jsonify({"error": "full", "grid": game.board.grid})
    winner = game.play_turn(col)
    scores = []
    if game.mode == "human_vs_ai" and not game.game_over:
        ai_col, scores = get_ai_move()
        ai_winner = game.play_turn(ai_col)
        if ai_winner:
            winner = ai_winner
    return jsonify({
        "grid": game.board.grid,
        "winner": winner,
        "scores": scores,
        "winning_cells": game.board.winning_cells,
        "draw": game.board.is_full()
    })


@app.route("/ai_move", methods=["POST"])
def ai_move():
    global game
    if not game or game.game_over or game.paused:
        return jsonify({"error": "invalid"})
    col, scores = get_ai_move()
    winner = game.play_turn(col)
    return jsonify({
        "grid": game.board.grid,
        "winner": winner,
        "scores": scores if game.ai_type == "minimax" else [],
        "winning_cells": game.board.winning_cells,
        "draw": game.board.is_full()
    })


@app.route("/undo", methods=["POST"])
def undo():
    if game:
        game.undo()
    return jsonify({"grid": board.grid})


@app.route("/restart", methods=["POST"])
def restart():
    if game:
        game.restart()
    return jsonify({"grid": board.grid})


@app.route("/pause", methods=["POST"])
def pause():
    if game:
        game.pause()
    return jsonify({"status": "paused"})


@app.route("/resume", methods=["POST"])
def resume():
    if game:
        game.resume()
    return jsonify({"status": "resumed"})


@app.route("/save", methods=["POST"])
def save():
    if game:
        return jsonify(save_game_from_board(game))
    return jsonify({"error": "no_game"})


@app.route("/ai_suggest", methods=["POST"])
def ai_suggest():
    if not game:
        return jsonify({"col": None})
    col, _ = get_ai_move()
    return jsonify({"col": col})


def get_ai_move():
    if game.ai_type == "random":
        col = game.random_move()
        return col, []
    elif game.ai_type == "bdd":
        col = game.ai_bdd.choisir_coup(game.board)
        return col, []
    else:
        col = game.ai.choose_move(game.board)
        scores = game.ai.scores
        return col, scores



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
    global game, board
    game = load_game(partie_id)
    board = game.board
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)