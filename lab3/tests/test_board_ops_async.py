# tests/test_board_ops_async.py
import pytest
import asyncio
from src.board_ops import BoardOps
from src.board import Board, _Card
from src.game_states import CardState, CardEvent
from lab3.src.game_states import CardStateMachine


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def make_simple_board():
    """2x2 board layout: A A / B C"""
    grid = [
        [_Card("A", CardState.DOWN), _Card("A", CardState.DOWN)],
        [_Card("B", CardState.DOWN), _Card("C", CardState.DOWN)],
    ]
    b = Board(2, 2, grid, {})
    b._pending = {}
    b._players = {}
    return b


# ---------------------------------------------------------------------
# Basic rule tests (1-A → 3-B)
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_first_card_no_card_in_space():
    b = make_simple_board()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "p1")
    CardStateMachine.transition(c, CardEvent.REMOVE, "p1")
    out = await BoardOps.flip(b, "p1", 0, 0)
    assert "No card" in out or "removed" in out


@pytest.mark.asyncio
async def test_first_card_flip_when_already_up_uncontrolled():
    b = make_simple_board()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "x")
    c.controller = None
    out = await BoardOps.flip(b, "p1", 0, 0)
    assert "my A" in out or "my a" in out


@pytest.mark.asyncio
async def test_first_card_flip_controlled_by_other_player():
    b = make_simple_board()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "p2")
    c.controller = "p2"
    out = await BoardOps.flip(b, "p1", 0, 0)
    assert "controlled" in out.lower() or "p2" in out.lower()


@pytest.mark.asyncio
async def test_second_card_mismatch_then_reset_on_next_flip():
    b = make_simple_board()
    await BoardOps.flip(b, "p1", 1, 0)  # first B
    await BoardOps.flip(b, "p1", 1, 1)  # second C (mismatch)
    # Both stay up temporarily
    assert b._grid[1][0].state == CardState.UP
    assert b._grid[1][1].state == CardState.UP
    # Next first-card flip resets them
    await BoardOps.flip(b, "p1", 0, 0)
    assert b._grid[1][0].state == CardState.DOWN
    assert b._grid[1][1].state == CardState.DOWN


@pytest.mark.asyncio
async def test_second_card_match_then_removed_on_next_flip():
    b = make_simple_board()
    await BoardOps.flip(b, "p1", 0, 0)
    await BoardOps.flip(b, "p1", 0, 1)

    c1, c2 = b._grid[0][0], b._grid[0][1]
    assert c1.state == CardState.UP and c2.state == CardState.UP
    assert c1.controller is None and c2.controller is None

    # Next move removes them
    await BoardOps.flip(b, "p1", 1, 0)
    assert c1.state == CardState.NONE and c2.state == CardState.NONE


@pytest.mark.asyncio
async def test_second_card_already_controlled_by_other_player():
    b = make_simple_board()
    # Player 2 controls a matched pair (A, A)
    await BoardOps.flip(b, "p2", 0, 0)
    await BoardOps.flip(b, "p2", 0, 1)
    # Player 1 tries to flip one of them
    out = await BoardOps.flip(b, "p1", 0, 0)
    assert "controlled" in out.lower() or "p2" in out.lower()


# ---------------------------------------------------------------------
# Concurrency test: rule 1-D waiting
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_waiting_queue_resolves_in_fifo_order():
    b = make_simple_board()

    # Player 1 flips (0,0) → controls card
    t1 = asyncio.create_task(BoardOps.flip(b, "p1", 0, 0))
    await asyncio.sleep(0.01)  # allow control to acquire

    # Player 2 and Player 3 both try same card (should wait)
    t2 = asyncio.create_task(BoardOps.flip(b, "p2", 0, 0))
    t3 = asyncio.create_task(BoardOps.flip(b, "p3", 0, 0))

    # La început, amândoi ar trebui să fie în așteptare
    await asyncio.sleep(0.05)
    assert not t2.done() and not t3.done()

    # Player 1 eliberează cartea (flipă a doua carte + cleanup)
    await BoardOps.flip(b, "p1", 0, 1)
    await BoardOps.flip(b, "p1", 1, 0)  # triggers cleanup

    # Acum ambii așteptători ar trebui să se deblocheze într-un timp rezonabil
    await asyncio.wait_for(asyncio.gather(t2, t3), timeout=0.5)

    # Rezultatele ar trebui să fie niște răspunsuri text (nu blocaj)
    assert isinstance(t2.result(), str)
    assert isinstance(t3.result(), str)


# ---------------------------------------------------------------------
# LOOK tests
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_look_formats_board_properly():
    b = make_simple_board()
    out = BoardOps.look(b, "p1")
    assert "2x2" in out
    assert "down ?" in out


@pytest.mark.asyncio
async def test_look_shows_controlled_cards_as_my():
    b = make_simple_board()
    await BoardOps.flip(b, "p1", 1, 0)
    out = BoardOps.look(b, "p1")
    assert "my B" in out or "my b" in out
