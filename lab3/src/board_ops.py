import asyncio
from typing import Tuple, List, Callable, Awaitable, Any
from src.board import Board, _Card
from src.game_states import CardState, CardEvent, CardStateMachine
from src.board_validator import BoardValidator
from src.scheduler.prioritizer import PriorityScheduler


DEBUG = True
def dbg(*args):
    if DEBUG:
        try: print("[DEBUG][BoardOps]", *args, flush=True)
        except: pass


class BoardOps:
    """
    Operations for managing concurrent card game board state.
    Provides thread-safe operations for multiple players to interact with the board.
    """

    @staticmethod
    def _ensure_scheduler(board: Board):
        if not hasattr(board, "_scheduler") or board._scheduler is None:
            board._scheduler = PriorityScheduler(board.height, board.width)
            dbg("init _scheduler")

    @staticmethod
    def _ensure_watchers(board: Board):
        if not hasattr(board, "_watchers") or board._watchers is None:
            board._watchers = []
            dbg("init _watchers")

    @staticmethod
    def _ensure_locks(board: Board):
        if not hasattr(board, "_locks") or board._locks is None:
            board._locks = {
                (r, c): asyncio.Lock()
                for r in range(board.height)
                for c in range(board.width)
            }
            dbg("init _locks")

    @staticmethod
    def _ensure_players(board: Board):
        if not hasattr(board, "_players") or board._players is None:
            board._players = {}
            dbg("init _players")

    @staticmethod
    def _ensure_pending(board: Board):
        if not hasattr(board, "_pending") or board._pending is None:
            board._pending = {}
            dbg("init _pending")

    @staticmethod
    def _notify_watchers(board: Board):
        BoardOps._ensure_watchers(board)

        if board._watchers:
            dbg("notify_watchers: waking", len(board._watchers), "watchers")

        for fut in board._watchers:
            if not fut.done():
                fut.set_result(True)

        board._watchers.clear()

    @staticmethod
    async def look(board: Board, player_id: str) -> str:
        """
        Get a textual representation of the board from a player's perspective.
        
        Requires:
          - board is a valid Board instance with proper invariants
          - player_id is a non-empty string identifying the player
        
        Effects:
          - Returns a string representation of the board showing:
            * Board dimensions as "heightxwidth"
            * "none" for removed cards
            * "down ?" for face-down cards  
            * "my value" for face-up cards controlled by this player
            * "up value" for face-up cards controlled by others or uncontrolled
          - Does not modify board state
          - Raises no exceptions (BoardValidator may raise on invariant violation)
        """
        BoardValidator.assert_invariants(board)
        lines = [f"{board.height}x{board.width}"]
        for r in range(board.height):
            for c in range(board.width):
                card = board._grid[r][c]

                if card.state == CardState.NONE:
                    lines.append("none")
                elif card.state == CardState.DOWN:
                    lines.append("down ?")
                elif card.state == CardState.UP:
                    if card.controller == player_id:
                        lines.append(f"my {card.value}")
                    else:
                        lines.append(f"up {card.value}")

        BoardValidator.assert_invariants(board)
        return "\n".join(lines)

    @staticmethod
    async def watch(board: Board, player_id: str) -> str:
        """
        Wait for board changes and return current state.
        
        Requires:
          - board is a valid Board instance with proper invariants
          - player_id is a non-empty string identifying the player
        
        Effects:
          - Blocks until board changes occur or timeout (0.5s) expires
          - Returns same format as look() after change detection
          - Registers player as a watcher; they will be notified on next state change
          - Does not modify card states or controllers
          - May raise asyncio.TimeoutError if no changes occur within timeout
        """
        BoardValidator.assert_invariants(board)
        BoardOps._ensure_watchers(board)

        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        board._watchers.append(fut)
        dbg("[WATCH] adding watcher for", player_id)

        try:
            await asyncio.wait_for(fut, timeout=0.5)
        except asyncio.TimeoutError:
            dbg("[WATCH] timeout for", player_id)
            return await BoardOps.look(board, player_id)

        return await BoardOps.look(board, player_id)

    @staticmethod
    async def map(board: Board, transformer: Callable[[_Card], Awaitable[Any]]) -> str:
        """
        Apply a transformation function to all cards on the board.
        
        Requires:
          - board is a valid Board instance with proper invariants
          - transformer is an async function that takes a _Card and returns any value
          - transformer should not modify card state or controller directly
        
        Effects:
          - Applies transformer to every non-removed card on the board
          - If transformer returns a _Card, replaces the original card
          - If transformer returns a string, updates the card's value
          - Notifies all watchers if any changes occurred
          - Returns "Map applied successfully"
          - Raises no exceptions (transformer exceptions propagate to caller)
        """
        BoardValidator.assert_invariants(board)
        BoardOps._ensure_locks(board)
        BoardOps._ensure_watchers(board)

        changed = False

        async def transform_cell(r, c, card):
            nonlocal changed
            async with board._locks[(r, c)]:
                res = await transformer(card)
                new_val = res.value if isinstance(res, _Card) else str(res)

                if new_val != card.value:
                    changed = True
                    board._grid[r][c] = _Card(
                        value=new_val,
                        state=card.state,
                        controller=card.controller,
                        last_controller=card.last_controller,
                    )

        await asyncio.gather(*[
            asyncio.create_task(transform_cell(r, c, card))
            for r, row in enumerate(board._grid)
            for c, card in enumerate(row)
            if card.state != CardState.NONE
        ])

        if changed:
            BoardOps._notify_watchers(board)

        BoardValidator.assert_invariants(board)
        return "Map applied successfully"

    @staticmethod
    async def replace(board: Board, old_value: str, new_value: str) -> str:
        """
        Replace all occurrences of a card value with a new value.
        
        Requires:
          - board is a valid Board instance with proper invariants
          - old_value and new_value are non-empty strings
        
        Effects:
          - Replaces all cards with value == old_value to have value == new_value
          - Preserves card state, controller, and other properties
          - Notifies all watchers if any changes occurred
          - Returns message indicating replacement count
          - Raises no exceptions
        """
        BoardValidator.assert_invariants(board)
        BoardOps._ensure_locks(board)
        BoardOps._ensure_watchers(board)

        changed = False

        async def replace_cell(r, c, card):
            nonlocal changed
            async with board._locks[(r, c)]:
                if card.value == old_value:
                    changed = True
                    board._grid[r][c] = _Card(
                        value=new_value,
                        state=card.state,
                        controller=card.controller,
                        last_controller=card.last_controller,
                    )

        await asyncio.gather(*[
            asyncio.create_task(replace_cell(r, c, card))
            for r, row in enumerate(board._grid)
            for c, card in enumerate(row)
            if card.state != CardState.NONE
        ])

        if changed:
            BoardOps._notify_watchers(board)

        BoardValidator.assert_invariants(board)
        return f"Replaced {old_value} with {new_value}"

    @staticmethod
    async def flip(board: Board, player_id: str, row: int, col: int) -> str:
        """
        Attempt to flip a card at the specified position.
        
        Requires:
          - board is a valid Board instance with proper invariants
          - player_id is a non-empty string identifying the player
          - 0 <= row < board.height and 0 <= col < board.width
        
        Effects:
          - Completes any pending previous turn for this player (Rule 3-A/B)
          - If player has no controlled cards, attempts to flip first card (Rule 1)
          - If player has one controlled card, attempts to flip second card (Rule 2)
          - May add player to wait queue if card is controlled by another (Rule 1-D)
          - Returns board state via look() or wait message
          - Notifies watchers on state changes
          - May raise ValueError for invalid coordinates
        """
        BoardValidator.assert_invariants(board)

        BoardOps._ensure_scheduler(board)
        BoardOps._ensure_watchers(board)
        BoardOps._ensure_players(board)
        BoardOps._ensure_pending(board)

        return await BoardOps._flip_locked(board, player_id, row, col)

    # -------------------- Internal: flip logic --------------------
    @staticmethod
    async def _flip_locked(board: Board, player_id: str, row: int, col: int) -> str:
        """
        Internal flip implementation with coordinate validation and queue checking.
        
        Requires:
          - board is properly initialized with scheduler, players, pending state
          - player_id is a non-empty string
          - 0 <= row < board.height and 0 <= col < board.width
          - Board invariants hold
        
        Effects:
          - Completes player's previous turn via _finish_previous_turn()
          - Validates coordinates and player queue status
          - Delegates to _handle_first_card() or _handle_second_card()
          - Returns board state or error message
          - Maintains board invariants
        """
        BoardValidator.assert_invariants(board)

        # Step 0: Finish previous turn (Rule 3-A / 3-B)
        await BoardOps._finish_previous_turn(board, player_id)

        # Step 1: Check if coordinates are valid
        if not (0 <= row < board.height and 0 <= col < board.width):
            return "Invalid coordinates."

        # FIXED: Clear any stale waiting status before checking
        waiting_pos = board._scheduler.waiting_on(player_id)
        if waiting_pos is not None:
            # If player was waiting but card no longer exists, clear the wait
            card_at_waiting = board._grid[waiting_pos[0]][waiting_pos[1]]
            if card_at_waiting.state == CardState.NONE:
                board._scheduler.remove_player(waiting_pos, player_id)
                waiting_pos = None

        # Check if player is waiting elsewhere 
        waiting_pos = board._scheduler.waiting_on(player_id)
        if waiting_pos is not None and waiting_pos != (row, col):
            return f"You are in a queue for {waiting_pos}. Wait until you get control."

        card = board._grid[row][col]

        # Step 2: Get currently controlled cards
        controlled = BoardOps._get_controlled_cards(board, player_id)

        # CASE 1: Player has no controlled cards (First Card)
        if len(controlled) == 0:
            return await BoardOps._handle_first_card(board, player_id, row, col)

        # CASE 2: Player has one controlled card (Second Card)
        elif len(controlled) == 1:
            return await BoardOps._handle_second_card(board, player_id, row, col, controlled[0])

        # Should not happen, but defensive coding
        else:
            board._players[player_id] = []
            return await BoardOps.look(board, player_id)


    @staticmethod
    async def _finish_previous_turn(board: Board, player_id: str):
        """
        Complete the player's previous turn according to Rules 3-A and 3-B.
        
        Requires:
          - board has proper _pending state structure
          - player_id is a non-empty string
        
        Effects:
          - If player had matched pair (Rule 3-A):
            * Removes both cards from board
            * Clears controllers and waiting queues for those cards
          - If player had mismatched cards (Rule 3-B):
            * Flips down any uncontrolled cards from previous turn
            * Clears controller references
          - Clears player's pending state and controlled cards
          - Notifies all watchers
          - Maintains board invariants
        """
        
        if player_id not in board._pending:
            return

        positions, matched = board._pending[player_id]

        if matched:
            # Rule 3-A: Matched pair - remove cards from board
            for (pr, pc) in positions:
                card = board._grid[pr][pc]
                if card.state != CardState.NONE:
                    CardStateMachine.transition(card, CardEvent.REMOVE, player_id)
                card.controller = None
                card.last_controller = None
                board._scheduler.clear_card((pr, pc))

        else:
            # Rule 3-B: Non-matching cards - turn face down if conditions met
            for (pr, pc) in positions:
                card = board._grid[pr][pc]
                if (card.state == CardState.UP and 
                    (card.controller is None or card.controller == player_id)):
                    CardStateMachine.transition(card, CardEvent.RESET, player_id)
                    card.controller = None
                card.last_controller = None

        # Clean up pending state
        del board._pending[player_id]
        board._players[player_id] = []
        BoardOps._notify_watchers(board)

    @staticmethod
    def _get_controlled_cards(board: Board, player_id: str) -> List[Tuple[int, int]]:
        """
        Get list of positions where player currently controls face-up cards.
        
        Requires:
          - board is a valid Board instance
          - player_id is a non-empty string
        
        Effects:
          - Returns list of (row, col) tuples for cards where:
            * card.state == CardState.UP
            * card.controller == player_id
          - Does not modify board state
          - Returns empty list if player controls no cards
        """
        return [
            (r, c)
            for r, row_cards in enumerate(board._grid)
            for c, card in enumerate(row_cards)
            if card.state == CardState.UP and card.controller == player_id
        ]

    @staticmethod
    async def _handle_first_card(board: Board, player_id: str, row: int, col: int) -> str:
        """
        Handle Rule 1: Player attempts to flip their first card.
        
        Requires:
          - player_id has no currently controlled cards
          - 0 <= row < board.height and 0 <= col < board.width
        
        Effects:
          - Rule 1-A: Returns "No card in that space." if card is removed
          - Rule 1-B: Flips face-down card up and takes control
          - Rule 1-C: Takes control of uncontrolled face-up card  
          - Rule 1-D: Adds to wait queue if card controlled by another player
          - Returns board state via look() or wait message
          - Notifies watchers on successful flip
        """
        card = board._grid[row][col]

        # Rule 1-A: No card in space
        if card.state == CardState.NONE:
            # Also remove player from any queue for this position
            board._scheduler.remove_player((row, col), player_id)
            return "No card in that space."

        # Rule 1-D: Card is face up and controlled by another player - WAIT
        if (card.state == CardState.UP and
                card.controller is not None and
                card.controller != player_id):

            got_access = await board._scheduler.wait_for_turn((row, col), player_id, board)
            if not got_access:
                dbg("first card WAIT for", player_id, "at", (row, col))
                return f"WAIT for card at ({row}, {col})"

        # Rule 1-B: Card is face down - flip it up and take control
        if card.state == CardState.DOWN:
            CardStateMachine.transition(card, CardEvent.FLIP, player_id)
            card.controller = player_id
            card.last_controller = player_id
            BoardOps._notify_watchers(board)

        # Rule 1-C: Card is face up but not controlled - take control
        elif card.state == CardState.UP and card.controller is None:
            card.controller = player_id
            card.last_controller = player_id

        board._players[player_id] = [(row, col)]
        return await BoardOps.look(board, player_id)

    @staticmethod
    async def _handle_second_card(
        board: Board,
        player_id: str,
        row: int,
        col: int,
        first_pos: Tuple[int, int],
    ) -> str:
        """
        Handle Rule 2: Player attempts to flip their second card.
        
        Requires:
          - player_id controls exactly one card at first_pos
          - 0 <= row < board.height and 0 <= col < board.width
        
        Effects:
          - Rule 2-A: Fails if no card, relinquishes first card control
          - Rule 2-B: Fails if card controlled by another, relinquishes first card
          - Rule 2-C: Flips face-down second card up
          - Rule 2-D: On match, keeps control of both cards
          - Rule 2-E: On mismatch, relinquishes control of both cards
          - Returns board state via look()
          - Notifies watchers
          - Uses locking to prevent race conditions
        """
        r1, c1 = first_pos
        first_card = board._grid[r1][c1]
        second_card = board._grid[row][col]

        async with board._locks[(row, col)]:
            # Rule 2-A: No card in space - operation FAILS, relinquish first card
            if second_card.state == CardState.NONE:
                first_card.controller = None
                # Store pending state for Rule 3-B (only the first card)
                board._pending[player_id] = ([(r1, c1)], False)
                board._players[player_id] = []
                BoardOps._notify_watchers(board)
                return "No card in that space."

            #  Rule 2-B: Card is face up and controlled by ANOTHER player - FAIL, no wait
            if (second_card.state == CardState.UP and
                    second_card.controller is not None and
                    second_card.controller != player_id):  
                first_card.controller = None
                # Store pending state for Rule 3-B (only the first card)
                board._pending[player_id] = ([(r1, c1)], False)
                board._players[player_id] = []
                BoardOps._notify_watchers(board)
                return f"Card is controlled by {second_card.controller}."

            # Card is either DOWN or UP but controlled by self or no one
            # Rule 2-C: If face down, turn it face up
            if second_card.state == CardState.DOWN:
                CardStateMachine.transition(second_card, CardEvent.FLIP, player_id)
                BoardOps._notify_watchers(board)

            # Rule 2-D vs 2-E: check match
            matched = (first_card.value == second_card.value)

            if matched:
                # Rule 2-D: Successful match - keep control of both cards
                second_card.controller = player_id
                second_card.last_controller = player_id
                board._players[player_id] = [(r1, c1), (row, col)]
                board._pending[player_id] = ([(r1, c1), (row, col)], True)
            else:
                # Rule 2-E: No match - relinquish control of both cards
                first_card.controller = None
                second_card.controller = None
                board._players[player_id] = []
                board._pending[player_id] = ([(r1, c1), (row, col)], False)

            BoardOps._notify_watchers(board)
            return await BoardOps.look(board, player_id)

    @staticmethod
    async def reset_board(board: Board) -> str:
        """
        Reset the entire board to initial state.
        
        Requires:
          - board is a valid Board instance
        
        Effects:
          - Resets all cards to face-down state with no controllers
          - Clears all player states and pending actions
          - Resets scheduler with empty queues
          - Notifies all watchers
          - Returns "Board reset successfully"
          - Maintains board invariants
        """
        BoardValidator.assert_invariants(board)

        BoardOps._ensure_locks(board)
        BoardOps._ensure_watchers(board)

        dbg("reset_board: full reset")

        board._scheduler = PriorityScheduler(board.height, board.width)

        for r in range(board.height):
            for c in range(board.width):
                card = board._grid[r][c]
                if card.state != CardState.NONE:
                    board._grid[r][c] = _Card(
                        value=card.value,
                        state=CardState.DOWN,
                        controller=None,
                        last_controller=None
                    )

        board._pending = {}
        board._players = {}

        BoardOps._notify_watchers(board)
        return "Board reset successfully"