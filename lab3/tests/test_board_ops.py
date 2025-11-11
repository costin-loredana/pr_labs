import pytest
from src.board_ops import BoardOps
from src.board import Board, _Card
from src.game_states import CardState, CardEvent
from lab3.src.game_states import CardStateMachine


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def make_simple_board():
    """
    Create a 2x2 board layout:
        A A
        B C
    Used across all tests.
    """
    grid = [
        [_Card("A", CardState.DOWN), _Card("A", CardState.DOWN)],
        [_Card("B", CardState.DOWN), _Card("C", CardState.DOWN)],
    ]
    b = Board(2, 2, grid, {})   # ✅ matches your __init__(width, height, grid, player)
    b._pending = {}
    return b



# ---------------------------------------------------------------------
# 1-A – No card in space
# ---------------------------------------------------------------------
def test_first_card_no_card_in_space():
    b = make_simple_board()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "p1")
    CardStateMachine.transition(c, CardEvent.REMOVE, "p1")
    out = BoardOps.flip(b, "p1", 0, 0)
    assert "No card" in out or "removed" in out


# ---------------------------------------------------------------------
# 1-C – First card already up but uncontrolled
# ---------------------------------------------------------------------
def test_first_card_flip_when_already_up_uncontrolled():
    b = make_simple_board()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "x")
    c.controller = None
    out = BoardOps.flip(b, "p1", 0, 0)
    assert "my A" in out or "my a" in out


# ---------------------------------------------------------------------
# 1-D – First card controlled by another player
# ---------------------------------------------------------------------
def test_first_card_flip_controlled_by_other_player():
    b = make_simple_board()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "p2")
    c.controller = "p2"
    out = BoardOps.flip(b, "p1", 0, 0)
    assert "controlled" in out.lower() or "p2" in out.lower()


# ---------------------------------------------------------------------
# 2-E + 3-B – Mismatch cards reset next turn
# ---------------------------------------------------------------------
def test_second_card_mismatch_then_reset_on_next_flip():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 1, 0)  # first B
    BoardOps.flip(b, "p1", 1, 1)  # second C (mismatch)
    # Both stay up temporarily
    assert b._grid[1][0].state == CardState.UP
    assert b._grid[1][1].state == CardState.UP
    # Next first-card flip resets them
    BoardOps.flip(b, "p1", 0, 0)
    assert b._grid[1][0].state == CardState.DOWN
    assert b._grid[1][1].state == CardState.DOWN


# ---------------------------------------------------------------------
# 2-D + 3-A – Matched pair remains up, removed on next turn
# ---------------------------------------------------------------------
def test_second_card_match_both_uncontrolled_then_removed():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 0, 0)  # first A
    BoardOps.flip(b, "p1", 0, 1)  # second A (match)

    c1 = b._grid[0][0]
    c2 = b._grid[0][1]
    # Should be face up but uncontrolled
    assert c1.state == CardState.UP and c2.state == CardState.UP
    assert c1.controller is None and c2.controller is None

    # Clicking one of them again does nothing
    before = (c1.state, c2.state)
    BoardOps.flip(b, "p1", 0, 0)
    after = (c1.state, c2.state)
    assert before == after

    # Next flip of a *different* card removes them
    BoardOps.flip(b, "p1", 1, 0)
    assert c1.state == CardState.NONE and c2.state == CardState.NONE


# ---------------------------------------------------------------------
# 2-B – Second card already controlled by another player
# ---------------------------------------------------------------------
def test_second_card_already_controlled_by_other_player():
    b = make_simple_board()
    # Player 2 controls a matched pair (A, A)
    BoardOps.flip(b, "p2", 0, 0)
    BoardOps.flip(b, "p2", 0, 1)
    # Now p1 tries to flip one of them
    out = BoardOps.flip(b, "p1", 0, 0)
    assert "controlled" in out.lower() or "p2" in out.lower()


# ---------------------------------------------------------------------
# LOOK – Proper formatting and ownership
# ---------------------------------------------------------------------
def test_look_formats_board_properly():
    b = make_simple_board()
    out = BoardOps.look(b, "p1")
    assert "2x2" in out
    assert "down ?" in out


def test_look_shows_controlled_cards_as_my():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 1, 0)
    out = BoardOps.look(b, "p1")
    assert "my B" in out or "my b" in out
