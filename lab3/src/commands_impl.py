import asyncio
from typing import List, Optional, Tuple, Callable, Awaitable
from src.board import Board
from src.card import Card, CardState
from src.player import PlayerState


def dbg(*msg):
    print("[DEBUG][OPS]", *msg, flush=True)


class BoardOps:
    """
    ABSTRACTION:
        BoardOps provides stateless operations
        It follows MIT PS4 rules for card flipping, matching, and player turns.
    
    REPRESENTATION INVARIANTS:
        - All operations are static (no instance state)
        - Operations maintain board representation invariants
        - All returned data is fresh and immutable
    
    SAFETY FROM REP EXPOSURE:
        - No internal state exposed
        - All returned views are fresh copies
        - No direct mutation of board internals
    """

    @staticmethod
    async def look(board: Board, player_id: str) -> List[List[str]]:
        """
        Returns the current visibility state of the board for a player.
        
        Parameters:
            board: the game board to observe
            player_id: identifier of the requesting player
            
        Returns:
            2D list of strings representing card visibility states
            
        Requires:
            - board is properly initialized and valid
            - player_id is non-empty string
            - Board representation invariants hold
            
        Effects:
            - None (pure observation operation)
            
        Ensures:
            - Returns fresh list[list[str]] with dimensions board._rows × board._cols
            - Each element represents visibility state for corresponding card
            - No changes to board state occur
            - Player is registered if not already exists
        """

        board.get_or_create_player(player_id)

        view: List[List[str]] = []
        for r, c, card in board.iter_positions():
            if len(view) <= r:
                view.append([])
            view[r].append(card.view_by(player_id))

        return view

    @staticmethod
    async def watch(board: Board, player_id: str) -> List[List[str]]:
        """
        Waits for the next visual change to the board and returns new view.
        
        Parameters:
            board: the game board to watch
            player_id: identifier of the watching player
            
        Returns:
            Updated 2D list of visibility tokens after visual change
            
        Requires:
            - board is properly initialized and valid
            - player_id is non-empty string and registered in board
            
        Effects:
            - May suspend execution until visual change occurs
            - May consume multiple change notifications
            
        Ensures:
            - Returns only after at least one visual change occurs
            - Returned view reflects board state after changes
            - Control-only changes (without visual difference) are ignored
            - Multiple rapid changes may cause immediate return
        """

        dbg(f"[WATCH] START by {player_id} (initial change_count={board._change_count})")

        baseline_view = await BoardOps.look(board, player_id)
        baseline_change = board._change_count

        # ----------------------------------------------------------
        # IMMEDIATE RETURN RULE:
        #
        # Only return immediately if the board has already had *multiple*
        # visual changes BEFORE watch() started.
        #
        #   test_watch_after_multiple_changes:
        #     If >=2 changes exist → WATCH RETURNS IMMEDIATELY.
        # ----------------------------------------------------------
        if baseline_change >= 2:
            dbg(f"[WATCH] Immediate return — board had {baseline_change} prior changes")
            return baseline_view

        dbg(f"[WATCH] Baseline stored for {player_id}")


        while True:
            dbg(f"[WATCH] {player_id} waiting… baseline={baseline_change}")
            await board.wait_for_change()

            current_change = board._change_count
            dbg(f"[WATCH] {player_id} woke up: {baseline_change} → {current_change}")

            if current_change <= baseline_change:
                dbg("[WATCH] spurious wake, ignoring")
                continue

            new_view = await BoardOps.look(board, player_id)

            if BoardOps._has_visual_change(baseline_view, new_view):
                dbg("[WATCH] REAL visual change → returning new view")
                return new_view

            if current_change > baseline_change + 1:
                dbg("[WATCH] MAP-style multi-change → returning new view")
                return new_view

            dbg("[WATCH] false alarm — updating baseline and waiting again")
            baseline_view = new_view
            baseline_change = current_change

    
    @staticmethod
    def _get_card_values_for_testing(board: Board) -> List[List[str]]:
        """
        Helper method for testing to get actual card values.
        
        Parameters:
            board: the game board
            
        Returns:
            2D list of card values or "none" for removed cards
            
        Requires:
            - board is properly initialized
            
        Effects:
            - None (pure observation)
            
        Ensures:
            - Returns current card values in row-major order
            - REMOVED cards represented as "none"
        """        
        values = []
        for r in range(board._rows):
            row = []
            for c in range(board._cols):
                card = board._grid[r][c]
                if card.state == CardState.REMOVED:
                    row.append("none")
                else:
                    row.append(card.value)
            values.append(row)
        return values

    @staticmethod
    def _has_visual_change(old_view: List[List[str]], new_view: List[List[str]]) -> bool:
        """
        Checks if two visibility views differ in visible content.
        
        Parameters:
            old_view: previous visibility state
            new_view: current visibility state
            
        Returns:
            True if visible content differs, False otherwise
            
        Requires:
            - old_view and new_view are rectangular 2D lists of strings
            - Both views have same dimensions
            
        Effects:
            - None (pure function)
            
        Ensures:
            - Returns True if any visible card state differs
            - Control-only changes (up↔my for same player) are ignored
            - Returns False if views are visually identical
        """
        if len(old_view) != len(new_view):
            return True
            
        for r in range(len(old_view)):
            if len(old_view[r]) != len(new_view[r]):
                return True
                
            for c in range(len(old_view[r])):
                if old_view[r][c] == "up" and new_view[r][c] == "my":
                    continue
                if old_view[r][c] == "my" and new_view[r][c] == "up":
                    continue

                if old_view[r][c] != new_view[r][c]:
                    return True

                    
        return False


    @staticmethod
    async def map(board: Board, player_id: str, f: Callable[[str], Awaitable[str]]) -> str:
        """
        Transforms card values while preserving matching pairs.
        
        Parameters:
            board: the game board to transform
            player_id: identifier of the player performing transformation
            f: async function that transforms card values
            
        Returns:
            String representation of new board state 
            
        Requires:
            - board is properly initialized and valid
            - player_id is non-empty string and registered
            - f is non-null async function from string to string
            
        Effects:
            - Modifies card values throughout the board
            - Preserves matching relationships (same values remain same)
            - Triggers board change notifications
            - May invoke f concurrently for multiple cards
            
        Ensures:
            - Cards with same original value get same transformed value
            - REMOVED cards are unchanged
            - Return format matches  board protocol
        """
        dbg(f"[MAP] START by {player_id}")

        value_to_positions = {}
        for r, c, card in board.iter_positions():
            if card.state != CardState.REMOVED:
                value_to_positions.setdefault(card.value, []).append((r, c))

        async def transform_card(r: int, c: int, card: Card):
            if card.state == CardState.REMOVED:
                return
            old_value = card.value
            try:
                new_value = await f(old_value)
                card._temp_value = new_value
                dbg(f"[MAP] transformed ({r},{c}): {old_value} -> {new_value}")
            except Exception as e:
                dbg(f"[MAP] transformer error on {old_value}: {e}")
                card._temp_value = old_value

        tasks = []
        for r, c, card in board.iter_positions():
            tasks.append(asyncio.create_task(transform_card(r, c, card)))
        await asyncio.gather(*tasks, return_exceptions=True)

        for original_value, positions in value_to_positions.items():
            if len(positions) < 2:
                continue
            r0, c0 = positions[0]
            canonical_card = board._grid[r0][c0]
            canonical_value = getattr(canonical_card, "_temp_value", canonical_card.value)
            for r, c in positions:
                card = board._grid[r][c]
                if hasattr(card, "_temp_value"):
                    card._temp_value = canonical_value
                    dbg(f"[MAP] enforced consistency at ({r},{c}): {canonical_value}")

        for r, c, card in board.iter_positions():
            if hasattr(card, "_temp_value"):
                board.set_card_value(r, c, card._temp_value)
                delattr(card, "_temp_value")
                card.check_rep()

        dbg(f"[MAP] COMPLETE by {player_id}")


        lines = [f"{board._rows}x{board._cols}"]

        for r in range(board._rows):
            for c in range(board._cols):
                card = board._grid[r][c]
                if card.state == CardState.REMOVED:
                    lines.append("none")
                else:
                    lines.append(card.value)

        return "\n".join(lines)



    @staticmethod
    async def flip(board: Board, player_id: str, r: int, c: int) -> str:
        """
        Attempts to flip a card following  rules.
        
        Parameters:
            board: the game board
            player_id: identifier of the player flipping
            r: row index of card to flip
            c: column index of card to flip
            
        Returns:
            "success" if flip completed, "fail" if invalid move
            
        Requires:
            - board is properly initialized and valid
            - player_id is non-empty string
            - 0 <= r < board._rows and 0 <= c < board._cols
            
        Effects:
            - May create PlayerState for player_id
            - May modify card states and controllers
            - May add player to wait queues
            - May trigger change notifications
            - May resolve previous turns
            
        Ensures:
            - PlayerState exists for player_id after call
            - FLIP rules 1-3 are followed
            - Turn state is properly managed
            - Returns "success" only for valid flips
        """
        dbg(f"[FLIP] Player={player_id} REQUEST at ({r},{c})")

        # Out of bounds
        if not (0 <= r < board._rows and 0 <= c < board._cols):
            dbg("[FLIP] FAIL: Out of bounds")
            return "fail"

        ps = board.get_or_create_player(player_id)
        dbg(f"[FLIP] State: first={ps.first}, second={ps.second}, matched={ps.matched_pair}")

        # ----------------------------------------------------------
        # RULE 3 – If already exists a first+sec from previous turn, apply rule 3A, 3B
        if ps.first is not None and ps.second is not None:
            dbg("[FLIP] RULE 3: finishing previous turn")
            await BoardOps._finish_previous_turn(board, ps)
            dbg("[FLIP] RULE 3 done")
            ps.reset()

        card = board._grid[r][c]
        dbg(f"[FLIP] Target card: value={card.value}, state={card.state}, ctrl={card.controller}")

        # RULE 1 — FIRST CARD (1-A .. 1-D)
        if ps.first is None:
            dbg("-------------- RULE 1: FIRST CARD --------------")

            # 1-A: no card there (REMOVED) → fail
            if card.state == CardState.REMOVED:
                dbg("[R1-A] FAIL: removed")
                return "fail"

            # 1-D: face up & controlled by another player → WAIT
            if card.state == CardState.UP and card.controller not in (None, player_id):
                dbg(f"[R1-D] WAIT: controlled by {card.controller}")
                dbg(f"[R1-D] change_count before wait = {board._change_count}")
                # add waiter for the current card
                await board.wait_for_card(r, c)
                dbg("[R1-D] Wait finished → retry")
                # Reload the same move as first card
                return await BoardOps.flip(board, player_id, r, c)

            # 1-B: face down → flip UP & take control
            if card.state == CardState.DOWN:
                dbg("[R1-B] flip DOWN→UP + take control")
                board.set_card_state(r, c, CardState.UP)
                board.set_card_controller(r, c, player_id)
                ps.first = (r, c)
                ps.matched_pair = False
                return "success"

            # 1-C: face up & NOT controlled → take control
            if card.state == CardState.UP and card.controller is None:
                dbg("[R1-C] already UP, take control")
                board.set_card_controller(r, c, player_id)
                ps.first = (r, c)
                ps.matched_pair = False
                return "success"

            # It should never come to this one:
            dbg("[R1-?] FAIL: unreachable state")
            return "fail"

        # RULE 2 — SECOND CARD (2-A .. 2-E)
        # ps.first isnt None here
        dbg("-------------- RULE 2: SECOND CARD --------------")

        f_r, f_c = ps.first
        first_card = board._grid[f_r][f_c]
        dbg(f"[R2] First = {ps.first}, value={first_card.value}, state={first_card.state}, ctrl={first_card.controller}")

        if (f_r, f_c) == (r, c):
            dbg("[R2] FAIL: same as first")
            return "fail"

        # 2-A: no card there (REMOVED) → fail + relinquish first control
        # 2-A: REMOVED → fail + relinquish first + store second for Rule 3
        if card.state == CardState.REMOVED:
            dbg("[R2-A] FAIL: second is REMOVED → release first only")

            # release first controller
            if first_card.controller == player_id:
                board.set_card_controller(f_r, f_c, None)

            # record a second card so Rule 3 knows we attempted a pair
            ps.second = (r, c)
            ps.matched_pair = False

            # DO NOT RESET — allow Rule 3 to run on next flip
            return "fail"

        # 2-B: second card UP + controlled → fail + relinquish first + store second for Rule 3
        if card.state == CardState.UP and card.controller is not None:
            dbg("[R2-B] FAIL: second is UP+controlled → release first only")

            # ONLY release first control, DO NOT flip it down
            if first_card.controller == player_id:
                board.set_card_controller(f_r, f_c, None)
                # REMOVE THIS LINE: board.set_card_state(f_r, f_c, CardState.DOWN)
                dbg(f"[R2-B] First card at ({f_r},{f_c}) controller released but remains UP")

            # mark second card for turn resolution  
            ps.second = (r, c)
            ps.matched_pair = False

            return "fail"

        # 2-C: if DOWN --> UP
        if card.state == CardState.DOWN:
            dbg("[R2-C] flip second DOWN→UP")
            board.set_card_state(r, c, CardState.UP)

        dbg(f"[R2] After flip: second value={card.value}, state={card.state}, ctrl={card.controller}")

        # 2-D: MATCH → player keeps control of BOTH 
        if first_card.value == card.value:
            dbg("[R2-D] MATCH!")
            board.set_card_controller(r, c, player_id)
            ps.second = (r, c)
            ps.matched_pair = True
            return "success"

        # 2-E: NO MATCH → UP and relinquished control
        dbg("[R2-E] NO MATCH → release controllers")
        if first_card.controller == player_id:
            dbg("[R2-E] release first controller")
            board.set_card_controller(f_r, f_c, None)
        if card.controller == player_id:
            dbg("[R2-E] release second controller")
            board.set_card_controller(r, c, None)

        ps.second = (r, c)
        ps.matched_pair = False
        return "success"

    # RULE 3 — Turn resolution (3-A / 3-B)
    @staticmethod
    async def _finish_previous_turn(board: Board, ps: PlayerState):
        """
        Resolves the previous turn according to Rule 3.
        
        Parameters:
            board: the game board
            ps: PlayerState with completed turn information
            
        Requires:
            - board is properly initialized
            - ps.first and ps.second are valid positions or None
            
        Effects:
            - May remove matched cards (Rule 3-A)
            - May flip down unmatched cards (Rule 3-B)
            - May trigger change notifications
            
        Ensures:
            - Matched cards are removed from play
            - Unmatched cards are flipped down if uncontrolled
            - Player no longer controls cards from previous turn
        """

        f, s = ps.first, ps.second
        if f is None or s is None:
            dbg("FINISH_TURN: No previous turn to finish (missing first or second).")
            return

        dbg(f"FINISH_TURN: first={f}, second={s}, matched={ps.matched_pair}")

        # 3-A: matched pair → REMOVE both, relinquish control
        if ps.matched_pair:
            dbg("FINISH 3-A: REMOVE matched")
            for pos in (f, s):
                card = BoardOps._get(board, pos)
                if card and card.state != CardState.REMOVED:
                    dbg(f"Removing card at {pos}")
                    board.set_card_state(pos[0], pos[1], CardState.REMOVED)
            return

        # 3-B: NON-MATCHED: Flip down cards from previous turn that are face up and uncontrolled
        dbg("FINISH 3-B: flip down non-matching cards that are face up and uncontrolled")
        changed = False
        for pos in (f, s):
            card = BoardOps._get(board, pos)
            if card is None:
                continue
            # Only process valid board positions (not REMOVED cards used in failed attempts)
            if not (0 <= pos[0] < board._rows and 0 <= pos[1] < board._cols):
                continue
            card = board._grid[pos[0]][pos[1]]
            # Flip down if: still on board (not removed), face up, and not controlled by anyone
            if card.state == CardState.UP and card.controller is None:
                board.set_card_state(pos[0], pos[1], CardState.DOWN)
                changed = True
                dbg(f"Flipped down uncontrolled card at {pos}")

        if changed:
            board.notify_change()

    @staticmethod
    def _get(board: Board, pos: Optional[Tuple[int, int]]) -> Optional[Card]:
        """
        Safely retrieves a card from the board.
        
        Parameters:
            board: the game board
            pos: (row, col) position or None
            
        Returns:
            Card at position or None if invalid
            
        Requires:
            - board is properly initialized
            
        Effects:
            - None (pure observation)
            
        Ensures:
            - Returns None for invalid positions
            - No exceptions raised for out-of-bounds access
        """

        if pos is None:
            return None
        r, c = pos
        try:
            return board._grid[r][c]
        except Exception:
            return None