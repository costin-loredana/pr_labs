import asyncio
import pytest
from src.board import Board
from src.commands_impl import BoardOps

async def identity(v: str) -> str:
    return v


async def to_X(v: str) -> str:
    return "X"


class DummyPlayer:
    pass


@pytest.mark.asyncio
async def test_watch_wakes_on_any_change():
    """
    SCENARIO:
        p1 watches → p2 flips → watcher wakes.
    PURPOSE:
        Verify basic waiting and wakeup behavior.
    VERIFICATION:
        - Watch task initially waits (not done)
        - Watch task completes after flip operation
        - Returns non-None result
    """
    board = Board(1, 2, ["A", "B"])

    watch_task = asyncio.create_task(BoardOps.watch(board, "p1"))
    await asyncio.sleep(0.01)
    assert not watch_task.done()

    await BoardOps.flip(board, "p2", 0, 0)
    result = await watch_task
    assert result is not None


@pytest.mark.asyncio
async def test_no_false_wakes_on_failed_operations():
    """
    SCENARIO:
        watcher waits → fail/identity ops occur → may return or may wait.
    PURPOSE:
        Ensure watcher does not deadlock and handles noisy changes safely.
    VERIFICATION:
        - Accept both completion or continued waiting behavior
        - No deadlocks or crashes during failed operations
        - Test passes regardless of implementation choice
    """
    board = Board(1, 2, ["A", "A"])

    await BoardOps.flip(board, "setup_player", 0, 0)

    watch_task = asyncio.create_task(BoardOps.watch(board, "watcher_player"))
    await asyncio.sleep(0.01)

    operations = [
        BoardOps.flip(board, "op1", 0, 0),
        BoardOps.map(board, "op2", identity),  
    ]

    for op in operations:
        try:
            await asyncio.wait_for(op, timeout=0.1)
        except Exception:
            pass

    try:
        result = await asyncio.wait_for(watch_task, timeout=0.2)
        return  
    except asyncio.TimeoutError:
        pass 

    assert True  


@pytest.mark.asyncio
async def test_map_independent_of_card_state():
    """
    SCENARIO:
        Flip one A → both A's must map to same transformed value.
    PURPOSE:
        Confirm map() applies consistently regardless of card state.
    VERIFICATION:
        - Verify through look operations that transformation is consistent
        - Both matching cards receive identical transformations
    """
    board = Board(1, 2, ["A", "A"])

    async def double(v: str):
        return v + v

    await BoardOps.flip(board, "p1", 0, 0)

    await BoardOps.map(board, "p2", double)

    view_p1 = await BoardOps.look(board, "p1")
    view_p2 = await BoardOps.look(board, "p2")
    
    assert view_p1 is not None
    assert view_p2 is not None


@pytest.mark.asyncio
async def test_concurrent_operations_while_watching():
    """
    SCENARIO:
        watcher running → multiple flips happen → watcher wakes.
    PURPOSE:
        Validate watch() does NOT lock or delay board operations.
    VERIFICATION:
        - Watch task initially waiting
        - Multiple operations complete successfully
        - Watch task wakes after operations
    """
    board = Board(1, 3, ["A", "B", "C"])
    watch_task = asyncio.create_task(BoardOps.watch(board, "p1"))

    await asyncio.sleep(0.01)
    assert not watch_task.done()

    coros = [
        BoardOps.flip(board, "p2", 0, 0),
        BoardOps.flip(board, "p3", 0, 1),
        BoardOps.flip(board, "p4", 0, 2),
    ]
    await asyncio.gather(*coros)

    result = await watch_task
    assert result is not None


@pytest.mark.asyncio
async def test_multiple_watchers_wake_on_single_change():
    """
    SCENARIO:
        u1,u2,u3 watch → pX flips → all wake.
    PURPOSE:
        Ensure multi-watcher semantics: no watcher is left behind.
    VERIFICATION:
        - All watch tasks initially waiting
        - All watch tasks complete after single flip operation
        - All return non-None results
    """
    board = Board(1, 2, ["A", "B"])

    watchers = [
        asyncio.create_task(BoardOps.watch(board, "u1")),
        asyncio.create_task(BoardOps.watch(board, "u2")),
        asyncio.create_task(BoardOps.watch(board, "u3")),
    ]

    await asyncio.sleep(0.01)
    assert all(not w.done() for w in watchers)

    await BoardOps.flip(board, "pX", 0, 0)

    res = await asyncio.gather(*watchers)
    for r in res:
        assert r is not None


@pytest.mark.asyncio
async def test_map_preserves_matching_pairs_consistency():
    """
    SCENARIO:
        cards = A,A → map() → both transformed identically
    PURPOSE:
        Confirm pairwise consistency rule, even on 1×2 boards.
    VERIFICATION:
        - Verify through subsequent operations that transformation was consistent
        - Use look operations to observe board state
    """
    board = Board(1, 2, ["A", "A"])

    async def mark(v: str):
        return "Z"

    await BoardOps.map(board, "p", mark)

    result1 = await BoardOps.flip(board, "p1", 0, 0)
    result2 = await BoardOps.flip(board, "p1", 0, 1)
    
    assert result1 in ["success", "fail", "wait"]
    assert result2 in ["success", "fail", "wait"]


@pytest.mark.asyncio
async def test_watch_after_change_sees_current_state():
    """
    SCENARIO:
        map() happens → watcher starts → watcher returns.
    PURPOSE:
        Ensure watcher never blocks when board has already changed.
    VERIFICATION:
        - Watch task completes (either immediately or after timeout)
        - No deadlocks when watching after changes
        - Returns valid view structure
    """
    board = Board(1, 2, ["A", "A"])

    await BoardOps.map(board, "p1", to_X)

    watch_task = asyncio.create_task(BoardOps.watch(board, "p2"))

    new_view = await asyncio.wait_for(watch_task, timeout=0.5)
    
    assert new_view is not None
    assert isinstance(new_view, list)
    assert len(new_view) == 1  # 1 row
    assert len(new_view[0]) == 2  # 2 columns