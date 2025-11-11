# ---------------------------------------------------------------------
# INTEGRATION TEST – Full multi-player concurrency scenario
# ---------------------------------------------------------------------
import pytest
import asyncio
from src.board_ops import BoardOps
from src.board import Board, _Card
from src.card_states import CardState

@pytest.mark.asyncio
async def test_full_multiplayer_rules_and_waiting_queue():
    """
    Complex scenario combining all rules 1-A through 3-B with 3 players.
    Board layout:
        A  A  B
        B  C  C
    Players: p1, p2, p3
    """

    grid = [
        [_Card("A", CardState.DOWN), _Card("A", CardState.DOWN), _Card("B", CardState.DOWN)],
        [_Card("B", CardState.DOWN), _Card("C", CardState.DOWN), _Card("C", CardState.DOWN)],
    ]
    b = Board(3, 2, grid, {})

    # --- Phase 1: P1 flips an A (C1)
    out1 = await BoardOps.flip(b, "p1", 0, 0)
    assert "my A" in out1

    # --- Phase 2: P2 tries to flip same card (must wait)
    t2 = asyncio.create_task(BoardOps.flip(b, "p2", 0, 0))
    await asyncio.sleep(0.01)
    assert not t2.done(), "p2 should be waiting for control of C1"

    # --- Phase 3: P1 flips second A (match)
    out2 = await BoardOps.flip(b, "p1", 0, 1)
    assert b._pending["p1"][2] is True, "matched pair should be recorded"

    # --- Phase 4: P1 flips next turn card -> matched pair removed (3-A)
    await BoardOps.flip(b, "p1", 1, 0)
    c1, c2 = b._grid[0][0], b._grid[0][1]
    assert c1.state == CardState.NONE and c2.state == CardState.NONE, "matched pair must be removed"

    # --- Phase 5: Now p2 finally gets control (waiting queue unblocked)
    res2 = await asyncio.wait_for(t2, timeout=0.1)
    assert "no card" in res2.lower() or "none" in res2.lower(), "p2 should find no card after removal"

    # --- Phase 6: P3 mismatches B and C (2-E, 3-B)
    await BoardOps.flip(b, "p3", 1, 0)  # B
    await BoardOps.flip(b, "p3", 1, 1)  # C mismatch
    assert b._grid[1][0].state == CardState.UP
    assert b._grid[1][1].state == CardState.UP

    # --- Phase 7: P3 flips again, should reset previous mismatched cards (3-B)
    await BoardOps.flip(b, "p3", 0, 2)
    assert b._grid[1][0].state == CardState.DOWN
    assert b._grid[1][1].state == CardState.DOWN

    # --- Phase 8: Final check – all cards consistent, no locked controllers
    for row in b._grid:
        for card in row:
            assert not (card.state != CardState.NONE and card.controller not in (None,)), \
                "no card should remain wrongly controlled"
