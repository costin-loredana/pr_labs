from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class PlayerState:
    """
    A PlayerState tracks the transient flip selection state for one player
    during their turn in the Memory Scramble game.
    
    ABSTRACTION FUNCTION (AF):
        AF(self) = a player's current turn state consisting of:
        - first: the position of the first card selected this turn, or None
        - second: the position of the second card selected this turn, or None  
        - matched_pair: whether the two selected cards form a matching pair
    
    REPRESENTATION INVARIANTS (RI):
        - If matched_pair == True, then first ≠ None and second ≠ None
        - If second == None, then matched_pair == False
        - first and second are either None or valid (row, col) tuples
        - first and second are distinct positions when both are not None
        - Tuple coordinates are non-negative integers
    
    SAFETY FROM REP EXPOSURE:
        - All fields are immutable (tuples or primitive types)
        - No external references to mutable state
        - reset() maintains representation invariants
    """
    
    first: Optional[Tuple[int, int]] = None
    second: Optional[Tuple[int, int]] = None
    matched_pair: bool = False

    def reset(self):
        """
        Resets the player's turn state to initial conditions.
        
        Requires:
            - Representation invariants hold before call
            
        Effects:
            - Sets first = None
            - Sets second = None  
            - Sets matched_pair = False
            
        Ensures:
            - All fields reset to default values
            - Representation invariants hold after call
            - Player is ready to start a new turn
        """
        self.first = None
        self.second = None
        self.matched_pair = False
        self.check_rep()

    def check_rep(self):
        """
        Verifies all representation invariants hold.
        
        Requires: nothing
        
        Effects:
            - Raises AssertionError if any representation invariant is violated
            - No state modification if invariants hold
            
        Ensures:
            - All representation invariants are satisfied
            - PlayerState is in valid configuration
        """
        # RI: If matched_pair is True, both positions must exist
        if self.matched_pair:
            assert self.first is not None, "Matched pair must have first position"
            assert self.second is not None, "Matched pair must have second position"
        
        # RI: If second is None, matched_pair must be False
        if self.second is None:
            assert not self.matched_pair, "Cannot have match without second card"
        
        # RI: Positions should be valid tuples if not None
        if self.first is not None:
            assert isinstance(self.first, tuple), "First position must be tuple"
            assert len(self.first) == 2, "First position must be (r, c) tuple"
            r, c = self.first
            assert isinstance(r, int), "Row coordinate must be integer"
            assert isinstance(c, int), "Column coordinate must be integer"
            assert r >= 0, "Row coordinate must be non-negative"
            assert c >= 0, "Column coordinate must be non-negative"
            
        if self.second is not None:
            assert isinstance(self.second, tuple), "Second position must be tuple"
            assert len(self.second) == 2, "Second position must be (r, c) tuple"
            r, c = self.second
            assert isinstance(r, int), "Row coordinate must be integer"
            assert isinstance(c, int), "Column coordinate must be integer"
            assert r >= 0, "Row coordinate must be non-negative"
            assert c >= 0, "Column coordinate must be non-negative"
        
        # RI: Positions must be distinct when both exist
        if self.first is not None and self.second is not None:
            assert self.first != self.second, "First and second positions must be distinct"

    def has_completed_turn(self) -> bool:
        """
        Checks if the player has a completed turn that needs resolution.
        
        Returns:
            True if both first and second positions are set, False otherwise
            
        Requires: nothing
        
        Effects: none (pure observation)
        
        Ensures:
            - Returns True only when both first and second are not None
            - Return value indicates whether turn resolution is needed
        """
        return self.first is not None and self.second is not None

    def is_selecting_first_card(self) -> bool:
        """
        Checks if the player is ready to select their first card.
        
        Returns:
            True if first position is None, False otherwise
            
        Requires: nothing
            
        Effects: none (pure observation)
        
        Ensures:
            - Returns True when no card has been selected this turn
            - Returns False when first card is already selected
        """
        return self.first is None

    def is_selecting_second_card(self) -> bool:
        """
        Checks if the player is ready to select their second card.
        
        Returns:
            True if first position is set but second is None, False otherwise
            
        Requires: nothing
            
        Effects: none (pure observation)
        
        Ensures:
            - Returns True when first card is selected but second is not
            - Returns False when either no cards or both cards are selected
        """
        return self.first is not None and self.second is None

    def set_first_card(self, position: Tuple[int, int]):
        """
        Sets the first card position for the current turn.
        
        Parameters:
            position: (row, col) tuple of the first card selected
            
        Requires:
            - position is valid (r, c) tuple with non-negative integers
            - first is currently None (starting new turn)
            - Representation invariants hold before call
            
        Effects:
            - Sets first = position
            - Sets matched_pair = False
            
        Ensures:
            - first == position after call
            - matched_pair == False after call
            - Representation invariants hold after call
        """
        assert self.first is None, "Cannot set first card when already selected"
        assert isinstance(position, tuple) and len(position) == 2, "Position must be (r, c) tuple"
        r, c = position
        assert isinstance(r, int) and isinstance(c, int), "Coordinates must be integers"
        assert r >= 0 and c >= 0, "Coordinates must be non-negative"
        
        self.first = position
        self.matched_pair = False
        self.check_rep()

    def set_second_card(self, position: Tuple[int, int], matched: bool):
        """
        Sets the second card position and match result for the current turn.
        
        Parameters:
            position: (row, col) tuple of the second card selected
            matched: whether the two selected cards form a matching pair
            
        Requires:
            - position is valid (r, c) tuple with non-negative integers
            - first is not None (first card already selected)
            - second is currently None
            - position != first (distinct cards)
            - Representation invariants hold before call
            
        Effects:
            - Sets second = position
            - Sets matched_pair = matched
            
        Ensures:
            - second == position after call
            - matched_pair == matched after call
            - Representation invariants hold after call
        """
        assert self.first is not None, "Must have first card before setting second"
        assert self.second is None, "Cannot set second card when already selected"
        assert isinstance(position, tuple) and len(position) == 2, "Position must be (r, c) tuple"
        r, c = position
        assert isinstance(r, int) and isinstance(c, int), "Coordinates must be integers"
        assert r >= 0 and c >= 0, "Coordinates must be non-negative"
        assert position != self.first, "Second card must be different from first"
        
        self.second = position
        self.matched_pair = matched
        self.check_rep()

    def get_selected_positions(self) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """
        Returns both selected card positions.
        
        Returns:
            Tuple of (first_position, second_position)
            
        Requires: nothing
            
        Effects: none (pure observation)
        
        Ensures:
            - Returns current first and second positions (may be None)
            - Return values are immutable and safe for external use
        """
        return (self.first, self.second)

    def __str__(self):
        """
        Returns string representation for debugging.
        
        Returns: formatted string showing current state
        
        Requires: nothing
        
        Effects: none (pure function)
        
        Ensures:
            - Return value clearly represents current state
            - No state modification occurs
        """
        return f"PlayerState(first={self.first}, second={self.second}, matched={self.matched_pair})"