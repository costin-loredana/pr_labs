import sys
import os
from http import HTTPStatus

from flask import Flask, Response, send_from_directory

from src.board import Board
from src.commands import look, flip, map as map_command, watch


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT_DIR, "public")

app = Flask(__name__, static_folder=PUBLIC_DIR)

board: Board | None = None


@app.route("/look/<player_id>")
async def look_endpoint(player_id: str):
    """
    Returneaza starea vizibila a tablei pentru player-ul dat.
    NU asteapta, doar citeste.
    """
    try:
        result = await look(board, player_id)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Look error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)



@app.route("/flip/<player_id>/<int:row>,<int:col>")
async def flip_endpoint(player_id: str, row: int, col: int):
    """
    Aplica regulile de joc (1A–3B) pentru un flip.
    """
    try:
        result = await flip(board, player_id, row, col)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except RuntimeError as e:
        # mesaje gen "You are in a queue..."
        return Response(str(e), status=HTTPStatus.CONFLICT, mimetype="text/plain")
    except Exception as e:
        return Response(f"Flip error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


@app.route("/replace/<player_id>/<old_value>/<new_value>")
async def replace_endpoint(player_id: str, old_value: str, new_value: str):
    """
    Inlocuieste toate cartile cu valoarea old_value cu new_value.
    Foloseste BoardOps.replace/map.
    """
    try:
        result = await map_command(board, old_value, new_value)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Replace error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)



@app.route("/watch/<player_id>")
async def watch_endpoint(player_id: str):
    """
    Watch pentru schimbari pe board.
    NU returneaza imediat, asteapta pana cand:
      - se schimba starea unei carti (DOWN <-> UP, REMOVE, sau valoare schimbata)
    Apoi intoarce look(board, player).
    Daca nu se intampla nimic intr-un anumit timeout, intoarce tot board-ul.
    """
    try:
        result = await watch(board, player_id)
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")
    except Exception as e:
        return Response(f"Watch error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)



@app.route("/restart")
async def restart_endpoint():
    """
    Reincarca fisierul de board si reseteaza toata starea dinamica:
      - scheduler
      - watchers
      - locks
      - players
      - pending turns
    """
    global board
    try:
        if len(sys.argv) < 3:
            return Response("Server was not started with a board file.",
                            status=HTTPStatus.INTERNAL_SERVER_ERROR)

        filename = sys.argv[2]

        # Trezeste watcher-ii vechi (daca exista) ca sa nu ramana await-uri blocate
        if board is not None and hasattr(board, "_watchers") and board._watchers:
            for fut in board._watchers:
                if not fut.done():
                    fut.set_result(True)
            board._watchers.clear()

        # Incarca un nou board din fisier
        board = Board.parse_from_file(filename)

        # Reset complet al runtime-ului; 
        board._scheduler = None
        board._watchers = []     
        board._locks = None
        board._players = {}
        board._pending = {}

        result = await look(board, "system")
        return Response(result, status=HTTPStatus.OK, mimetype="text/plain")

    except Exception as e:
        return Response(f"Restart error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)



@app.route("/")
def index():
    """
    Serveste UI-ul Memory Scramble: index.html din public/
    """
    return send_from_directory(PUBLIC_DIR, "index.html")



@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add(
        "Access-Control-Allow-Headers",
        "Content-Type,Authorization",
    )
    response.headers.add(
        "Access-Control-Allow-Methods",
        "GET,PUT,POST,DELETE,OPTIONS",
    )
    return response



def main():
    global board

    if len(sys.argv) < 3:
        raise ValueError("Usage: python -m src.server PORT FILENAME")

    port = int(sys.argv[1])
    filename = sys.argv[2]

    board = Board.parse_from_file(filename)

    print("===============================================")
    print("     Memory Scramble Server (Flask async)      ")
    print("===============================================")
    print(f"Port:        {port}")
    print(f"Board file:  {filename}")
    print("-----------------------------------------------")
    print(f"  GET /look/<player_id>")
    print(f"  GET /flip/<player_id>/<row>,<col>")
    print(f"  GET /watch/<player_id>")
    print(f"  GET /replace/<player_id>/<old>/<new>")
    print(f"  GET /restart")
    print("===============================================")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        threaded=False,
    )


if __name__ == "__main__":
    main()
