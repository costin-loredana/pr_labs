import asyncio
import random
import time
import traceback
from typing import List, Tuple

from src.board import Board
from src.commands import flip, look

"""
DESIGN:
    - 4 concurrent players making random moves
    - Random delays between 0.1ms and 2ms to simulate real-world timing
    - 100 moves per player (400+ total flip attempts)
    - Continuous verification of *abstract* invariants using look()
    - Comprehensive metrics collection

SAFETY FROM REP EXPOSURE:
    - This module treats Board as a black-box ADT.
    - It NEVER:
        * touches Board._grid, Board._players, or any other private field
        * inspects Card or PlayerState objects directly
        * depends on any internal representation details
    - All reasoning is done via:
        * Board.parseFromFile(...)
        * flip(board, pid, row, col)
        * look(board, pid)
"""

BOARD_FILE = "boards/ab.txt"
PLAYERS = 4
MOVES = 100
MIN_DELAY = 0.0001
MAX_DELAY = 0.002

# Global metrics
total_flips = 0
success_flips = 0
fail_flips = 0
wait_results = 0
exceptions = 0
completed_turns = 0  # times a player successfully completed a two-flip turn

VALID_TOKENS = {"down", "up", "my", "none"}


def sanity_check_view(
    view: List[List[str]],
    expected_rows: int,
    expected_cols: int,
    pid: str,
    seen_none: set | None = None,
) -> None:
    """
    sanity_check_view(view, expected_rows, expected_cols, pid, seen_none) -> None

    PURPOSE:
        Check high-level invariants of the abstract board view returned by look().

    REQUIRES:
        - view is the result of a call to look(board, pid)
        - expected_rows, expected_cols are the dimensions of the board
        - pid is a non-empty player identifier
        - if provided, seen_none is a set of (row, col) positions previously
          observed as removed ("none") for this player

    EFFECTS:
        - Raises AssertionError if a high-level abstract invariant is violated.
        - Does NOT modify the board, the view, or any Board internals.
        - Does NOT access or depend on any private fields of Board, Card, or PlayerState.

    ENSURES:
        - view has the expected rectangular shape
        - all cells contain only valid visibility tokens
        - the number of "my" cells (cards controlled by pid) is at most 2
        - if seen_none is provided, positions previously observed as "none"
          remain "none" in the current view (monotonic removal)
    """
    assert len(view) == expected_rows, f"[{pid}] row count mismatch in view"
    for row in view:
        assert len(row) == expected_cols, f"[{pid}] column count mismatch in view row"

    # Token invariants and monotonic 'none' tracking
    my_count = 0
    if seen_none is not None:
        # Update seen_none with any new "none" cells in this view
        for r in range(expected_rows):
            for c in range(expected_cols):
                cell = view[r][c]
                assert (
                    cell in VALID_TOKENS
                ), f"[{pid}] invalid visibility token {cell!r} at ({r},{c})"

                if cell == "my":
                    my_count += 1
                if cell == "none":
                    seen_none.add((r, c))

        # Positions previously seen as "none" must stay "none"
        for (r, c) in seen_none:
            assert (
                view[r][c] == "none"
            ), f"[{pid}] removed cell ({r},{c}) reappeared as {view[r][c]!r}"
    else:
        for r in range(expected_rows):
            for c in range(expected_cols):
                cell = view[r][c]
                assert (
                    cell in VALID_TOKENS
                ), f"[{pid}] invalid visibility token {cell!r} at ({r},{c})"
                if cell == "my":
                    my_count += 1

    # A player can control at most two cards ("my") at any time
    assert (
        my_count <= 2
    ), f"[{pid}] too many controlled cards: {my_count} 'my' tokens in view"


async def player_task(pid: str, board: Board, rows: int, cols: int) -> None:
    """
    player_task(pid, board, rows, cols) -> None

    PURPOSE:
        Simulate a single player making random moves against the shared board.

    REQUIRES:
        - pid is a non-empty string uniquely identifying the player
        - board is a valid Board instance created by Board.parseFromFile
        - rows, cols are the dimensions of the board as observed via look()

    EFFECTS:
        - Performs MOVES flip attempts with small random delays between them.
        - Updates global statistics counters:
            total_flips, success_flips, fail_flips, wait_results,
            completed_turns, exceptions
        - Uses ONLY the abstract commands API: flip() and look().
        - Prints progress information for each attempted flip.
        - Catches and reports exceptions without crashing the whole program.

    ENSURES:
        - Does NOT access Board._grid, Board._players, or any other private fields.
        - Does NOT inspect Card or PlayerState objects directly.
        - Does NOT rely on any internal representation of Board.
        - Maintains basic abstract invariants over the player's view after each move.
    """
    global total_flips, success_flips, fail_flips, wait_results, exceptions, completed_turns

    # Track which cells this player has ever seen as "none" (removed)
    seen_none: set[Tuple[int, int]] = set()

    for move_num in range(MOVES):
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

        r1 = random.randrange(rows)
        c1 = random.randrange(cols)

        try:
            # First flip attempt
            t0 = time.time()
            res1 = await flip(board, pid, r1, c1)
            elapsed = (time.time() - t0) * 1000.0

            print(f"[SIM] {pid} move#{move_num} flip1 ({r1},{c1}) -> {res1} ({elapsed:.3f} ms)")

            # Check abstract invariants based on the player's view
            view_after_first = await look(board, pid)
            sanity_check_view(view_after_first, rows, cols, pid, seen_none)

            total_flips += 1
            if res1 == "success":
                success_flips += 1
            elif res1 == "fail":
                fail_flips += 1
            elif res1 == "wait":
                wait_results += 1

            # Second flip attempt if first was successful (attempt to complete a turn)
            if res1 == "success":
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

                r2 = random.randrange(rows)
                c2 = random.randrange(cols)

                t0 = time.time()
                res2 = await flip(board, pid, r2, c2)
                elapsed = (time.time() - t0) * 1000.0

                print(f"[SIM] {pid} move#{move_num} flip2 ({r2},{c2}) -> {res2} ({elapsed:.3f} ms)")

                view_after_second = await look(board, pid)
                sanity_check_view(view_after_second, rows, cols, pid, seen_none)

                total_flips += 1
                if res2 == "success":
                    success_flips += 1
                    completed_turns += 1
                elif res2 == "fail":
                    fail_flips += 1
                elif res2 == "wait":
                    wait_results += 1

        except Exception as e:
            exceptions += 1
            print(f"[SIM][ERROR] {pid} move#{move_num} crashed: {e}")
            traceback.print_exc()
            # Continue with next move despite the error


