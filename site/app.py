from flask import Flask, render_template, request, jsonify
import sys
import os
import json
import time

sys.path.append(os.path.abspath(".."))

from board import Board, RED, YELLOW
from game import Game
from game_repository import save_game_from_board

app = Flask(__name__)

with open("../config.json", "r") as f:
    cfg = json.load(f)["config"]

ROWS = cfg["rows"]
COLS = cfg["cols"]

board = Board(ROWS, COLS)
game = None


@app.route("/")
def index():
    return render_template("game.html", rows=ROWS, cols=COLS, grid=board.grid)


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

    return jsonify({"grid": board.grid})


@app.route("/move", methods=["POST"])
def move():
    global game

    if not game or game.game_over or game.paused:
        return jsonify({"error": "invalid"})

    col = int(request.json["col"])

    # 🔴 Colonne pleine
    if game.board.is_column_full(col):
        return jsonify({
            "error": "full",
            "grid": game.board.grid
        })

    winner = game.play_turn(col)

    # 🔥 HUMAN VS AI
    if game.mode == "human_vs_ai" and not game.game_over:
        ai_col = game.ai_move()
        winner = game.play_turn(ai_col)

    # 🔥 AI VS AI → boucle automatique
    if game.mode == "ai_vs_ai":
        ai_col = game.ai_move()
        winner = game.play_turn(ai_col)
        time.sleep(0.5)   # 0.5 seconde entre coups

    return jsonify({
        "grid": game.board.grid,
        "winner": winner,
        "scores": game.ai.scores if game.ai_type == "minimax" else [],
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
        result = save_game_from_board(game)
        return jsonify(result)
    return jsonify({"error": "no_game"})


@app.route("/ai_suggest", methods=["POST"])
def ai_suggest():
    if not game:
        return jsonify({"col": None})

    if game.ai_type == "random":
        col = game.random_move()
    else:
        col = game.ai.choose_move(board)

    return jsonify({"col": col})
def get_ai_move():
    if game.ai_type == "random":
        col = game.random_move()
        return col, []
    else:
        col, scores = game.ai.choose_move_with_scores(board)
        return col, scores


if __name__ == "__main__":
    app.run(debug=True)