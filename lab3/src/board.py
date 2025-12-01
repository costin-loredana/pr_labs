import asyncio
from typing import Dict, Tuple, Optional, List
from pathlib import Path

from src.card import Card, CardState
from src.player import PlayerState


def dbg_board(*msg):
    print("[DEBUG][BOARD]", *msg, flush=True)


class Board:
    """
    A Board represents the game state for a memory matching game.
    
    ABSTRACTION FUNCTION (AF):
        AF(self) = a game board with:
        - dimensions: rows × columns  
        - card matrix M where M[r][c] has value and visibility state
        - player registry mapping player_id → PlayerState
        - synchronization state for card access and change notifications
    
    REPRESENTATION INVARIANTS (RI):
        - _rows > 0 and _cols > 0
        - _grid is _rows × _cols matrix of Card objects
        - All Card objects have valid CardState values
        - If card.state == REMOVED, then card.controller == None
        - _change_count ≥ 0
        - _players keys are non-empty strings
    
    SAFETY FROM REP EXPOSURE:
        - No direct access to _grid, _players, or _waiters
        - All returned data is either immutable or fresh copies
        - Card objects are not exposed directly to clients
    """

    def __init__(self, rows: int, cols: int, values: List[str]):
        """
        Creates a new Board with specified dimensions and card values.
        
        Parameters:
            rows: number of rows (must be > 0)
            cols: number of columns (must be > 0) 
            values: card values in row-major order (length must equal rows*cols)
            
        Throws:
            ValueError: if rows ≤ 0 or cols ≤ 0 or length mismatch
        
        Requires:
            - rows > 0 and cols > 0
            - len(values) == rows * cols
            - All values are non-empty strings
            
        Effects:
            - Initializes _grid as rows×cols matrix of Cards with given values
            - All cards start in CardState.DOWN
            - _players = empty dictionary
            - _waiters = empty dictionary  
            - _change_count = 0
            - _change_waiters = empty list
            
        Ensures:
            - Representation invariants hold
            - Board is ready for game operations
        """
        if rows <= 0 or cols <= 0:
            raise ValueError("rows and cols must be positive")
        if rows * cols != len(values):
            raise ValueError("board size mismatch")

        self._rows = rows
        self._cols = cols

        # Build 2D grid of Cards
        self._grid: List[List[Card]] = []
        idx = 0
        for r in range(rows):
            row = []
            for c in range(cols):
                v = values[idx]
                card = Card(v)
                card.set_board_ref(self)   # link card -> board for change notifications
                row.append(card)
                idx += 1
            self._grid.append(row)

        # Per-player state
        self._players: Dict[str, PlayerState] = {}

        # FIFO async waiters per card position (for RULE 1-D contention)
        self._waiters: Dict[Tuple[int, int], List[asyncio.Future]] = {}

        self._change_count: int = 0
        self._change_waiters: List[asyncio.Future] = []
        
        self.checkRep()

    def checkRep(self):
        """
        Verifies all representation invariants hold.
        
        Requires: nothing
        Effects: none (except assertion failures)
        Ensures: all representation invariants are satisfied
        """
        # Basic dimensions
        assert self._rows > 0 and self._cols > 0
        
        # Grid structure
        assert len(self._grid) == self._rows
        for row in self._grid:
            assert len(row) == self._cols
        
        # Card states are valid
        for r in range(self._rows):
            for c in range(self._cols):
                card = self._grid[r][c]
                assert card.state in CardState
                if card.state == CardState.REMOVED:
                    assert card.controller is None

    def __str__(self):
        """
        Returns informal string representation for debugging.
        
        Returns: multi-line string showing board contents
        Effects: none (pure function)
        """
        rows = []
        for r in range(self._rows):
            row = " ".join(self._grid[r][c].value for c in range(self._cols))
            rows.append(row)
        return f"Board({self._rows}x{self._cols}):\n" + "\n".join(rows)

    def toString(self) -> str:
        """
        Returns board in MIT format for client communication.
        
        Returns: string in format:
            "RxC"
            "token1"
            "token2"
            ...
        where tokens are:
            - "down" for face-down cards
            - "none" for removed cards  
            - "controller value" for face-up cards (e.g., "player1 A")
            
        Requires: nothing
        Effects: none (pure function)
        Ensures: return format matches MIT Memory Scramble protocol
        """
        lines = [f"{self._rows}x{self._cols}"]
        for r in range(self._rows):
            for c in range(self._cols):
                card = self._grid[r][c]
                if card.state == CardState.REMOVED:
                    lines.append("none")
                elif card.state == CardState.DOWN:
                    lines.append("down") 
                else:  # UP
                    lines.append(f"{card.controller or 'none'} {card.value}")
        return "\n".join(lines)

    @staticmethod
    async def parseFromFile(filename: str) -> "Board":
        """
        Creates a Board by parsing a board configuration file.
        
        Parameters:
            filename: path to board configuration file
            
        Returns: new Board instance
        
        Throws:
            ValueError: if file format invalid or value count mismatch
            FileNotFoundError: if file doesn't exist
            IOError: if file cannot be read
        
        Requires:
            - filename refers to existing, readable file
            - File format:
                First line: "RxC" where R, C are positive integers
                Next R lines: C space-separated string values
            - Total values = R × C
            
        Effects:
            - Reads and parses the file
            - Returns new Board with dimensions and values from file
            
        Ensures:
            - All cards initialize to CardState.DOWN
            - Board representation invariants hold
        """
        path = Path(filename)
        if not path.exists():
            raise ValueError(f"File not found: {filename}")

        raw_lines = path.read_text(encoding="utf8").splitlines()
        lines = [ln.strip() for ln in raw_lines if ln.strip()]

        header = lines[0].lower().replace("x", " ")
        parts = header.split()
        if len(parts) != 2:
            raise ValueError("Invalid header format")

        rows, cols = map(int, parts)
        values: List[str] = []
        for line in lines[1:]:
            values.extend(line.split())

        if len(values) != rows * cols:
            raise ValueError("Board file values mismatch")

        return Board(rows, cols, values)

    def get_or_create_player(self, pid: str) -> PlayerState:
        """
        Retrieves existing PlayerState or creates new one for player ID.
        
        Parameters:
            pid: player identifier (non-empty string)
            
        Returns: PlayerState instance for the player
        
        Requires:
            - pid is non-empty string
            
        Effects:
            - If pid not in _players: creates new PlayerState and adds to _players
            
        Ensures:
            - Same pid always returns same PlayerState instance
            - _players[pid] exists after call
        """
        if pid not in self._players:
            self._players[pid] = PlayerState()
        return self._players[pid]

    def iter_positions(self):
        """
        Iterates over all board positions.
        
        Returns: generator yielding (r, c, Card) tuples
        
        Requires: nothing
        Effects: none (pure iteration)
        
        Rep Exposure: 
            - Yields internal Card objects (safe for internal use only)
            - Clients must not modify returned Cards
        """
        for r in range(self._rows):
            for c in range(self._cols):
                yield (r, c, self._grid[r][c])

    def _validate_position(self, r: int, c: int):
        """
        Validates that (r,c) is within board bounds.
        
        Parameters:
            r: row index
            c: column index
            
        Throws:
            ValueError: if position out of bounds
            
        Requires: nothing
        Effects: none (except exception)
        Ensures: if no exception, then 0 <= r < _rows and 0 <= c < _cols
        """
        if not (0 <= r < self._rows and 0 <= c < self._cols):
            raise ValueError(f"Position ({r},{c}) out of bounds for {self._rows}x{self._cols} board")

    async def wait_for_card(self, r: int, c: int):
        """
        Waits for a card to become available (FLIP Rule 1-D implementation).
        
        Parameters:
            r: row index
            c: column index  
            
        Returns: True when card becomes available
        
        Throws:
            ValueError: if position invalid
            
        Requires:
            - 0 <= r < _rows and 0 <= c < _cols
            
        Effects:
            - Adds caller to FIFO wait queue for position (r,c)
            - Suspends execution until card becomes available or is removed
            
        Ensures:
            - Returns only when card is DOWN or REMOVED (available for flipping)
            - Waiters are served in FIFO order
        """
        self.checkRep()
        self._validate_position(r, c)
        
        fut = asyncio.Future()
        self._waiters.setdefault((r, c), []).append(fut)
        dbg_board(f"[WAIT] Added waiter for card ({r},{c}). Total now: {len(self._waiters[(r,c)])}")
        
        result = await fut
        self.checkRep()
        return result

    def notify_card_available(self, r: int, c: int):
        """
        Notifies all waiters that a card has become available.
        
        Parameters:
            r: row index
            c: column index
            
        Throws:
            ValueError: if position invalid
            
        Requires:
            - 0 <= r < _rows and 0 <= c < _cols
            
        Effects:
            - Resolves all Futures in _waiters[(r,c)] with True
            - Clears the wait queue for (r,c)
            - Calls notify_change() (triggers visual update)
            
        Ensures:
            - All waiters for (r,c) are notified
            - Wait queue for (r,c) is empty after call
        """
        self.checkRep()
        self._validate_position(r, c)
        
        queue = self._waiters.get((r, c))
        if not queue:
            self.checkRep()
            return
        fut = queue.pop(0)
        dbg_board(f"[NOTIFY] Card ({r},{c}) available. Releasing 1 waiter (FIFO). Remaining={len(queue)}")
        #dbg_board(f"[NOTIFY] Card ({r},{c}) available. Releasing {len(queue)} waiter(s).")
        # Empty the queue
        if not fut.done():
            fut.set_result(True)

        self._waiters[(r, c)] = queue
        #for fut in queue:
            #if not fut.done():
             #   fut.set_result(True)

        # Visual change
        self.notify_change()
        self.checkRep()

    def notify_change(self):
        """
        Notifies all watchers of visual state changes.
        
        Requires: nothing
        
        Effects:
            - Increments _change_count by 1
            - Resolves all Futures in _change_waiters with new _change_count
            - Clears _change_waiters
            
        Ensures:
            - _change_count increases monotonically
            - All waiting watch() calls resume with updated count
        """
        self._change_count += 1
        dbg_board(f"[CHANGE] change_count -> {self._change_count}")

        # Wake all waiting watch calls
        if self._change_waiters:
            waiters = self._change_waiters.copy()
            self._change_waiters.clear()

            for fut in waiters:
                if not fut.done():
                    fut.set_result(self._change_count)

    async def wait_for_change(self) -> int:
        """
        Waits for the next visual change to the board.
        
        Returns: new _change_count after change occurs
        
        Throws:
            asyncio.CancelledError: if task is cancelled while waiting
            
        Requires: nothing
        
        Effects:
            - Adds Future to _change_waiters
            - Suspends execution until notify_change() is called
            
        Ensures:
            - Returns only after at least one visual change occurs
            - Return value > value at time of call
        """
        self.checkRep()

        fut = asyncio.Future()
        self._change_waiters.append(fut)
        dbg_board(f"[WATCH-WAIT] Added watch waiter. Total now: {len(self._change_waiters)}")

        try:
            await fut
            dbg_board(f"[WATCH-WAIT] Resumed watcher. change_count={self._change_count}")
            self.checkRep()
            return self._change_count
        except asyncio.CancelledError:
            if fut in self._change_waiters:
                self._change_waiters.remove(fut)
            self.checkRep()
            raise

    def set_card_state(self, r: int, c: int, state: CardState):
        """
        Sets the visibility state of a card.
        
        Parameters:
            r: row index
            c: column index
            state: new CardState value
            
        Throws:
            ValueError: if position invalid
            
        Requires:
            - 0 <= r < _rows and 0 <= c < _cols
            - state is valid CardState value
            
        Effects:
            - Updates card.state to new value
            - If state == REMOVED: calls notify_card_available(r, c)
            - Triggers visual change notification
            
        Ensures:
            - card.state == state after call
            - If state changed, visual observers are notified
        """
        self.checkRep()
        self._validate_position(r, c)
        
        card = self._grid[r][c]
        old_state = card.state

        if old_state != state:
            dbg_board(f"[STATE] ({r},{c}) {old_state} -> {state}")
            card.state = state  # Card itself will notify_change through _notify_board()

            # Wake the ones from a queue 
            if state == CardState.REMOVED:
                self.notify_card_available(r, c)
                
        self.checkRep()

    def set_card_controller(self, r: int, c: int, controller: Optional[str]):
        """
        Sets the controller of a card.
        
        Parameters:
            r: row index
            c: column index  
            controller: player ID or None to release control
            
        Throws:
            ValueError: if position invalid
            
        Requires:
            - 0 <= r < _rows and 0 <= c < _cols
            - controller is None or non-empty string
            
        Effects:
            - Updates card.controller
            - If controller changes from non-None to None: calls notify_card_available(r, c)
            - Triggers visual change notification
            
        Ensures:
            - card.controller == controller after call
            - If controller released, waiters are notified
        """
        self.checkRep()
        self._validate_position(r, c)
        
        card = self._grid[r][c]
        old_controller = card.controller

        if old_controller != controller:
            dbg_board(f"[CTRL] ({r},{c}) controller {old_controller} -> {controller}")
            card.controller = controller  # Visually notify

            if old_controller is not None and controller is None:
                self.notify_card_available(r, c)
                
        self.checkRep()

    def set_card_value(self, r: int, c: int, value: str):
        """
        Sets the value of a card.
        
        Parameters:
            r: row index
            c: column index
            value: new card value
            
        Throws:
            ValueError: if position invalid or value empty
            
        Requires:
            - 0 <= r < _rows and 0 <= c < _cols  
            - value is non-empty string
            
        Effects:
            - Updates card.value
            - Triggers visual change notification
            
        Ensures:
            - card.value == value after call
            - Visual observers are notified of change
        """
        self.checkRep()
        self._validate_position(r, c)
        
        card = self._grid[r][c]
        old_val = card.value
        if old_val != value:
            dbg_board(f"[VALUE] ({r},{c}) {old_val} -> {value}")
            card.value = value  # Card notifies the board
            
        self.checkRep()

    def format_for_player_view(self, player_id: str, view: List[List[str]]) -> str:
        """
        Formats a player's view into MIT protocol format.
        
        Parameters:
            player_id: player identifier (for potential per-player formatting)
            view: 2D list of visibility tokens from look() operation
            
        Returns: string in MIT board format
        
        Requires:
            - view is fresh 2D list with dimensions _rows × _cols
            - Each view[r][c] is valid token: "down", "none", or controller string
            
        Effects: none (pure function)
        
        Ensures:
            - Return format matches MIT protocol specification
            - Cards with tokens "down" or "none" output as-is
            - Cards with controller tokens output as "controller value"
        """
        self.checkRep()
        
        lines = [f"{self._rows}x{self._cols}"]
        for r in range(self._rows):
            for c in range(self._cols):
                token = view[r][c]
                card = self._grid[r][c]
                if token in ("down", "none"):
                    lines.append(token)
                else:
                    lines.append(f"{token} {card.value}")
                    
        self.checkRep()
        return "\n".join(lines)