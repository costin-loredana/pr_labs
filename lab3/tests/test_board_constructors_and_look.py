import asyncio
import pytest
from src.board import Board
from src.board_ops import BoardOps
from src.card_states import CardState
from src.board_validator import BoardValidator

# --------------------------------------------------------------------
# 🧩 Problem 0 – Constructors and look()
# --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_from_file_creates_valid_board(tmp_path):
    """Verify parse_from_file builds a structurally correct board."""
    board_file = tmp_path / "tiny.txt"
    board_file.write_text("2x2\nA\nA\nB\nB\n")

    board = Board.parse_from_file(str(board_file))

    # Validate structure
    assert isinstance(board, Board)
    assert board.height == 2
    assert board.width == 2

    # Every cell should be a _Card with valid state/value
    for r in range(board.height):
        for c in range(board.width):
            card = board._grid[r][c]
            assert card.state in (CardState.DOWN, CardState.UP, CardState.NONE)
            assert card.value is not None

    # No invariant violation
    assert BoardValidator.assert_invariants(board)


@pytest.mark.asyncio
async def test_parse_from_file_invalid_board(tmp_path):
    """Invalid file must raise an exception."""
    bad = tmp_path / "bad.txt"
    bad.write_text("2x2\nA\nA\nB\n")  # only 3 cards
    with pytest.raises(Exception):
        Board.parse_from_file(str(bad))


@pytest.mark.asyncio
async def test_look_shows_board_state(tmp_path):
    """look() should reflect all card states properly."""
    board_file = tmp_path / "simple.txt"
    board_file.write_text("2x2\nA\nA\nB\nB\n")
    board = Board.parse_from_file(str(board_file))

    # Initially everything DOWN
    output = await BoardOps.look(board, "p1")
    lines = output.splitlines()
    assert lines[0] == "2x2"
    assert all("down" in line or "?" in line for line in lines[1:])

    # Flip one card manually
    card = board._grid[0][0]
    card.state = CardState.UP
    card.controller = "p1"
    card.last_controller = "p1"

    updated = await BoardOps.look(board, "p1")
    assert "my" in updated

    # Another player should see same card as "up"
    other_view = await BoardOps.look(board, "p2")
    assert "up" in other_view and "my" not in other_view


@pytest.mark.asyncio
async def test_look_async_consistency(tmp_path):
    """Simulate concurrent look() calls from multiple players."""
    board_file = tmp_path / "async.txt"
    board_file.write_text("2x2\nA\nA\nB\nB\n")
    board = Board.parse_from_file(str(board_file))

    async def player_look(pid):
        return await BoardOps.look(board, pid)

    views = await asyncio.gather(
        player_look("alice"), player_look("bob"), player_look("carol")
    )
    assert all(view.startswith("2x2") for view in views)
