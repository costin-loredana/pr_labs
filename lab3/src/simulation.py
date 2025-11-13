import asyncio
import random
import sys
import time
from src.board import Board
from src.board_ops import BoardOps
from src.board_validator import BoardValidator
from src.scheduler.prioritizer import PriorityScheduler

MODE = "visual"
DEBUG = True



def draw_board(text: str) -> str:
    """
    Convert board text representation to ASCII art visualization.
    
    Requires:
      - text is a valid board string from BoardOps.look() with format:
        "heightxwidth"
        "cell1_state"
        "cell2_state"
        ...
    
    Effects:
      - Returns ASCII art representation of the board
      - Converts:
        * "none" → "."
        * "down ?" → "#" 
        * "my value" or "up value" → "value"
        * Unknown formats → "?"
      - Creates bordered grid with proper dimensions
      - Returns empty string if input is empty
    """
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
            formatted.append(".")
        elif cell.startswith("down"):
            formatted.append("#")
        elif parts[0] in ("my", "up") and len(parts) == 2:
            formatted.append(parts[1])
        else:
            formatted.append("?")

    rows = [formatted[i * w:(i + 1) * w] for i in range(h)]
    border_top = "+" + "---" * w + "+"
    border_bottom = "+" + "---" * w + "+"
    body = "\n".join("| " + " ".join(row) + " |" for row in rows)
    return f"{border_top}\n{body}\n{border_bottom}"


async def random_delay(min_ms: float, max_ms: float):
    """
    Effects:
      - Pauses execution for random.uniform(min_ms, max_ms) milliseconds
      - Converts milliseconds to seconds for asyncio.sleep()
    """
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000.0)

def random_int(max_value: int) -> int:
    """
    Generate random integer in range [0, max_value-1].
    Effects:
      - Returns random integer where 0 <= result < max_value
      - Uses random.randint() for uniform distribution
    """
    return random.randint(0, max_value - 1)


async def simulate_player(board: Board, player_id: str, tries: int,
                          min_delay_ms: float, max_delay_ms: float, stats: dict):
    """
    Simulate a player making random moves with timing and statistics.
    Requires:
      - board is properly initialized Board instance
      - player_id is unique string identifier
      - tries > 0 (number of turn attempts)
      - 0 <= min_ms <= max_ms (delay range)
      - stats is mutable dictionary for collecting statistics
    
    Effects:
      - Performs 'tries' number of two-card flip attempts
      - Adds random delays between actions to simulate human timing
      - Updates stats dictionary with:
        * flips: total flip operations attempted
        * matches: successful card matches detected
        * mismatches: failed matches detected  
        * turns: completed turn attempts
        * waits: number of times player had to wait
        * errors: exceptions encountered
        * time: total active simulation time
      - Validates board invariants after each turn
      - Continues simulation even if errors occur
      - Prints progress if in visual mode with DEBUG enabled
    """
    size = board.height
    start_time = time.perf_counter()
    stats[player_id] = {"flips": 0, "matches": 0, "mismatches": 0, "turns": 0, "waits": 0, "errors": 0}

    if DEBUG and MODE == "visual":
        print(f"\n=== {player_id} started ===")

    for turn in range(tries):
        try:
            await random_delay(min_delay_ms, max_delay_ms)
            r1, c1 = random_int(size), random_int(size)
            
            result1 = await BoardOps.flip(board, player_id, r1, c1)
            stats[player_id]["flips"] += 1
            stats[player_id]["turns"] += 1
            
            if "wait" in result1.lower():
                stats[player_id]["waits"] += 1

            if DEBUG and MODE == "visual":
                print(f"[{player_id}] turn {turn+1}: flipped ({r1},{c1})")
                if "wait" not in result1.lower():
                    board_state = await BoardOps.look(board, player_id)
                    print(draw_board(board_state))

            await random_delay(min_delay_ms, max_delay_ms)
            r2, c2 = random_int(size), random_int(size)
            
            result2 = await BoardOps.flip(board, player_id, r2, c2)
            stats[player_id]["flips"] += 1
            
            if "wait" in result2.lower():
                stats[player_id]["waits"] += 1

            board_state = await BoardOps.look(board, player_id)
            if "my" in result2.lower() and "my" in result1.lower():
                lines = board_state.splitlines()
                controlled_cards = [line for line in lines if "my" in line]
                if len(controlled_cards) == 2:
                    stats[player_id]["matches"] += 1
                else:
                    stats[player_id]["mismatches"] += 1
            elif "controlled" in result2.lower() or "no card" in result2.lower():
                stats[player_id]["mismatches"] += 1

            if DEBUG and MODE == "visual":
                print(f"[{player_id}] flipped ({r2},{c2})")
                if "wait" not in result2.lower():
                    print(draw_board(board_state))

            BoardValidator.assert_invariants(board)

        except Exception as e:
            if DEBUG and MODE == "visual":
                print(f"[{player_id}] error: {e}")
            stats[player_id]["errors"] += 1

    stats[player_id]["time"] = time.perf_counter() - start_time
    if DEBUG and MODE == "visual":
        print(f"=== {player_id} finished ===")



