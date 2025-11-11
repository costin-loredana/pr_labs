import asyncio
from src.board import Board
from src.board_ops import BoardOps

async def test_watch_unblocks_on_flip():
    board = Board.parse_from_file("boards/ab.txt")

    async def wait_for_change():
        result = await BoardOps.watch(board, "p1")
        print("Watcher resumed:\n", result)
        return result

    watcher = asyncio.create_task(wait_for_change())

    # give watcher time to start waiting
    await asyncio.sleep(0.1)

    # trigger a change
    await BoardOps.flip(board, "p1", 0, 0)

    result = await asyncio.wait_for(watcher, timeout=1.0)
    assert "my" in result or "up" in result
    print(" test_watch_unblocks_on_flip passed!")

if __name__ == "__main__":
    asyncio.run(test_watch_unblocks_on_flip())
