import asyncio
from typing import Callable, Awaitable, Any
from src.board import Board
from src.board_ops import BoardOps


async def look(board: Board, player_id: str) -> str:
    """
    Return the visible board state for this player.
    """
    return await BoardOps.look(board, player_id)


async def flip(board: Board, player_id: str, row: int, col: int) -> str:
    """
    Perform flip operation using the game rules.
    """
    return await BoardOps.flip(board, player_id, row, col)


async def watch(board: Board, player_id: str) -> str:
    """
    Async long-poll watch.
    Browserul apelează continuu /watch.
    Serverul blochează până când BoardOps.notify_watchers() trezește acest player.
    """
    return await BoardOps.watch(board, player_id)


async def map(board: Board, old_value: str, new_value: str) -> str:
    """
    Replace all cards matching old_value with new_value.
    This is a simplified version that works with the /replace endpoint.
    """
    return await BoardOps.replace(board, old_value, new_value)


async def transform(board: Board, transformer: Callable[[Any], Awaitable[Any]]) -> str:
    """
    Apply a transformation function to all non-NONE cards on the board.
    The transformer should be an async function that takes a card and returns a new value.
    """
    return await BoardOps.map(board, transformer)