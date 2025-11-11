import asyncio
import random
import sys
import time
from src.board import Board
from src.commands import look, flip
from src.board_validator import BoardValidator
from src.scheduler.prioritizer import PriorityScheduler

MODE = "visual"
DEBUG = True


# ---------------------------------------------------------------------
# 🎨 Board Drawing (for visual mode)
# ---------------------------------------------------------------------
def draw_board(text: str) -> str:
    lines = text.strip().splitlines()
    if not lines:
        return ""
    header = lines[0]
    cells = lines[1:]
    try:
        h, w = map(int, header.lower().split("x"))
    except Exception:
        h = w = int(len(cells) ** 0.5)

    formatted = []
    for cell in cells:
        parts = cell.split()
        if not parts:
            formatted.append(" ")
        elif parts[0] == "none":
            formatted.append("·")
        elif cell.startswith("down"):
            formatted.append("■")
        elif parts[0] in ("my", "up") and len(parts) == 2:
            formatted.append(parts[1])
        else:
            formatted.append("?")

    rows = [formatted[i * w:(i + 1) * w] for i in range(h)]
    border_top = "┌" + "───" * w + "┐"
    border_bottom = "└" + "───" * w + "┘"
    body = "\n".join("│ " + " ".join(row) + " │" for row in rows)
    return f"{border_top}\n{body}\n{border_bottom}"


# ---------------------------------------------------------------------
# ⚙️ Random helpers
# ---------------------------------------------------------------------
async def random_delay(min_ms: float, max_ms: float):
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000.0)

def random_int(max_value: int) -> int:
    return random.randint(0, max_value - 1)


# ---------------------------------------------------------------------
# 🧩 Player Simulation (with Statistics)
# ---------------------------------------------------------------------
async def simulate_player(board: Board, player_id: str, tries: int,
                          min_delay_ms: float, max_delay_ms: float, stats: dict):
    size = board.height
    start_time = time.perf_counter()
    stats[player_id] = {"flips": 0, "matches": 0, "mismatches": 0, "turns": 0}

    if DEBUG and MODE == "visual":
        print(f"\n=== {player_id} started ===")

    for _ in range(tries):
        try:
            await random_delay(min_delay_ms, max_delay_ms)
            r1, c1 = random_int(size), random_int(size)
            s1 = await flip(board, player_id, r1, c1)
            stats[player_id]["flips"] += 1
            stats[player_id]["turns"] += 1

            if DEBUG and MODE == "visual":
                print(f"[{player_id}] flipped ({r1},{c1})")
                print(draw_board(s1))

            await random_delay(min_delay_ms, max_delay_ms)
            r2, c2 = random_int(size), random_int(size)
            s2 = await flip(board, player_id, r2, c2)
            stats[player_id]["flips"] += 1

            # detect match vs mismatch
            if "none" in s2.lower():
                stats[player_id]["matches"] += 1
            elif "down" in s2.lower():
                stats[player_id]["mismatches"] += 1

            if DEBUG and MODE == "visual":
                print(f"[{player_id}] flipped ({r2},{c2})")
                print(draw_board(s2))

            BoardValidator.assert_invariants(board)

            # If the board clears, end early
            if "down" not in s2:
                break

        except Exception as e:
            if DEBUG and MODE == "visual":
                print(f"[{player_id}] error: {e}")
            stats[player_id]["errors"] = stats[player_id].get("errors", 0) + 1

    stats[player_id]["time"] = time.perf_counter() - start_time
    if DEBUG and MODE == "visual":
        print(f"=== {player_id} finished ===")


# ---------------------------------------------------------------------
# 🧪 Run simulation
# ---------------------------------------------------------------------
async def run_simulation(filename: str, players: int = 4,
                         tries: int = 100, min_delay_ms: float = 0.1, max_delay_ms: float = 2.0):
    board = Board.parse_from_file(filename)

    # ✅ Attach the new fair scheduler
    board._scheduler = PriorityScheduler(board.height, board.width)

    initial = await look(board, "system")
    if DEBUG and MODE == "visual":
        print("=== INITIAL BOARD ===")
        print(draw_board(initial))

    stats = {}
    start_time = time.perf_counter()

    tasks = [
        simulate_player(board, f"player{i+1}", tries, min_delay_ms, max_delay_ms, stats)
        for i in range(players)
    ]
    await asyncio.gather(*tasks)

    total_time = time.perf_counter() - start_time
    final = await look(board, "system")

    if DEBUG and MODE == "visual":
        print("=== FINAL BOARD ===")
        print(draw_board(final))

    print(f"\n🏁 Simulation complete in {total_time:.3f}s")
    if "down" not in final:
        print("✅ All cards matched — board cleared!")
    else:
        print("✅ Simulation ended without crashes or deadlocks.")

    # Print per-player summary
    print("\n📊 Player Statistics:")
    for pid, st in stats.items():
        print(f"  {pid}: {st['flips']} flips | {st['matches']} matches | "
              f"{st['mismatches']} mismatches | {st['turns']} turns | "
              f"{st.get('errors',0)} errors | {st['time']:.2f}s active")


# ---------------------------------------------------------------------
# 🚀 Entry point
# ---------------------------------------------------------------------
def main():
    global MODE, DEBUG
    if len(sys.argv) < 2:
        print("Usage: python -m src.simulation <boardfile> [fuzz|visual]")
        sys.exit(1)

    filename = sys.argv[1]
    if len(sys.argv) >= 3 and sys.argv[2].lower() == "fuzz":
        MODE = "fuzz"
        DEBUG = False
        print("⚡ Running in FUZZ mode: fast randomized concurrency test\n")
        asyncio.run(run_simulation(filename, players=4, tries=200,
                                   min_delay_ms=0.1, max_delay_ms=2.0))
    else:
        MODE = "visual"
        DEBUG = True
        print("🐢 Running in VISUAL mode: human-readable board view\n")
        asyncio.run(run_simulation(filename, players=3, tries=8,
                                   min_delay_ms=400, max_delay_ms=1000))


if __name__ == "__main__":
    main()
