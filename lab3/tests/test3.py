import asyncio
import os
from src.board import Board, _Card
from src.board_ops import BoardOps
from src.card_states import CardState
from src.board_validator import BoardValidator


async def transformer(card):
    """
    Asynchronous transformer that changes each card value visibly,
    but keeps state and controller untouched.
    """
    await asyncio.sleep(0.01)
    return f"{card.value}_X"


async def test_map_preserves_state_and_controller():
    # --- Locate the board file ---
    here = os.path.dirname(__file__)
    board_path = os.path.join(here, "..", "boards", "ab.txt")
    board_path = os.path.abspath(board_path)

    # --- Parse board and prepare ---
    board = Board.parse_from_file(board_path)

    # Manually tweak one card to ensure state/controller preservation
    board._grid[0][0].state = CardState.UP
    board._grid[0][0].controller = "p1"
    board._grid[0][0].last_controller = "p1"

    # Snapshot the board state before map()
    before = [
        [(c.value, c.state, c.controller, c.last_controller) for c in row]
        for row in board._grid
    ]

    # --- Apply map() ---
    result = await BoardOps.map(board, transformer)
    print(result)
    BoardValidator.assert_invariants(board)

    # --- Verify that only values changed ---
    for r, row in enumerate(board._grid):
        for c, card in enumerate(row):
            old_value, old_state, old_controller, old_last = before[r][c]

            # Value must be transformed
            assert card.value == f"{old_value}_X", f"Value not transformed at ({r},{c})"

            # State and controllers must stay the same
            assert card.state == old_state, f"State changed at ({r},{c})"
            assert card.controller == old_controller, f"Controller changed at ({r},{c})"
            assert card.last_controller == old_last, f"Last controller changed at ({r},{c})"

    print("✅ test_map_preserves_state_and_controller passed!")


if __name__ == "__main__":
    asyncio.run(test_map_preserves_state_and_controller())
