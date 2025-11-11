import asyncio
from collections import deque
from typing import Tuple, Dict, Deque


class PriorityScheduler:
    """
    Fair async scheduler for concurrent player access to board cards.
    Ensures strict FIFO order (first-come, first-served) when multiple
    players attempt to flip or control the same card concurrently.
    """

    def __init__(self, height: int, width: int):
        self._conditions: Dict[Tuple[int, int], asyncio.Condition] = {
            (r, c): asyncio.Condition() for r in range(height) for c in range(width)
        }
        self._queues: Dict[Tuple[int, int], Deque[str]] = {
            (r, c): deque() for r in range(height) for c in range(width)
        }

    # ----------------------------------------------------------
    # Main scheduler API
    # ----------------------------------------------------------

    async def wait_for_turn(self, pos: Tuple[int, int], player_id: str, timeout: float = 10.0):
        """
        Player waits until it reaches the front of the FIFO queue.
        Does NOT pop the queue here. That happens on release_card().
        FIXED: handle case where queue becomes empty -> avoid IndexError.
        """
        cond = self._conditions[pos]
        queue = self._queues[pos]

        async with cond:
            queue.append(player_id)
            try:
                while True:
                    # if queue is empty -> avoid queue[0] crash
                    if not queue:
                        return

                    # if this player is first -> allowed to continue
                    if queue[0] == player_id:
                        return

                    await asyncio.wait_for(cond.wait(), timeout)

            except asyncio.TimeoutError:
                # cleanup if player is still in queue
                if player_id in queue:
                    queue.remove(player_id)
                raise

    async def wait_for_release(self, pos: Tuple[int, int], timeout: float = 10.0):
        """
        Wait until controlling player releases the card.
        """
        cond = self._conditions[pos]
        async with cond:
            await asyncio.wait_for(cond.wait(), timeout)

    async def release_card(self, pos: Tuple[int, int]):
        """
        Pops the queue here, preserving FIFO order,
        then notifies all waiting players.
        """
        cond = self._conditions[pos]
        queue = self._queues[pos]

        async with cond:
            if queue:
                queue.popleft()
            cond.notify_all()

    def clear_card(self, pos: Tuple[int, int]):
        self._queues[pos].clear()

    def reset_all(self):
        for q in self._queues.values():
            q.clear()

    def get_waiting_list(self, pos: Tuple[int, int]):
        return list(self._queues[pos])

    def __repr__(self):
        return f"<PriorityScheduler cards={len(self._queues)}>"
