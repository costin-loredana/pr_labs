import sys, os, asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.board import Board, _Card
from src.board_ops import BoardOps
from src.card_states import CardState


# ================================================================
# Helper: make a Board from raw values
# ================================================================
def make_board_from_values(rows_of_values):
    """
    rows_of_values: list[list[str]] with card labels.
    All cards start DOWN and uncontrolled.
    """
    height = len(rows_of_values)
    width = len(rows_of_values[0])
    grid = [
        [
            _Card(value=v, state=CardState.DOWN, controller=None, last_controller=None)
            for v in row
        ]
        for row in rows_of_values
    ]
    return Board(width=width, height=height, grid=grid, player={})


# ================================================================
# TEST 1: 3-A — matched pair is removed on next move
# ================================================================
@pytest.mark.asyncio
async def test_matched_pair_removed_on_next_move():
    # 2x2 board with a guaranteed pair at (0,0) and (0,1)
    # A A
    # B C
    board = make_board_from_values([
        ["A", "A"],
        ["B", "C"],
    ])

    # Flip a matching pair
    await BoardOps.flip(board, "p1", 0, 0)
    await BoardOps.flip(board, "p1", 0, 1)

    # At this point, by spec, both A's should be UP and under p1's control,
    # and cleanup is deferred until next move.

    # Trigger rule 3-A by making *another* move
    await BoardOps.flip(board, "p1", 1, 0)

    # Now the original matching pair must be REMOVED (state = NONE)
    assert board._grid[0][0].state == CardState.NONE
    assert board._grid[0][1].state == CardState.NONE
    # and control is gone
    assert board._grid[0][0].controller is None
    assert board._grid[0][1].controller is None


# ================================================================
# TEST 2: 3-B — mismatched cards flip back DOWN on next move
# ================================================================
@pytest.mark.asyncio
async def test_mismatched_pair_flipped_down_on_next_move():
    # 2x2 board with *no* pairs:
    # A B
    # C D
    board = make_board_from_values([
        ["A", "B"],
        ["C", "D"],
    ])

    # Flip a mismatching pair: (0,0) = A, (0,1) = B
    await BoardOps.flip(board, "p1", 0, 0)
    await BoardOps.flip(board, "p1", 0, 1)

    # After the second flip:
    # - both cards A and B should be UP
    # - 2-E says: mismatch, relinquish control immediately, leave face up
    c1 = board._grid[0][0]
    c2 = board._grid[0][1]
    assert c1.state == CardState.UP
    assert c2.state == CardState.UP

    # Now rule 3-B: on the *next* move by this player,
    # any previously unmatched cards that are still on the board,
    # still face up, and not controlled by another player,
    # must be turned face DOWN.
    await BoardOps.flip(board, "p1", 1, 0)  # arbitrary next move

    c1_after = board._grid[0][0]
    c2_after = board._grid[0][1]

    # They should now be DOWN (since they are still on the board,
    # were face up, and are not controlled by anybody else).
    if c1_after.state != CardState.NONE:
        assert c1_after.state == CardState.DOWN
        assert c1_after.controller is None

    if c2_after.state != CardState.NONE:
        assert c2_after.state == CardState.DOWN
        assert c2_after.controller is None


# ================================================================
# TEST 3: watch() unblocks when flip changes the board
# ================================================================
@pytest.mark.asyncio
async def test_watch_unblocks_on_flip():
    # tiny board is enough for watch()
    board = make_board_from_values([
        ["X", "Y"],
        ["Z", "W"],
    ])

    async def player_watch_then_flip():
        view_before = await BoardOps.look(board, "p1")

        # Start watching in the background
        task = asyncio.ensure_future(BoardOps.watch(board, "p1"))

        # Cause a visible change: flip a DOWN card to UP
        await BoardOps.flip(board, "p1", 0, 0)

        # The watch() should now wake up and return a new view
        view_after = await task
        return view_before, view_after

    before, after = await player_watch_then_flip()

    # before: all DOWN
    assert "down ?" in before

    # after: some card should be visible as "my ..." or "up ..."
    assert "my " in after or "up " in after
