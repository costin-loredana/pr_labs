from __future__ import annotations
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from src.game_states import CardState


# ===============================================================
# 🃏 Internal Card representation
# ===============================================================
@dataclass
class _Card:
    """
    One cell of the board.
    States: face-up, face-down, or none (removed).
    """
    value: str
    state: CardState
    controller: Optional[str] = None      # player ID who controls the card
    last_controller: Optional[str] = None # last player who flipped the card


# ===============================================================
# 🎯 Board representation
# ===============================================================
class Board:
    """
    Mutable and concurrency-safe representation of the Memory Scramble board.

    Abstraction function:
        Represents a 2D grid of cards where each cell has a visible state and controller.

    Representation invariant:
        - width, height > 0
        - each row has exactly `width` cards
        - if state == "none" then controller == None
        - _grid, _players are private
    """

    def __init__(self, width: int, height: int, grid: List[List[_Card]], player: Dict[str, List[Tuple[int, int]]]):
        self.width = width
        self.height = height
        self._grid = grid                        # 2D list of Card objects
        self._players = player                   # mapping: player_id -> list of (r,c)
        self._pending: Dict[str, Tuple[Tuple[int, int], Tuple[int, int], bool]] = {}

        # Fairness scheduler (attached dynamically by BoardOps)
        self._scheduler = None

        # Locks per card for concurrent access
        self._locks: Dict[Tuple[int, int], asyncio.Lock] = {
            (r, c): asyncio.Lock()
            for r in range(height)
            for c in range(width)
        }

        # Watchers for /watch endpoint
        self._watchers: List[asyncio.Future] = []

        self.check_rep()

    # ------------------------------------------------------------
    # Representation check
    # ------------------------------------------------------------
    def check_rep(self):
        assert self.width > 0 and self.height > 0, "Board must have positive dimensions"
        assert len(self._grid) == self.height, f"expected {self.height} rows"
        for row in self._grid:
            assert len(row) == self.width, f"expected {self.width} columns per row"

    # ------------------------------------------------------------
    # Board parser
    # ------------------------------------------------------------
    @staticmethod
    def parse_from_file(filename: str) -> Board:
        """
        Accepts formats:
          1) Matrix with spaces: next H lines each have W tokens
          2) Flat list: following lines contain H*W tokens
          3) Compact chars: concatenated characters count equals H*W
        """
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Board file not found: {filename}")

        raw = path.read_text(encoding="utf-8").strip().splitlines()
        if not raw:
            raise ValueError("Empty board file")

        header = raw[0].strip().lower()
        if "x" not in header:
            raise ValueError(f"Invalid dimension line {raw[0]}")
        h_str, w_str = header.split("x", 1)
        try:
            height, width = int(h_str), int(w_str)
        except Exception:
            raise ValueError(f"Invalid dimensions: {raw[0]}")

        body = [ln.strip() for ln in raw[1:] if ln.strip()]

        # Strategy A: rows with space-separated tokens
        if len(body) == height:
            rows = [ln.split() for ln in body]
            if all(len(r) == width for r in rows):
                labels = rows
            else:
                labels = None
        else:
            labels = None

        # Strategy B: flat list of tokens
        if labels is None:
            tokens: List[str] = []
            for ln in body:
                parts = ln.split()
                tokens.extend(parts if parts else [])
            if len(tokens) == width * height:
                labels = [tokens[i * width:(i + 1) * width] for i in range(height)]

        # Strategy C: compact chars (no spaces)
        if labels is None:
            compact = "".join(body)
            if len(compact) == width * height:
                tokens = list(compact)
                labels = [tokens[i * width:(i + 1) * width] for i in range(height)]

        if labels is None:
            sample = body[0] if body else "<no body>"
            raise ValueError(
                "Board file format not recognized. Need either:\n"
                f" - {height} lines each with {width} space-separated tokens, or\n"
                f" - A flat list of {height*width} tokens, or\n"
                f" - {height*width} total characters.\n"
                f"First body line was: {sample}"
            )

        grid: List[List[_Card]] = [
            [_Card(value=v, state=CardState.DOWN, controller=None) for v in row]
            for row in labels
        ]
        return Board(width=width, height=height, grid=grid, player={})

    # ------------------------------------------------------------
    # Debugging helpers
    # ------------------------------------------------------------
    def __str__(self) -> str:
        """Human-readable board view."""
        rows = [" ".join(card.value for card in row) for row in self._grid]
        return f"{self.height}x{self.width}\n" + "\n".join(rows)

    def get_card(self, row: int, col: int) -> _Card:
        """Return reference to the card at (row, col)."""
        return self._grid[row][col]

    def set_card(self, row: int, col: int, card: _Card) -> None:
        """Replace the card at (row, col)."""
        self._grid[row][col] = card

    def dump(self) -> str:
        """Return text view of values, states, and controllers."""
        lines = []
        for row in self._grid:
            line = [f"{c.value}({c.state.name},{c.controller or '-'})" for c in row]
            lines.append(" ".join(line))
        return "\n".join(lines)
