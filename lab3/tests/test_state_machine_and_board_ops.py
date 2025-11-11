import pytest
from lab3.src.game_states import CardStateMachine
from src.game_states import CardState, CardEvent
from src.board_ops import BoardOps
from src.board import Board, _Card


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def make_card(value="A", state=CardState.DOWN, controller=None):
    """Quick helper to make a single card."""
    return _Card(value=value, state=state, controller=controller)


def make_simple_board():
    """Make a simple 2×2 board for testing."""
    grid = [
        [_Card("A", CardState.DOWN), _Card("B", CardState.DOWN)],
        [_Card("A", CardState.DOWN), _Card("B", CardState.DOWN)],
    ]
    return Board(width=2, height=2, grid=grid, player={})


# ---------------------------------------------------------------------
# Problem 1 — CardStateMachine tests
# ---------------------------------------------------------------------

def test_flip_down_to_up_sets_controller_and_last_controller():
    c = make_card()
    CardStateMachine.transition(c, CardEvent.FLIP, "p1")
    assert c.state == CardState.UP
    assert c.controller == "p1"
    assert c.last_controller == "p1"


def test_flip_up_to_down_clears_controller_but_remembers_last():
    c = make_card(state=CardState.UP, controller="p1")
    c.last_controller = "p1"
    CardStateMachine.transition(c, CardEvent.FLIP, "p1")
    assert c.state == CardState.DOWN
    assert c.controller is None
    assert c.last_controller == "p1"


def test_remove_from_up_clears_controller_and_sets_none():
    c = make_card(state=CardState.UP, controller="p1")
    CardStateMachine.transition(c, CardEvent.REMOVE, "p1")
    assert c.state == CardState.NONE
    assert c.controller is None


def test_reset_from_up_turns_down():
    c = make_card(state=CardState.UP, controller="p1")
    CardStateMachine.transition(c, CardEvent.RESET, "p1")
    assert c.state == CardState.DOWN
    assert c.controller is None


def test_invalid_transition_raises():
    c = make_card(state=CardState.NONE)
    with pytest.raises(ValueError):
        CardStateMachine.transition(c, CardEvent.FLIP, "p1")


# ---------------------------------------------------------------------
# Problem 2 — BoardOps integration tests
# ---------------------------------------------------------------------

def test_first_card_flip_and_last_controller():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 0, 0)
    c = b.get_card(0, 0)
    assert c.state == CardState.UP
    assert c.controller == "p1"
    assert c.last_controller == "p1"


def test_second_card_match_removes_both_cards():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 0, 0)
    BoardOps.flip(b, "p1", 1, 0)  # same value A
    c1 = b.get_card(0, 0)
    c2 = b.get_card(1, 0)
    assert c1.state == CardState.NONE
    assert c2.state == CardState.NONE


def test_second_card_mismatch_keeps_them_up_then_resets_next_turn():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 0, 0)  # A
    BoardOps.flip(b, "p1", 0, 1)  # B mismatch
    c1 = b.get_card(0, 0)
    c2 = b.get_card(0, 1)
    assert c1.state == CardState.UP
    assert c2.state == CardState.UP
    # Next flip triggers reset
    BoardOps.flip(b, "p1", 1, 1)
    assert b.get_card(0, 0).state == CardState.DOWN
    assert b.get_card(0, 1).state == CardState.DOWN


def test_cleanup_previous_turn_removes_matched_pair():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 0, 0)
    BoardOps.flip(b, "p1", 1, 0)  # A-A match
    BoardOps.flip(b, "p1", 0, 1)  # triggers cleanup
    assert b.get_card(0, 0).state == CardState.NONE
    assert b.get_card(1, 0).state == CardState.NONE


def test_cleanup_previous_turn_resets_mismatched_pair():
    b = make_simple_board()
    BoardOps.flip(b, "p1", 0, 0)  # A
    BoardOps.flip(b, "p1", 0, 1)  # B mismatch
    BoardOps.flip(b, "p1", 1, 1)  # triggers cleanup
    assert b.get_card(0, 0).state == CardState.DOWN
    assert b.get_card(0, 1).state == CardState.DOWN