async def fast_simulate_player(board: Board, player_id: str, moves: int):
    """
    High-performance fuzz testing without delays or validation.
    
    Requires:
      - board is properly initialized Board instance  
      - player_id is unique string identifier
      - moves > 0 (number of two-card flip operations)
    
    Effects:
      - Performs 'moves' number of rapid two-card flip operations
      - No delays between operations for maximum throughput
      - No board validation or statistics beyond error counting
      - Returns number of exceptions encountered during execution
      - Continues execution even when errors occur
      - Designed for stress testing concurrent access patterns
    """
    size = board.height
    errors = 0
    
    for _ in range(moves):
        try:
            r1, c1 = random.randint(0, size-1), random.randint(0, size-1)
            await BoardOps.flip(board, player_id, r1, c1)
            
            r2, c2 = random.randint(0, size-1), random.randint(0, size-1)
            await BoardOps.flip(board, player_id, r2, c2)
            
        except Exception:
            errors += 1
    
    return errors


async def run_simulation(filename: str, players: int = 4,
                         tries: int = 100, min_delay_ms: float = 0.1, max_delay_ms: float = 2.0):
    """
    Run comprehensive simulation with multiple players and detailed statistics.
    
    Requires:
      - filename is valid path to board definition file
      - players > 0 (number of concurrent players)
      - tries > 0 (turns per player) 
      - 0 <= min_delay_ms <= max_delay_ms (action timing range)
    
    Effects:
      - Loads board from file and initializes game state
      - Runs specified number of players concurrently
      - Collects detailed statistics for each player
      - Prints initial and final board states in visual mode
      - Reports simulation results including:
        * Total execution time
        * Board clearance status
        * Per-player flip, match, wait, error counts
        * Aggregate statistics
      - Catches and reports simulation-level exceptions
      - Validates no crashes or deadlocks occurred
    """
    board = Board.parse_from_file(filename)

    board._scheduler = PriorityScheduler(board.height, board.width)
    board._pending = {}
    board._players = {}
    board._watchers = []

    initial = await BoardOps.look(board, "system")
    if DEBUG and MODE == "visual":
        print("=== INITIAL BOARD ===")
        print(draw_board(initial))

    stats = {}
    start_time = time.perf_counter()

    tasks = [
        simulate_player(board, f"player{i+1}", tries, min_delay_ms, max_delay_ms, stats)
        for i in range(players)
    ]
    
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"Simulation error: {e}")

    total_time = time.perf_counter() - start_time
    final = await BoardOps.look(board, "system")

    if DEBUG and MODE == "visual":
        print("=== FINAL BOARD ===")
        print(draw_board(final))

    print(f"\nSimulation complete in {total_time:.3f}s")
    
    if "down" not in final and "up" not in final:
        print("All cards matched - board cleared!")
    else:
        remaining_down = final.lower().count("down")
        remaining_up = final.lower().count("up")
        print(f"Simulation ended with {remaining_down} cards face down and {remaining_up} cards face up")

    print("\nPlayer Statistics:")
    for pid, st in stats.items():
        print(f"  {pid}: {st['flips']} flips | {st['matches']} matches | "
              f"{st['mismatches']} mismatches | {st['waits']} waits | "
              f"{st['turns']} turns | {st['errors']} errors | {st['time']:.2f}s active")
    
    total_flips = sum(st['flips'] for st in stats.values())
    total_errors = sum(st['errors'] for st in stats.values())
    total_waits = sum(st['waits'] for st in stats.values())
    print(f"\nTotals: {total_flips} flips | {total_waits} waits | {total_errors} errors")
    
    if total_errors == 0:
        print("SUCCESS: No crashes or deadlocks detected!")
    else:
        print(f"NOTE: {total_errors} errors occurred during simulation")



