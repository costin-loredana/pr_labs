import asyncio
from collections import deque
from typing import Tuple, Dict, Deque, Optional
from src.game_states import CardState


DEBUG = True

def dbg(*args):
    if DEBUG:
        try:
            print("[DEBUG][Scheduler]", *args, flush=True)
        except Exception:
            pass


class PriorityScheduler:
    """
    FIFO scheduler for managing concurrent access to board positions.
    Provides fair queueing for players waiting to access controlled cards.
    """

    def __init__(self, height: int, width: int):
        """
        Initialize scheduler with queues for all board positions.
        
        Requires:
          - height > 0 and width > 0 (valid board dimensions)
        
        Effects:
          - Creates empty FIFO queues for every (row, col) position
          - Initializes internal state for tracking player queues
        """
        self._queues: Dict[Tuple[int, int], Deque[str]] = {
            (r, c): deque() for r in range(height) for c in range(width)
        }
        dbg("init scheduler:", height, "x", width)

    async def wait_for_turn(self, pos: Tuple[int, int], player_id: str, board=None) -> bool:
        """
        Request access to a card position, waiting if necessary.
        
        Requires:
          - pos is a valid (row, col) tuple within board dimensions
          - player_id is a non-empty string
          - board is optional Board instance for availability checking
        
        Effects:
          - Adds player to queue for position if not already present
          - Returns True if:
            * Player is first in queue AND
            * Card exists AND 
            * (Card is face-down OR card is uncontrolled/self-controlled)
          - Returns False if:
            * Player not first in queue OR
            * Card removed OR
            * Card controlled by another player
          - Removes player from queue when access granted or card removed
          - Non-blocking: returns immediately with access decision
        """
        if player_id not in self._queues[pos]:
            self._queues[pos].append(player_id)
            dbg("added to queue:", player_id, "for", pos, "queue:", list(self._queues[pos]))
        
        # Check if this player can actually get the card
        if board is not None:
            card = board._grid[pos[0]][pos[1]]
            
            if self._queues[pos] and self._queues[pos][0] == player_id:
                if card.state == CardState.NONE:
                    self._queues[pos].popleft()
                    dbg("card removed, removing player from queue:", player_id, "from", pos)
                    return False
                elif card.state == CardState.UP:
                    if card.controller is None or card.controller == player_id:
                        self._queues[pos].popleft()
                        dbg("granting access to:", player_id, "for", pos)
                        return True
                    dbg("card still controlled by another, keeping in queue:", player_id, "for", pos)
                    return False
                else:  
                    self._queues[pos].popleft()
                    dbg("granting access to face-down card:", player_id, "for", pos)
                    return True
        
        dbg("not first in queue:", player_id, "for", pos)
        return False

    async def release_card(self, pos: Tuple[int, int]):
        dbg("release_card: card", pos, "is available")

    def clear_card(self, pos: Tuple[int, int]):
        queue = self._queues[pos]
        if queue:
            dbg("clear_card: clearing queue for", pos, "players:", list(queue))
            queue.clear()

    def remove_player(self, pos: Tuple[int, int], player_id: str):
        queue = self._queues[pos]
        if player_id in queue:
            queue.remove(player_id)
            dbg("remove_player: removed", player_id, "from queue for", pos, "remaining:", list(queue))

    def waiting_on(self, player_id: str) -> Optional[Tuple[int, int]]:
        for pos, q in self._queues.items():
            if player_id in q:
                return pos
        return None

    def get_waiting_list(self, pos: Tuple[int, int]):
        return list(self._queues[pos])

    def get_queue_length(self, pos: Tuple[int, int]) -> int:
        return len(self._queues[pos])

    def can_player_act(self, player_id: str, target_pos: Tuple[int, int]) -> bool:
        waiting_pos = self.waiting_on(player_id)
        if waiting_pos is None:
            return True
        return waiting_pos == target_pos

    async def signal_available(self, pos: Tuple[int, int]):
        dbg("signal_available: card", pos, "is available")

    async def mark_card_removed(self, pos: Tuple[int, int]):
        self.clear_card(pos)
        dbg("mark_card_removed: card", pos, "marked as removed")

    async def mark_card_exists(self, pos: Tuple[int, int]):
        dbg("mark_card_exists: card", pos, "marked as existing")

    def reset_all(self):
        """
        Reset all queues to empty state.
        
        Effects:
          - Clears all player queues for all positions
          - Returns scheduler to initial empty state
        """
        for pos, queue in self._queues.items():
            if queue:
                dbg("reset_all: clearing queue for", pos, "players:", list(queue))
                queue.clear()
        dbg("reset_all: all queues cleared")

    def __repr__(self):
        active_queues = sum(1 for q in self._queues.values() if q)
        return f"<PriorityScheduler cards={len(self._queues)}, active_queues={active_queues}>"