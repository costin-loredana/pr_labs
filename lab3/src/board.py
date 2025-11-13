from __future__ import annotations
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from src.game_states import CardState



@dataclass
class _Card:
    """
    Internal representation of a single card in the memory game.
    
    Representation Invariant:
      - value is non-empty string
      - state is a valid CardState enum value
      - If state == CardState.NONE then controller == None
      - If matched == True, typically indicates card was part of a successful pair
    
    Note: This is an internal data class not intended for direct external use.
    Clients should interact with cards through Board and BoardOps interfaces.
    """
    value: str
    state: CardState
    controller: Optional[str] = None
    last_controller: Optional[str] = None
    matched: bool = False  



class Board:
    """
    Abstraction function:
        Represents a 2D grid of cards where each cell has a visible state and controller.

    Representation invariant:
        - width, height > 0
        - each row has exactly `width` cards
        - if state == "none" then controller == None
        - _grid, _players are private
    """

    def __init__(self, width: int, height: int, grid: List[List[_Card]], players: Dict[str, List[Tuple[int, int]]]):
        """
        Initialize a new game board with specified dimensions and cards.
        Requires:
          - width > 0 and height > 0
          - grid is a height × width matrix of _Card objects
          - players is a dictionary mapping player IDs to their controlled positions
          - All cards in grid have valid states and values
        Effects:
          - Creates a new board with the specified cards and player states
          - Initializes per-position locks for concurrent access
          - Initializes empty watchers list and pending actions dictionary
          - Sets scheduler to None (to be initialized by BoardOps)
          - Verifies representation invariant via check_rep()
        """
        self.width = width
        self.height = height
        self._grid = grid                        # 2D list of Card objects
        self._players = players                  
        self._pending: Dict[str, Tuple[List[Tuple[int, int]], bool]] = {}  
        self._scheduler = None
        self._locks: Dict[Tuple[int, int], asyncio.Lock] = {
            (r, c): asyncio.Lock()
            for r in range(height)
            for c in range(width)
        }
        self._watchers: List[asyncio.Future] = []
        self.check_rep()

    def check_rep(self):
        """
        Verify that the representation invariant holds.
        Effects:
          - Asserts that board dimensions are positive
          - Asserts that _grid has correct height and each row has correct width
          - Raises AssertionError if any invariant is violated
        """
        assert self.width > 0 and self.height > 0, "Board must have positive dimensions"
        assert len(self._grid) == self.height, f"expected {self.height} rows, got {len(self._grid)}"
        for i, row in enumerate(self._grid):
            assert len(row) == self.width, f"expected {self.width} columns in row {i}, got {len(row)}"


    @staticmethod
    def parse_from_file(filename: str) -> Board:
        """
        Create a Board instance by parsing a board definition file.
        Requires:
          - filename is a valid path to an existing file
          - File contains board data in one of supported formats:
            * Matrix format: header "HxW" followed by H lines of W space-separated tokens
            * Flat list format: header "HxW" followed by H*W tokens across any lines
            * Compact format: header "HxW" followed by H*W concatenated characters
        Effects:
          - Returns a new Board with all cards face-down and no controllers
          - All cards have values parsed from the file
          - Players dictionary is initialized empty
          - Raises FileNotFoundError if file doesn't exist
          - Raises ValueError for malformed file content or dimensions
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
            [_Card(value=v, state=CardState.DOWN, controller=None, last_controller=None) for v in row]
            for row in labels
        ]
        return Board(width=width, height=height, grid=grid, players={})


    def __str__(self) -> str:
        """
        Get human-readable string representation of board values.
        
        Effects:
          - Returns string with format:
            "heightxwidth"
            "value1 value2 ..."
            "value3 value4 ..."
            ...
          - Only shows card values, not states or controllers
          - Does not modify board state
        """
        rows = [" ".join(card.value for card in row) for row in self._grid]
        return f"{self.height}x{self.width}\n" + "\n".join(rows)

    def get_card(self, row: int, col: int) -> _Card:
        """Return reference to the card at (row, col)."""
        if 0 <= row < self.height and 0 <= col < self.width:
            return self._grid[row][col]
        raise IndexError(f"Position ({row}, {col}) out of bounds")

    def set_card(self, row: int, col: int, card: _Card) -> None:
        """Replace the card at (row, col)."""
        if 0 <= row < self.height and 0 <= col < self.width:
            self._grid[row][col] = card
        else:
            raise IndexError(f"Position ({row}, {col}) out of bounds")

    def dump(self) -> str:
        """Return text view of values, states, and controllers."""
        lines = []
        for row in self._grid:
            line = [f"{c.value}({c.state.name},{c.controller or '-'})" for c in row]
            lines.append(" ".join(line))
        return "\n".join(lines)

    def get_grid_copy(self) -> List[List[_Card]]:
        """Return a deep copy of the grid for inspection."""
        return [
            [
                _Card(
                    value=card.value,
                    state=card.state,
                    controller=card.controller,
                    last_controller=card.last_controller
                )
                for card in row
            ]
            for row in self._grid
        ]

    def get_players_copy(self) -> Dict[str, List[Tuple[int, int]]]:
        """Return a copy of the players dictionary."""
        return {pid: positions[:] for pid, positions in self._players.items()}

    def get_pending_copy(self) -> Dict[str, Tuple[List[Tuple[int, int]], bool]]:
        """Return a copy of the pending dictionary."""
        return {pid: (positions[:], matched) for pid, (positions, matched) in self._pending.items()}