async def run_fast_fuzz(filename: str, players: int = 4, moves_per_player: int = 250):
    """
    Run high-performance fuzz test to stress concurrent system limits.
    
    Requires:
      - filename is valid path to board definition file
      - players > 0 (number of concurrent players)
      - moves_per_player > 0 (operations per player)
    
    Effects:
      - Loads board and performs minimal initialization
      - Runs players concurrently with maximum operation density
      - Measures performance in flips per second
      - Returns True if performance exceeds 1000 flips/second target
      - Reports:
        * Total operations and execution time
        * Operations per second
        * Error count
        * Performance target achievement
      - Designed to identify concurrency bottlenecks and race conditions
    """
    board = Board.parse_from_file(filename)
    
    board._scheduler = PriorityScheduler(board.height, board.width)
    board._pending = {}
    board._players = {}
    board._watchers = []
    
    print(f"FAST FUZZ TEST: {players} players × {moves_per_player} moves = {players * moves_per_player * 2} total flips")
    
    start_time = time.perf_counter()
    
    tasks = [
        fast_simulate_player(board, f"p{i}", moves_per_player)
        for i in range(players)
    ]
    
    error_counts = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time
    
    total_flips = players * moves_per_player * 2
    total_errors = sum(error_counts)
    flips_per_second = total_flips / total_time
    
    print(f"RESULTS:")
    print(f"   Time: {total_time:.3f}s")
    print(f"   Flips/sec: {flips_per_second:,.0f}")
    print(f"   Total flips: {total_flips}")
    print(f"   Errors: {total_errors}")
    
    if total_errors == 0:
        print("SUCCESS: No crashes under heavy concurrent load!")
    else:
        print(f"NOTE: {total_errors} errors (acceptable for fuzz testing)")
    
    return flips_per_second > 1000  


def main():
    global MODE, DEBUG
    if len(sys.argv) < 2:
        print("Usage: python -m src.simulation <boardfile> [fuzz|visual|fastfuzz]")
        sys.exit(1)

    filename = sys.argv[1]
    
    if len(sys.argv) >= 3:
        mode = sys.argv[2].lower()
        if mode == "fuzz":
            MODE = "fuzz"
            DEBUG = False
            print("Running in FUZZ mode: randomized concurrency test\n")
            asyncio.run(run_simulation(filename, players=4, tries=100,
                                       min_delay_ms=0.1, max_delay_ms=2.0))
        elif mode == "fastfuzz":
            MODE = "fuzz" 
            DEBUG = False
            print("Running in FAST FUZZ mode: high-performance stress test\n")
            success = asyncio.run(run_fast_fuzz(filename, players=4, moves_per_player=250))
            if success:
                print("Performance target achieved!")
            else:
                print("Performance needs improvement")
        else:
            MODE = "visual"
            DEBUG = True
            print("Running in VISUAL mode: human-readable board view\n")
            asyncio.run(run_simulation(filename, players=3, tries=8,
                                       min_delay_ms=400, max_delay_ms=1000))
    else:
        MODE = "visual"
        DEBUG = True
        print("Running in VISUAL mode: human-readable board view\n")
        asyncio.run(run_simulation(filename, players=3, tries=8,
                                   min_delay_ms=400, max_delay_ms=1000))


if __name__ == "__main__":
    main()