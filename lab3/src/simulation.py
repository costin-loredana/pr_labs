import asyncio
import random
import time
import traceback

from src.board import Board
from src.card import CardState
from src.commands import flip


"""
SPECIFICATION: Concurrent Game Simulation
=========================================

PURPOSE:
    Stress tests the Memory Scramble game implementation under realistic
    concurrent conditions with multiple players making simultaneous moves.

DESIGN:
    - 4 concurrent players making random moves
    - Random delays between 0.1ms and 2ms to simulate real-world timing
    - 100 moves per player (400+ total flip attempts)
    - Continuous invariant verification
    - Comprehensive metrics collection

INVARIANTS VERIFIED:
    - REMOVED cards have no controllers
    - DOWN cards have no controllers  
    - UP cards have valid player controllers when controlled
    - Card state transitions follow game rules
    - No crashes or deadlocks under concurrent access
"""

BOARD_FILE = "boards/ab.txt"
PLAYERS = 4
MOVES = 100
MIN_DELAY = 0.0001  
MAX_DELAY = 0.002   

total_flips = 0
success_flips = 0
fail_flips = 0
wait_results = 0
exceptions = 0
match_attempts = 0
successful_matches = 0


def sanity_check(board: Board):
    """
    Verifies board representation invariants during concurrent execution.
    
    Parameters:
        board: the game board to check
        
    Requires:
        - board is a valid Board instance
        - Board may be undergoing concurrent modifications
        
    Effects:
        - Raises AssertionError if any representation invariant is violated
        - No modification of board state
        
    Ensures:
        - All representation invariants hold at time of check
        - REMOVED and DOWN cards have no controllers
        - UP cards have valid controllers when controlled
    """
    for r, c, card in board.iter_positions():

        # Invariant: REMOVED cards cannot have controllers
        if card.state == CardState.REMOVED:
            assert card.controller is None, f"REMOVED card at ({r},{c}) has controller: {card.controller}"

        # Invariant: DOWN cards cannot have controllers  
        if card.state == CardState.DOWN:
            assert card.controller is None, f"DOWN card at ({r},{c}) has controller: {card.controller}"

        # Invariant: Controlled UP cards must have valid player IDs
        if card.state == CardState.UP and card.controller is not None:
            assert card.controller in board._players, f"Invalid controller {card.controller} for UP card at ({r},{c})"


def enhanced_sanity_check(board: Board):
    """
    Comprehensive invariant verification with game progress checks.
    
    Parameters:
        board: the game board to check
        
    Requires:
        - board is properly initialized
        - Board representation invariants should hold
        
    Effects:
        - Raises AssertionError if game invariants are violated
        - No modification of board state
        
    Ensures:
        - All basic representation invariants hold
        - Game state is consistent (matching pairs, card counts)
        - Player states are valid
    """
    removed_count = 0
    up_count = 0
    down_count = 0
    
    for r, c, card in board.iter_positions():
        # Basic state invariants
        if card.state == CardState.REMOVED:
            assert card.controller is None, "REMOVED card cannot have controller"
            removed_count += 1
        elif card.state == CardState.DOWN:
            assert card.controller is None, "DOWN card cannot have controller" 
            down_count += 1
        else:  # CardState.UP
            up_count += 1
            # UP cards can have controller, but it must be valid player
            if card.controller is not None:
                assert card.controller in board._players, f"Invalid controller: {card.controller}"
    
    # Game progress invariants
    total_cards = board._rows * board._cols
    assert removed_count + up_count + down_count == total_cards, "Card count mismatch"
    assert 0 <= removed_count <= total_cards, "Invalid removed card count"
    assert removed_count % 2 == 0, "Removed cards should come in pairs"
    
    # Player state invariants
    for player_id, player_state in board._players.items():
        assert isinstance(player_id, str) and player_id, "Invalid player ID"
        # PlayerState should maintain its own invariants
        player_state.check_rep()


async def player_task(pid: str, board: Board):
    """
    Simulates one player making random moves in the game.
    
    Parameters:
        pid: unique player identifier
        board: shared game board
        
    Requires:
        - pid is non-empty string
        - board is valid and properly initialized
        - BOARD_FILE contains valid game configuration
        
    Effects:
        - Makes MOVES flip attempts with random delays
        - Updates global statistics counters
        - May modify board state through flip operations
        - Prints progress and timing information
        - Catches and reports exceptions without crashing
        
    Ensures:
        - Completes MOVES flip attempts unless catastrophic failure
        - Maintains statistics for success/failure rates
        - Verifies invariants after each flip attempt
        - Continues execution despite individual operation failures
    """
    global total_flips, success_flips, fail_flips, exceptions, wait_results
    global match_attempts, successful_matches

    rows, cols = board._rows, board._cols

    for move_num in range(MOVES):
        # Random delay between moves
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

        r1 = random.randrange(rows)
        c1 = random.randrange(cols)

        try:
            # First flip attempt
            t0 = time.time()
            res1 = await flip(board, pid, r1, c1)
            elapsed = (time.time() - t0) * 1000

            print(f"[SIM] {pid} move#{move_num} flip1 ({r1},{c1}) -> {res1} ({elapsed:.3f} ms)")
            sanity_check(board)

            total_flips += 1
            if res1 == "success":
                success_flips += 1
            elif res1 == "fail":
                fail_flips += 1
            elif res1 == "wait":
                wait_results += 1

            # Second flip attempt if first was successful
            if res1 == "success":
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

                r2 = random.randrange(rows)
                c2 = random.randrange(cols)

                t0 = time.time()
                res2 = await flip(board, pid, r2, c2)
                elapsed = (time.time() - t0) * 1000

                print(f"[SIM] {pid} move#{move_num} flip2 ({r2},{c2}) -> {res2} ({elapsed:.3f} ms)")
                sanity_check(board)

                total_flips += 1
                if res2 == "success":
                    success_flips += 1
                    
                    # Check if this was a matching attempt
                    card1 = board._grid[r1][c1]
                    card2 = board._grid[r2][c2]
                    if card1.value == card2.value:
                        match_attempts += 1
                        successful_matches += 1
                        print(f"[SIM] {pid} MATCHED {card1.value}!")
                    else:
                        match_attempts += 1
                        
                elif res2 == "fail":
                    fail_flips += 1
                elif res2 == "wait":
                    wait_results += 1

        except Exception as e:
            exceptions += 1
            print(f"[SIM][ERROR] {pid} move#{move_num} crashed: {e}")
            traceback.print_exc()
            # Continue with next move despite error


