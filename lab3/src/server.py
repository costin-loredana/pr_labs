# src/server.py
import sys
import os
from flask import Flask, Response, send_from_directory, request
from http import HTTPStatus
import asyncio
from src.board import Board
from src.commands import look, flip, map as map_command
from src.commands import watch as watch_command


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT_DIR, "public")

app = Flask(__name__, static_folder=PUBLIC_DIR)
board = None


# ----------------------------------------------------------
# Endpoints asincrone — folosesc doar commands.py
# ----------------------------------------------------------

@app.route("/look/<player_id>")
async def look_endpoint(player_id: str):
    """Returnează vizualizarea tablei pentru jucător."""
    try:
        result = await look(board, player_id)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route("/flip/<player_id>/<int:row>,<int:col>")
async def flip_endpoint(player_id: str, row: int, col: int):
    """Încearcă să întoarcă cartea (row, col) pentru jucător."""
    try:
        result = await flip(board, player_id, row, col)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Flip error: {e}", status=HTTPStatus.CONFLICT, mimetype="text/plain")
    

@app.route("/replace/<player_id>/<old_value>/<new_value>")
async def replace_endpoint(player_id: str, old_value: str, new_value: str):
    """
    Handles GET /replace/<player>/<from>/<to> from the web client.
    Delegates to commands.map(), which calls BoardOps.map().
    """
    try:
        result = await map_command(board, old_value, new_value)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Replace error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route("/watch/<player_id>")
async def watch_endpoint(player_id: str):
    """Waits until the next board change, then returns it."""
    try:
        result = await watch_command(board, player_id)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Watch error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)



# ----------------------------------------------------------
# Restart board endpoint
# ----------------------------------------------------------
@app.route("/restart")
async def restart_endpoint():
    global board
    try:
        filename = sys.argv[2]
        # clean up all old waiters/watchers
        if board:
            for q in getattr(board, "_waiters", {}).values():
                while q:
                    fut = q.popleft()
                    if not fut.done():
                        fut.set_result(True)
            for fut in getattr(board, "_watchers", []):
                if not fut.done():
                    fut.set_result(True)
        # create new board
        board = Board.parse_from_file(filename)
        print(f"Board restarted from {filename}")
        result = await look(board, "system")
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Restart error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)

    



# ----------------------------------------------------------
# Frontend static
# ----------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


# ----------------------------------------------------------
# Main entry
# ----------------------------------------------------------
def main():
    global board
    if len(sys.argv) < 3:
        raise ValueError("Usage: python src/server.py PORT FILENAME")

    port = int(sys.argv[1])
    filename = sys.argv[2]
    board = Board.parse_from_file(filename)

    print(f"Starting Memory Scramble server on port {port}...")
    print(f"Loaded board from {filename}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
