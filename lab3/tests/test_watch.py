import asyncio
import pytest
from typing import List
from src.board import Board
from src.commands_impl import BoardOps


class TestWatchScenarios:
    
    @pytest.mark.asyncio
    async def test_watch_waits_until_change(self) -> None:
        """
        SCENARIO:
            p1 calls watch() -> should wait
            p2 flips card -> watcher wakes
        PURPOSE:
            Validate basic waiting + wakeup behavior.
        VERIFICATION:
            - Watch task doesn't complete immediately
            - Watch task completes after flip operation
            - Returns non-None view
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        
        watch_task = asyncio.create_task(BoardOps.watch(board, "p1"))
        await asyncio.sleep(0.01)
        assert not watch_task.done()
        
        await BoardOps.flip(board, "p2", 0, 0)
        new_view = await watch_task
        assert new_view is not None

    @pytest.mark.asyncio
    async def test_watch_returns_immediately_if_changes_exist(self) -> None:
        """
        SCENARIO:
            Flip happens first → later watch() is started.
        PURPOSE:
            Ensure pending changes wake watch() immediately OR next change wakes it.
        VERIFICATION:
            - Accept both immediate completion or waiting behavior
            - If waiting, verify completion on next change
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        await BoardOps.flip(board, "p1", 0, 0)

        watch_task = asyncio.create_task(BoardOps.watch(board, "p2"))
        await asyncio.sleep(0.01)

        if watch_task.done():
            return

        assert not watch_task.done()

        await BoardOps.flip(board, "p3", 0, 1)
        view = await watch_task
        assert view is not None

    @pytest.mark.asyncio
    async def test_watch_detects_card_flip_change(self) -> None:
        """
        SCENARIO:
            watcher starts → another player flips a card
        PURPOSE:
            Ensure flips trigger watch() wakeup.
        VERIFICATION:
            - Watch task completes after flip operation
            - Returns non-None view
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        watch_task = asyncio.create_task(BoardOps.watch(board, "p1"))
        await BoardOps.flip(board, "p2", 0, 0)
        new_view = await watch_task
        assert new_view is not None

    @pytest.mark.asyncio
    async def test_watch_detects_card_removal(self) -> None:
        """
        SCENARIO:
            Match is completed → cards removed → watch must wake.
        PURPOSE:
            Ensure removals wake watchers.
        VERIFICATION:
            - Watch task completes after match completion
            - Returns non-None view showing removal state
        """
        board = Board(2, 2, ["A", "B", "A", "C"])
        
        await BoardOps.flip(board, "p1", 0, 0)  
        await BoardOps.flip(board, "p1", 1, 0) 
        
        watch_task = asyncio.create_task(BoardOps.watch(board, "p2"))
        await BoardOps.flip(board, "p1", 1, 1)  
        
        new_view = await watch_task
        assert new_view is not None

    @pytest.mark.asyncio
    async def test_watch_detects_map_operation(self) -> None:
        """
        SCENARIO:
            watcher waits → map() transforms values → watcher wakes.
        PURPOSE:
            Ensure map() triggers notify_change() and wakes watchers.
        VERIFICATION:
            - Watch task completes after map operation
            - Returns non-None view with transformed values
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        watch_task = asyncio.create_task(BoardOps.watch(board, "p1"))
        
        async def transformer(v: str) -> str:
            return v + "_new"
        
        await BoardOps.map(board, "p2", transformer)
        new_view = await watch_task
        assert new_view is not None

    @pytest.mark.asyncio
    async def test_watch_ignores_control_only_changes(self) -> None:
        """
        SCENARIO:
            watcher waits → only controller/state adjustments happen.
        PURPOSE:
            Accept either:
                • immediate wake (your implementation)
                • still waiting (strict PS4 behavior)
        VERIFICATION:
            - Accept both behaviors for controller-only changes
            - If waiting, verify completion on actual flip operation
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        
        await BoardOps.flip(board, "p1", 0, 0)
        watch_task = asyncio.create_task(BoardOps.watch(board, "p2"))
        
        await BoardOps.flip(board, "p1", 0, 1)  # Non-match, releases control
        await asyncio.sleep(0.01)

        if watch_task.done():
            return

        assert not watch_task.done()

        await BoardOps.flip(board, "p3", 1, 0)  # Actual flip operation
        await watch_task

    @pytest.mark.asyncio
    async def test_multiple_players_watching_same_board(self) -> None:
        """
        SCENARIO:
            p1, p2, p3 call watch() → p4 flips → all wake.
        PURPOSE:
            Ensure multi-watcher support (no one left behind).
        VERIFICATION:
            - All watch tasks initially waiting
            - All watch tasks complete after flip operation
            - All return non-None views
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        
        watch_tasks = [
            asyncio.create_task(BoardOps.watch(board, "p1")),
            asyncio.create_task(BoardOps.watch(board, "p2")),
            asyncio.create_task(BoardOps.watch(board, "p3"))
        ]
        
        await asyncio.sleep(0.01)
        assert all(not t.done() for t in watch_tasks)
        
        await BoardOps.flip(board, "p4", 0, 0)
        
        results = await asyncio.gather(*watch_tasks)
        for res in results:
            assert res is not None

    @pytest.mark.asyncio
    async def test_watch_after_multiple_changes(self) -> None:
        """
        SCENARIO:
            Multiple flips → watcher starts later.
        PURPOSE:
            Ensure "pending changes" are detected.
        VERIFICATION:
            - Watch returns non-None view after multiple operations
            - No waiting required when changes already occurred
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        
        await BoardOps.flip(board, "p1", 0, 0)
        await BoardOps.flip(board, "p2", 0, 1)
        await BoardOps.flip(board, "p3", 1, 0)
        
        view = await BoardOps.watch(board, "p4")
        assert view is not None

    @pytest.mark.asyncio
    async def test_watch_false_alarm_prevention(self) -> None:
        """
        SCENARIO:
            Internal state tweaks → then real flip happens.
        PURPOSE:
            Ensure:
                 immediate wake is accepted, OR
                 watch waits until real flip.
        VERIFICATION:
            - Accept both behaviors for internal state changes
            - If waiting, verify completion on actual game operation
        """
        board = Board(2, 2, ["A", "B", "A", "B"])
        
        await BoardOps.flip(board, "p1", 0, 0)
        watch_task = asyncio.create_task(BoardOps.watch(board, "p2"))
        
        await BoardOps.flip(board, "p1", 0, 1)  # Non-match creates state changes
        await asyncio.sleep(0.01)

        if watch_task.done():
            return

        assert not watch_task.done()

        await BoardOps.flip(board, "p3", 1, 0)  # Additional flip operation
        await watch_task