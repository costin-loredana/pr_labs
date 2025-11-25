import sys
import os
import asyncio
from quart import Quart, Response, jsonify

from src.board import Board
from src.player import PlayerState
from src.card import CardState
from src.commands import look, flip, watch, map

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT_DIR, "public")

app = Quart(__name__, static_folder=PUBLIC_DIR)

board: Board | None = None



def format_board(board: Board, view):
    """
    Convert board view to MIT PS4 plain-text.
    Format:
        RxC
        status [value]
        status [value]
    """
    lines = [f"{board._rows}x{board._cols}"]

    for r in range(board._rows):
        for c in range(board._cols):
            token = view[r][c]
            card = board._grid[r][c]

            if token in ("down", "none"):
                lines.append(token)
            else:
                # up A, my A
                lines.append(f"{token} {card.value}")

    return "\n".join(lines)


@app.get("/look/<player_id>")
async def look_endpoint(player_id: str):
    global board

    try:
        board._players.setdefault(player_id, PlayerState())
        view = await look(board, player_id)
        txt = format_board(board, view)
        return Response(txt, content_type="text/plain")

    except Exception as e:
        print("LOOK ERROR:", e)
        return Response(f"Look error: {e}", status=500)


@app.get("/watch/<player_id>")
async def watch_endpoint(player_id: str):
    global board

    try:
        board._players.setdefault(player_id, PlayerState())

        try:
            view = await asyncio.wait_for(watch(board, player_id), timeout=30.0)
            txt = format_board(board, view)
            return Response(txt, content_type="text/plain")
        except asyncio.TimeoutError:
            print(f"[WATCH] Timeout for player {player_id}, returning current state")
            view = await look(board, player_id)
            txt = format_board(board, view)
            return Response(txt, content_type="text/plain")

    except Exception as e:
        print("WATCH ERROR:", e)
        try:
            view = await look(board, player_id)
            txt = format_board(board, view)
            return Response(txt, content_type="text/plain")
        except Exception as inner_e:
            print("WATCH FALLBACK ERROR:", inner_e)
            return Response("Watch error", status=500)


@app.get("/flip/<player_id>/<int:row>,<int:col>")
async def flip_endpoint(player_id: str, row: int, col: int):
    global board

    try:
        board._players.setdefault(player_id, PlayerState())
        result = await flip(board, player_id, row, col)

        if result == "fail":
            return Response("flip failed", status=409)

        view = await look(board, player_id)
        txt = format_board(board, view)
        return Response(txt, content_type="text/plain")

    except Exception as e:
        print("FLIP ERROR:", e)
        return Response(f"Flip error: {e}", status=500)



@app.get("/map/<player_id>/<operation>")
async def map_endpoint(player_id: str, operation: str):
    global board

    try:
        board._players.setdefault(player_id, PlayerState())

        if operation == "upper":
            async def f(x): return x.upper()

        elif operation == "lower":
            async def f(x): return x.lower()

        elif operation == "reverse":
            async def f(x): return x[::-1]

        else:
            return Response(f"Unknown map op '{operation}'", status=400)

        txt = await map(board, player_id, f)
        return Response(txt, content_type="text/plain")

    except Exception as e:
        print("MAP ERROR:", e)
        return Response(f"Map error: {e}", status=500)


@app.get("/replace/<player_id>/<old>/<new>")
async def replace_endpoint(player_id: str, old: str, new: str):
    global board

    try:
        board._players.setdefault(player_id, PlayerState())

        count = 0
        for r, c, card in board.iter_positions():
            if card.state != CardState.REMOVED and card.value == old:
                board.set_card_value(r, c, new)
                count += 1

        view = await look(board, player_id)
        txt = format_board(board, view)

        print(f"[DEBUG] REPLACE {old} → {new}: {count} cards changed")
        return Response(txt, content_type="text/plain")

    except Exception as e:
        print("REPLACE ERROR:", e)
        return Response(f"Replace error: {e}", status=500)


@app.get("/restart")
async def restart_endpoint():
    global board

    try:
        if board is None or not hasattr(board, "_filename"):
            return Response("Cannot restart - no board file", status=400)

        print("[RESTART] Resetting board...")

        filename = board._filename

        new_board = await Board.parseFromFile(filename)
        new_board._filename = filename

        new_board._change_count = 1

        board = new_board

        print("[RESTART] Board successfully reset.")
        return Response("Game restarted", status=200)

    except Exception as e:
        print("RESTART ERROR:", e)
        return Response(f"Restart error: {e}", status=500)



@app.get("/debug")
async def debug_board():
    global board

    if board is None:
        return jsonify({"error": "Board not loaded"})

    return jsonify({
        "rows": board._rows,
        "cols": board._cols,
        "players": list(board._players.keys()),
        "grid": [
            [
                {
                    "pos": (r, c),
                    "value": board._grid[r][c].value,
                    "state": board._grid[r][c].state.value,
                    "controller": board._grid[r][c].controller,
                }
                for c in range(board._cols)
            ]
            for r in range(board._rows)
        ],
        "change_count": board._change_count
    })



@app.get("/")
async def index():
    return await app.send_static_file("index.html")


async def startup(filename: str):
    global board
    board = await Board.parseFromFile(filename)
    board._filename = filename
    print(f"Loaded board: {board._rows}x{board._cols}")
    print(f"Watch support: ENABLED")



def main():
    if len(sys.argv) < 3:
        print("Usage: python -m src.server PORT BOARD_FILE")
        sys.exit(1)

    port = int(sys.argv[1])
    filename = sys.argv[2]

    asyncio.run(startup(filename))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )


if __name__ == "__main__":
    main()
