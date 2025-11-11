# ---------------------------------------------------------------------
# SCENARIO TEST – Cleanup after mismatches with multiple players
# ---------------------------------------------------------------------
import pytest
from src.board_ops import BoardOps
from src.board import Board, _Card
from src.card_states import CardState

@pytest.mark.asyncio
async def test_cleanup_rule_after_multiplayer_mismatch():
    """
    Scenario:
        P1 flips C1
        P1 flips C2 (mismatch)
        P2 flips C1 and controls it
        P2 flips C3 (mismatch)
        P1 flips C4 -> cleanup occurs (3-B)
    Expectation:
        C1 and C2 are turned face down.
    """
    # Construct a 2x3 board for clarity:
    #  A  B  C
    #  D  E  F
    grid = [
        [_Card("A", CardState.DOWN), _Card("B", CardState.DOWN), _Card("C", CardState.DOWN)],
        [_Card("D", CardState.DOWN), _Card("E", CardState.DOWN), _Card("F", CardState.DOWN)],
    ]
    b = Board(3, 2, grid, {})

    # Step 1-2: P1 flips C1 and C2 (mismatch)
    await BoardOps.flip(b, "p1", 0, 0)  # C1 = A
    await BoardOps.flip(b, "p1", 0, 1)  # C2 = B (mismatch)
    assert b._grid[0][0].state == CardState.UP
    assert b._grid[0][1].state == CardState.UP

    # Step 3-4: P2 flips C1 (takes control), then C3 (mismatch)
    await BoardOps.flip(b, "p2", 0, 0)  # now controlled by p2
    await BoardOps.flip(b, "p2", 0, 2)  # mismatch
    assert b._grid[0][0].state == CardState.UP
    assert b._grid[0][2].state == CardState.UP

    # Step 5: P1 flips new card C4 (should trigger cleanup)
    await BoardOps.flip(b, "p1", 1, 0)

    # ✅ Expect C1 and C2 reset to DOWN
    assert b._grid[0][0].state == CardState.DOWN
    assert b._grid[0][1].state == CardState.DOWN
