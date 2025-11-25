from typing import List, Callable, Awaitable
from src.board import Board
from src.commands_impl import BoardOps


async def look(board: Board, player_id: str) -> List[List[str]]:
    return await BoardOps.look(board, player_id)


async def flip(board: Board, player_id: str, row: int, col: int) -> str:
    return await BoardOps.flip(board, player_id, row, col)


async def map(board: Board, player_id: str,
              f: Callable[[str], Awaitable[str]]) -> str:
    return await BoardOps.map(board, player_id, f)


async def watch(board: Board, player_id: str) -> List[List[str]]:

    return await BoardOps.watch(board, player_id)