def set_deterministic_seed(seed: int = 42) -> None:
    """
    PURPOSE:
        Make the random behavior of the simulation reproducible.

    REQUIRES:
        - seed is an integer

    EFFECTS:
        - Initializes the random number generator with the given seed.
        - Affects all subsequent calls to random.* in this module.

    ENSURES:
        - Calling this with the same seed makes the simulation behavior
          reproducible *up to* scheduling nondeterminism from asyncio.
        - Does NOT interact with or depend on Board internals in any way.
    """
    random.seed(seed)
    print(f"[SIM] Set deterministic seed: {seed}")


async def run_fuzz() -> None:
    """

    PURPOSE:
        Run a concurrent fuzz test of the board game using only the abstract API.

    REQUIRES:
        - BOARD_FILE exists and is a valid board configuration.
        - Board.parseFromFile is implemented and returns a valid Board.
        - flip() and look() are implemented according to the game specification.

    EFFECTS:
        - Loads a board from BOARD_FILE.
        - Determines the board dimensions using look() for an observer player.
        - Spawns PLAYERS concurrent player_task() coroutines.
        - Collects statistics about flip outcomes and timing.
        - Prints a human-readable summary report at the end.

    ENSURES:
        - The simulation code never:
            * touches Board._grid, Board._players, or any private fields
            * inspects Card or PlayerState objects
            * depends on any particular internal representation
        - All interaction with the game goes through:
            * Board.parseFromFile(...)
            * flip(board, pid, r, c)
            * look(board, pid)
    """
    global total_flips, success_flips, fail_flips, wait_results, exceptions, completed_turns

    print(f"[SIM] Loading board from {BOARD_FILE}")
    board = await Board.parseFromFile(BOARD_FILE)

    # Use the abstract look() API to discover board dimensions for an "observer" player
    observer_id = "observer"
    initial_view = await look(board, observer_id)
    if not initial_view or not initial_view[0]:
        raise RuntimeError("[SIM] Board view is empty or malformed")

    rows = len(initial_view)
    cols = len(initial_view[0])

    # Basic sanity check on the observer view
    sanity_check_view(initial_view, rows, cols, observer_id, seen_none=set())

    print(f"[SIM] Board size (from look): {rows}x{cols}")
    print(f"[SIM] Starting {PLAYERS} players with {MOVES} moves each")
    print(f"[SIM] Delay range: {MIN_DELAY*1000:.1f}ms to {MAX_DELAY*1000:.1f}ms")

    start_time = time.time()

    # Create and run all player tasks concurrently
    tasks = [
        asyncio.create_task(player_task(f"player_{i}", board, rows, cols))
        for i in range(PLAYERS)
    ]

    await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    success_rate = (success_flips / total_flips * 100.0) if total_flips > 0 else 0.0
    flips_per_second = total_flips / elapsed if elapsed > 0.0 else 0.0

    print("\n" + "=" * 60)
    print("FUZZ TEST SUMMARY - ABSTRACT CONCURRENT TEST")
    print("=" * 60)
    print("Configuration:")
    print(f"  Players:                    {PLAYERS}")
    print(f"  Moves per player:           {MOVES}")
    print(f"  Delay range:                {MIN_DELAY*1000:.1f}ms - {MAX_DELAY*1000:.1f}ms")
    print(f"  Board file:                 {BOARD_FILE}")
    print(f"  Board size (from look):     {rows}x{cols}")
    print()
    print("Results:")
    print(f"  Total flip attempts:        {total_flips}")
    print(f"  Successful flips:           {success_flips} ({success_rate:.1f}%)")
    print(f"  Failed flips:               {fail_flips}")
    print(f"  Wait results:               {wait_results}")
    print(f"  Completed turns:            {completed_turns}")
    print(f"  Exceptions (crashes):       {exceptions}")
    print()
    print("Performance:")
    print(f"  Total elapsed time:         {elapsed:.3f} seconds")
    print(f"  Flips per second:           {flips_per_second:.1f}")
    print("=" * 60)

    if exceptions == 0:
        print("[SIM] SUCCESS - Fuzz test completed without crashes")
    else:
        print("[SIM] WARNING - Fuzz test completed with errors (see above)")

    print("=" * 60)


if __name__ == "__main__":
    """
    Main entry point for the abstract concurrent game simulation.

    EFFECTS:
        - Invokes asyncio.run(run_fuzz()).
        - Handles any top-level exceptions.
        - Ensures a clean shutdown of the event loop.

    ENSURES:
        - This script behaves as a *client* of the Board/commands ADT:
            * no access to private fields
            * no dependence on representation details
        - All safety from rep exposure is the responsibility of Board,
          Card, and PlayerState implementations, which are treated here
          as black-box abstract data types.
    """
    try:
        asyncio.run(run_fuzz())
        exit(0)
    except Exception as e:
        print(f"[SIM][FATAL] Top-level exception: {e}")
        traceback.print_exc()
        exit(1)
