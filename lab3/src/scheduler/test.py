import pytest
import asyncio
from src.scheduler.prioritizer import PriorityScheduler

@pytest.mark.asyncio
async def test_fifo_order():
    sched = PriorityScheduler(1, 1)
    order = []

    async def player(pid):
        await sched.wait_for_turn((0, 0), pid)
        order.append(pid)
        await sched.release_card((0, 0))

    await asyncio.gather(player("A"), player("B"), player("C"))
    assert order == ["A", "B", "C"]