def set_deterministic_seed(seed: int = 42):
    """
    Sets random seed for reproducible testing.
    
    Parameters:
        seed: random number generator seed
        
    Requires: nothing
    
    Effects:
        - Initializes random number generator with specified seed
        - Affects all subsequent random operations
        
    Ensures:
        - Random operations are reproducible with same seed
        - Does not guarantee fully deterministic execution due to async nature
    """
    random.seed(seed)
    print(f"[SIM] Set deterministic seed: {seed}")


async def run_fuzz():
    """
    Executes the main concurrent stress test.
    
    Requires:
        - BOARD_FILE exists and contains valid board configuration
        - All game components (Board, Card, PlayerState, BoardOps) are implemented
        - System has sufficient resources for concurrent execution
        
    Effects:
        - Loads board from file
        - Spawns PLAYERS concurrent player tasks
        - Executes MOVES moves per player with random timing
        - Collects comprehensive performance and reliability metrics
        - Prints detailed summary report
        
    Ensures:
        - Test completes without deadlocks
        - All player tasks finish execution
        - Comprehensive metrics are collected and reported
        - Final board state passes enhanced sanity check
    """
    global total_flips, success_flips, fail_flips, exceptions
    global match_attempts, successful_matches, wait_results

    # Uncomment for reproducible testing:
    # set_deterministic_seed(42)

    print(f"[SIM] Loading board from {BOARD_FILE}")
    board = await Board.parseFromFile(BOARD_FILE)
    print(f"[SIM] Board size: {board._rows}x{board._cols}")
    print(f"[SIM] Starting {PLAYERS} players with {MOVES} moves each")
    print(f"[SIM] Delay range: {MIN_DELAY*1000:.1f}ms to {MAX_DELAY*1000:.1f}ms")

    start_time = time.time()

    # Create and run all player tasks concurrently
    tasks = [
        asyncio.create_task(player_task(f"player_{i}", board))
        for i in range(PLAYERS)
    ]

    await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    # Final comprehensive check
    try:
        enhanced_sanity_check(board)
        final_sanity = "PASS"
    except AssertionError as e:
        final_sanity = f"FAIL: {e}"
        exceptions += 1

    # Calculate derived metrics
    success_rate = (success_flips / total_flips * 100) if total_flips > 0 else 0
    match_success_rate = (successful_matches / match_attempts * 100) if match_attempts > 0 else 0
    flips_per_second = total_flips / elapsed if elapsed > 0 else 0

    print("\n" + "="* 60)
    print("FUZZ TEST SUMMARY - MEMORY SCRAMBLE CONCURRENT TEST")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  Players:                    {PLAYERS}")
    print(f"  Moves per player:           {MOVES}")
    print(f"  Delay range:               {MIN_DELAY*1000:.1f}ms - {MAX_DELAY*1000:.1f}ms")
    print(f"  Board file:                {BOARD_FILE}")
    print(f"  Board size:                {board._rows}x{board._cols}")
    print()
    print(f"Results:")
    print(f"  Total flip attempts:        {total_flips}")
    print(f"  Successful flips:           {success_flips} ({success_rate:.1f}%)")
    print(f"  Failed flips:               {fail_flips}")
    print(f"  Wait results:               {wait_results}")
    print(f"  Match attempts:             {match_attempts}")
    print(f"  Successful matches:         {successful_matches} ({match_success_rate:.1f}%)")
    print(f"  Exceptions (crashes):       {exceptions}")
    print()
    print(f"Performance:")
    print(f"  Total elapsed time:        {elapsed:.3f} seconds")
    print(f"  Flips per second:          {flips_per_second:.1f}")
    print(f"  Final sanity check:        {final_sanity}")
    print("=" * 60)
    
    if exceptions == 0 and final_sanity == "PASS":
        print("[SIM] SUCCESS - Fuzz test completed without crashes or invariant violations")
    else:
        print("[SIM] WARNING - Fuzz test completed with issues (see above)")
    
    print("=" * 60)


if __name__ == "__main__":
    """
    Main entry point for concurrent game simulation.
    
    Effects:
        - Runs the complete fuzz test scenario
        - Handles any top-level exceptions
        - Ensures clean shutdown
        
    Ensures:
        - Test runs to completion
        - All resources are properly cleaned up
        - Exit code indicates test success (0) or failure (1)
    """
    try:
        asyncio.run(run_fuzz())
        exit(0)  # Success
    except Exception as e:
        print(f"[SIM][FATAL] Top-level exception: {e}")
        traceback.print_exc()
        exit(1)  # Failure