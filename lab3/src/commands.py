# src/commands.py
from src.board import Board
from src.board_ops import BoardOps


async def look(board: Board, player_id: str) -> str:
    """
    Returnează vizualizarea completă a tablei pentru un anumit jucător.
    Este complet asincronă.
    """
    return await BoardOps.look(board, player_id)


async def flip(board: Board, player_id: str, row: int, col: int) -> str:
    """
    Întoarce cartea de pe poziția (row, col) pentru player_id,
    respectând regulile 1-A → 3-B (asincron).
    """
    return await BoardOps.flip(board, player_id, row, col)

async def map(board, old_value: str, new_value: str):
    """
    Apply transformer f(card) = new_value if card.value == old_value else card.value.
    """
    async def transformer(card):
        return new_value if card.value == old_value else card.value
    return await BoardOps.map(board, transformer)

async def watch(board, player_id):
    return await BoardOps.watch(board, player_id)