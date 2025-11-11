import asyncio
from typing import Tuple, List, Optional
from src.board import Board, _Card
from src.game_states import CardState, CardEvent
from src.game_states import CardStateMachine
from src.board_validator import BoardValidator
from src.scheduler.prioritizer import PriorityScheduler


class BoardOps:
    """
    Asynchronous operations for the Memory Scramble board.
    Integrates a fair FIFO scheduler for concurrent access (rule 1-D).
    """

    # ----------------------------------------------------------
    # Utility
    # ----------------------------------------------------------
    @staticmethod
    def _ensure_scheduler(board: Board):
        if not hasattr(board, "_scheduler") or board._scheduler is None:
            board._scheduler = PriorityScheduler(board.height, board.width)

    @staticmethod
    def _ensure_watchers(board: Board):
        if not hasattr(board, "_watchers") or board._watchers is None:
            board._watchers = []

    @staticmethod
    def _ensure_locks(board: Board):
        if not hasattr(board, "_locks") or board._locks is None:
            board._locks = {
                (r, c): asyncio.Lock()
                for r in range(board.height)
                for c in range(board.width)
            }

    @staticmethod
    def _ensure_players(board: Board):
        if not hasattr(board, "_players") or board._players is None:
            board._players = {}

    @staticmethod
    def _ensure_pending(board: Board):
        if not hasattr(board, "_pending") or board._pending is None:
            board._pending = {}

    @staticmethod
    def _notify_watchers(board: Board):
        BoardOps._ensure_watchers(board)
        for fut in board._watchers:
            if not fut.done():
                fut.set_result(True)
        board._watchers.clear()

    # ----------------------------------------------------------
    # Look
    # ----------------------------------------------------------
    @staticmethod
    async def look(board: Board, player_id: str) -> str:
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

    # ----------------------------------------------------------
    # Watch
    # ----------------------------------------------------------
    @staticmethod
    async def watch(board: Board, player_id: str) -> str:
        BoardValidator.assert_invariants(board)
        BoardOps._ensure_watchers(board)
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        board._watchers.append(fut)
        try:
            await asyncio.wait_for(fut, timeout=0.5)
        except asyncio.TimeoutError:
            return await BoardOps.look(board, player_id)
        return await BoardOps.look(board, player_id)

    # ----------------------------------------------------------
    # Map / Transform
    # ----------------------------------------------------------
    @staticmethod
    async def map(board: Board, transformer):
        BoardValidator.assert_invariants(board)
        BoardOps._ensure_scheduler(board)
        BoardOps._ensure_watchers(board)
        BoardOps._ensure_locks(board)

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

    # ----------------------------------------------------------
    # FLIP (entry point – fără lock care blochează așteptarea)
    # ----------------------------------------------------------
    @staticmethod
    async def flip(board: Board, player_id: str, row: int, col: int) -> str:
        BoardValidator.assert_invariants(board)

        # Init toate structurile necesare
        BoardOps._ensure_scheduler(board)
        BoardOps._ensure_watchers(board)
        BoardOps._ensure_players(board)
        BoardOps._ensure_pending(board)

        # IMPORTANT:
        # Nu mai folosim lock aici, ca să nu blocăm toți jucătorii
        # atunci când unul așteaptă pe o carte (regula 1-D).
        return await BoardOps._flip_locked(board, player_id, row, col)

    # ----------------------------------------------------------
    # Internal: flip logic respecting all game rules
    # ----------------------------------------------------------
    @staticmethod
    async def _flip_locked(board: Board, player_id: str, row: int, col: int) -> str:
        BoardValidator.assert_invariants(board)

        # ------------------------------------------------------
        # Step 0: Finish previous turn (Rule 3-A / 3-B)
        # ------------------------------------------------------
        await BoardOps._finish_previous_turn(board, player_id)

        # ------------------------------------------------------
        # Step 1: Check if coordinates are valid
        # ------------------------------------------------------
        if not (0 <= row < board.height and 0 <= col < board.width):
            return "Invalid coordinates."

        card = board._grid[row][col]

        # ------------------------------------------------------
        # Step 2: Get currently controlled cards
        # ------------------------------------------------------
        controlled = BoardOps._get_controlled_cards(board, player_id)

        # ------------------------------------------------------
        # CASE 1: Player has no controlled cards (First Card)
        # ------------------------------------------------------
        if len(controlled) == 0:
            return await BoardOps._handle_first_card(board, player_id, row, col)

        # ------------------------------------------------------
        # CASE 2: Player has one controlled card (Second Card)
        # ------------------------------------------------------
        elif len(controlled) == 1:
            return await BoardOps._handle_second_card(board, player_id, row, col, controlled[0])

        # Should not happen, but defensive coding
        else:
            board._players[player_id] = []
            return await BoardOps.look(board, player_id)

    # ----------------------------------------------------------
    # Helper Methods for Complete Flip Logic
    # ----------------------------------------------------------

    @staticmethod
    async def _finish_previous_turn(board: Board, player_id: str):
        """Handle Rule 3-A and 3-B: Finish previous turn"""
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
                # Clear ALL waiting players from the queue for these cards
                board._scheduler.clear_card((pr, pc))

        else:
            # Rule 3-B: Non-matching cards - turn face down if conditions met
            for (pr, pc) in positions:
                card = board._grid[pr][pc]
                # still on board, UP, and not controlled by another player
                if (card.state == CardState.UP and
                        card.controller is None):
                    CardStateMachine.transition(card, CardEvent.RESET, player_id)
                card.last_controller = None

        # Clean up pending state
        del board._pending[player_id]
        board._players[player_id] = []
        BoardOps._notify_watchers(board)

    @staticmethod
    def _get_controlled_cards(board: Board, player_id: str) -> List[Tuple[int, int]]:
        """Get list of positions controlled by player"""
        return [
            (r, c)
            for r, row_cards in enumerate(board._grid)
            for c, card in enumerate(row_cards)
            if card.state == CardState.UP and card.controller == player_id
        ]

    @staticmethod
    async def _handle_first_card(board: Board, player_id: str, row: int, col: int) -> str:
        """Handle Rule 1: First card flip attempt"""
        card = board._grid[row][col]

        # Rule 1-A: No card in space
        if card.state == CardState.NONE:
            return "No card in that space."

        # Rule 1-D: Card is face up and controlled by another player - WAIT
        if (card.state == CardState.UP and
                card.controller is not None and
                card.controller != player_id):

            # Player joins waiting queue - their activity is PAUSED here
            await board._scheduler.wait_for_turn((row, col), player_id)

            # When we reach here, player is first in queue AND card should be available
            card = board._grid[row][col]

            # Re-check conditions after waiting
            if card.state == CardState.NONE:
                board._scheduler.remove_player((row, col), player_id)
                return "No card in that space."

            if card.controller is not None and card.controller != player_id:
                # Still controlled - yield and try again
                await board._scheduler.release_card((row, col))
                return await BoardOps._handle_first_card(board, player_id, row, col)

            # Card is now available - take control (Rule 1-C)
            card.controller = player_id
            card.last_controller = player_id
            board._scheduler.remove_player((row, col), player_id)
            board._players[player_id] = [(row, col)]
            BoardOps._notify_watchers(board)
            return await BoardOps.look(board, player_id)

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
        """Handle Rule 2: Second card flip attempt"""
        r1, c1 = first_pos
        first_card = board._grid[r1][c1]
        second_card = board._grid[row][col]

        # Rule 2-A: No card in space - operation FAILS, relinquish first card
        if second_card.state == CardState.NONE:
            first_card.controller = None
            # Store pending state for Rule 3-B (only the first card)
            board._pending[player_id] = ([(r1, c1)], False)
            board._players[player_id] = []
            BoardOps._notify_watchers(board)
            return "No card in that space."

        # Rule 2-B: Card is face up and controlled by any player - FAIL, no wait
        if (second_card.state == CardState.UP and
                second_card.controller is not None):
            first_card.controller = None
            # Store pending state for Rule 3-B (only the first card)
            board._pending[player_id] = ([(r1, c1)], False)
            board._players[player_id] = []
            BoardOps._notify_watchers(board)
            controller_msg = "you" if second_card.controller == player_id else second_card.controller
            return f"Card is controlled by {controller_msg}."

        # Card is either DOWN or UP but not controlled
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
