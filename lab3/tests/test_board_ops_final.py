import sys, os, pytest, asyncio
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.board_ops import BoardOps
from src.board import Board, _Card
from src.game_states import CardState, CardEvent, CardStateMachine
from src.scheduler.prioritizer import PriorityScheduler


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def make_board_5x5():
    grid = []
    values = [
        ["A", "A", "B", "B", "C"],
        ["C", "D", "D", "E", "E"],
        ["F", "F", "G", "G", "H"],
        ["H", "I", "I", "J", "J"],
        ["K", "K", "L", "L", "M"],
    ]
    for r in range(5):
        row = []
        for c in range(5):
            row.append(_Card(values[r][c], CardState.DOWN))
        grid.append(row)
    b = Board(5, 5, grid, {})
    b._pending = {}
    b._players = {}
    b._scheduler = PriorityScheduler(b.height, b.width)
    return b


# ---------------------------------------------------------------------
# Core tests (Rules 1–3)
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_no_card_in_space():
    b = make_board_5x5()
    c = b._grid[0][0]
    CardStateMachine.transition(c, CardEvent.FLIP, "p1")
    CardStateMachine.transition(c, CardEvent.REMOVE, "p1")
    out = await BoardOps.flip(b, "p1", 0, 0)
    assert "no card" in out.lower()


@pytest.mark.asyncio
async def test_first_flip_when_up_uncontrolled():
    b = make_board_5x5()
    c = b._grid[0][1]
    CardStateMachine.transition(c, CardEvent.FLIP, "x")
    c.controller = None
    out = await BoardOps.flip(b, "p1", 0, 1)
    assert "my" in out.lower() or "a" in out.lower()


@pytest.mark.asyncio
async def test_flip_controlled_by_other_player():
    b = make_board_5x5()
    c = b._grid[0][2]
    CardStateMachine.transition(c, CardEvent.FLIP, "p2")
    c.controller = "p2"

    task = asyncio.create_task(BoardOps.flip(b, "p1", 0, 2))
    await asyncio.sleep(0.01)
    assert not task.done()

    await BoardOps.flip(b, "p2", 0, 3)
    await BoardOps.flip(b, "p2", 1, 0)

    out = await asyncio.wait_for(task, timeout=0.5)
    assert isinstance(out, str)
    assert any(s in out.lower() for s in ["2x", "down", "up", "no card"])


@pytest.mark.asyncio
async def test_second_card_mismatch_then_reset_next_turn():
    b = make_board_5x5()
    await BoardOps.flip(b, "p1", 0, 2)
    await BoardOps.flip(b, "p1", 1, 3)
    await BoardOps.flip(b, "p1", 2, 0)
    c1, c2 = b._grid[0][2], b._grid[1][3]
    assert c1.state == CardState.DOWN
    assert c2.state == CardState.DOWN


@pytest.mark.asyncio
async def test_second_card_match_then_removed_on_next_flip():
    b = make_board_5x5()
    await BoardOps.flip(b, "p1", 0, 0)
    await BoardOps.flip(b, "p1", 0, 1)
    await BoardOps.flip(b, "p1", 1, 0)
    c1, c2 = b._grid[0][0], b._grid[0][1]
    assert c1.state == CardState.NONE
    assert c2.state == CardState.NONE


@pytest.mark.asyncio
async def test_second_card_already_controlled_by_other_player():
    b = make_board_5x5()
    await BoardOps.flip(b, "p2", 0, 0)
    await BoardOps.flip(b, "p2", 0, 1)

    task = asyncio.create_task(BoardOps.flip(b, "p1", 0, 0))
    await asyncio.sleep(0.01)
    assert not task.done()

    await BoardOps.flip(b, "p2", 1, 0)
    out = await asyncio.wait_for(task, timeout=0.5)
    assert isinstance(out, str)
    assert any(s in out.lower() for s in ["2x", "down", "up", "no card"])


# ---------------------------------------------------------------------
# Fair waiting queue (Rule 1-D)
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_waiting_queue_fifo_behavior():
    b = make_board_5x5()
    order = []

    async def player(pid):
        out = await BoardOps.flip(b, pid, 0, 0)
        order.append(pid)
        return out

    t1 = asyncio.create_task(player("p1"))
    await asyncio.sleep(0.01)
    t2 = asyncio.create_task(player("p2"))
    await asyncio.sleep(0.01)
    t3 = asyncio.create_task(player("p3"))

    await BoardOps.flip(b, "p1", 0, 1)
    await BoardOps.flip(b, "p1", 1, 0)

    await asyncio.gather(t1, t2, t3)
    assert order == ["p1", "p2", "p3"]


# ---------------------------------------------------------------------
# Look / Watch
# ---------------------------------------------------------------------
@pytest.mark.asyncio
async def test_look_format_and_controlled_cards():
    b = make_board_5x5()
    out = await BoardOps.look(b, "p1")
    assert "5x5" in out
    assert "down" in out
    await BoardOps.flip(b, "p1", 0, 0)
    out2 = await BoardOps.look(b, "p1")
    assert "my" in out2


@pytest.mark.asyncio
async def test_watch_notifies_after_change():
    b = make_board_5x5()
    task = asyncio.create_task(BoardOps.watch(b, "p1"))
    await asyncio.sleep(0.01)
    await BoardOps.flip(b, "p1", 0, 0)
    result = await asyncio.wait_for(task, timeout=0.5)
    assert "5x5" in result
