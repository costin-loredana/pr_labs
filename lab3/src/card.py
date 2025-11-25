from enum import Enum
from typing import Optional


class CardState(Enum):
    """
    Represents the possible visibility states of a card in Memory Scramble.
    
    Values:
        DOWN: Card is face-down and not visible to players
        UP: Card is face-up and visible to all players  
        REMOVED: Card has been matched and is permanently removed from play
    """
    DOWN = "down"
    UP = "up"
    REMOVED = "none"


class Card:
    """
    A Card represents a single card in the Memory Scramble game.
    
    ABSTRACTION FUNCTION (AF):
        AF(self) = a game card with:
        - value: the identifying string value of the card
        - state: current visibility state (DOWN, UP, or REMOVED)
        - controller: player ID controlling the card when face-up, or None
    
    REPRESENTATION INVARIANTS (RI):
        - _value is a non-empty string
        - _state is a valid CardState value
        - If _state == REMOVED, then _controller == None
        - If _controller != None, then _state == UP
        - _board_ref is either None or a valid Board reference
    
    SAFETY FROM REP EXPOSURE:
        - All properties return immutable values (strings, enums, or None)
        - No internal mutable state is exposed to clients
        - Setters maintain representation invariants
    """
    
    def __init__(self, value: str, state: CardState = CardState.DOWN, controller: Optional[str] = None):
        """
        Creates a new Card with specified value and initial state.
        
        Parameters:
            value: the identifying string value of the card
            state: initial visibility state (default: DOWN)
            controller: initial controller if card is UP (default: None)
            
        Requires:
            - value is a non-empty string
            - state is a valid CardState value
            - If controller is not None, then state must be UP
            - If state is REMOVED, then controller must be None
            
        Effects:
            - Initializes card with specified value, state, and controller
            - Sets _board_ref to None
            - Stores initial value for map() operations
            
        Ensures:
            - Representation invariants hold
            - Card is ready for game use
        """
        self._value = value
        self._state = state
        self._controller = controller
        self._board_ref = None
        self._initial_value = value  # Required for map() tests
        self.check_rep()

    def set_board_ref(self, board):
        """
        Sets reference to parent Board for change notifications.
        
        Parameters:
            board: the parent Board object
            
        Requires:
            - board has notify_change() method
            - board is not None
            
        Effects:
            - Sets _board_ref to board
            
        Ensures:
            - _board_ref == board after call
            - Future state changes will notify the board
        """
        self._board_ref = board

    def _notify_board(self):
        """
        Notifies the parent board of visual changes to this card.
        
        Requires: nothing
        
        Effects:
            - If _board_ref exists and has notify_change method, calls it
            - No effect if no board reference exists
            
        Ensures:
            - Board is notified of visual state changes
            - No exceptions raised if board reference is invalid
        """
        if self._board_ref and hasattr(self._board_ref, 'notify_change'):
            self._board_ref.notify_change()

    @property
    def value(self) -> str:
        """
        Returns the card's value string.
        
        Returns: non-empty string value of the card
        
        Requires: nothing
        
        Effects: none (pure observation)
        
        Ensures:
            - Returns current _value
            - Return value is non-empty string
        """
        return self._value

    @value.setter
    def value(self, new_value: str):
        """
        Sets the card's value and notifies board if changed.
        
        Parameters:
            new_value: new string value for the card
            
        Requires:
            - new_value is a non-empty string
            
        Effects:
            - If _value != new_value, updates value and notifies board
            - No effect if value unchanged
            
        Ensures:
            - _value == new_value after call
            - Representation invariants hold
            - Board notified if visual change occurred
        """
        if self._value != new_value:
            self._value = new_value
            self._notify_board()
        self.check_rep()

    @property
    def state(self) -> CardState:
        """
        Returns the card's current visibility state.
        
        Returns: current CardState value
        
        Requires: nothing
        
        Effects: none (pure observation)
        
        Ensures:
            - Returns current _state
            - Return value is valid CardState
        """
        return self._state

    @state.setter
    def state(self, new_state: CardState):
        """
        Sets the card's visibility state and maintains invariants.
        
        Parameters:
            new_state: new CardState value
            
        Requires:
            - new_state is a valid CardState value
            
        Effects:
            - Updates _state to new_state
            - If transitioning to REMOVED, sets controller to None
            - Notifies board if state actually changed
            
        Ensures:
            - _state == new_state after call
            - If new_state == REMOVED, then _controller == None
            - Representation invariants hold
            - Board notified if visual change occurred
        """
        if new_state == CardState.REMOVED and self._controller is not None:
            self._controller = None

        if self._state != new_state:
            self._state = new_state
            self._notify_board()
        self.check_rep()

    @property
    def controller(self) -> Optional[str]:
        """
        Returns the current controller of the card.
        
        Returns: player ID string or None if no controller
        
        Requires: nothing
        
        Effects: none (pure observation)
        
        Ensures:
            - Returns current _controller
            - Return value is None or non-empty string
            - If return value is not None, card state is UP
        """
        return self._controller

    @controller.setter
    def controller(self, new_controller: Optional[str]):
        """
        Sets the card's controller and maintains invariants.
        
        Parameters:
            new_controller: player ID string or None
            
        Requires:
            - If new_controller is not None, card must be UP
            - new_controller is either None or non-empty string
            
        Effects:
            - Updates _controller to new_controller
            - Notifies board if controller changed and card is UP
            
        Ensures:
            - _controller == new_controller after call
            - Representation invariants hold
            - Board notified if visual change occurred
        """
        if self._controller != new_controller:
            self._controller = new_controller
            if self._state == CardState.UP:
                self._notify_board()
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
            - Card is in valid configuration
        """
        # RI: value is a non-empty string
        assert isinstance(self._value, str) and self._value, f"Invalid card value: {self._value}"
        
        # RI: state is in CardState
        assert self._state in CardState, f"Invalid card state: {self._state}"
        
        # RI: If state == REMOVED → controller is None
        if self._state == CardState.REMOVED:
            assert self._controller is None, "REMOVED card cannot have controller"
        
        # RI: If controller is not None → state == UP
        if self._controller is not None:
            assert self._state == CardState.UP, "Controlled card must be UP"

    def view_by(self, player_id: str) -> str:
        """
        Returns visibility token for a specific player's view.
        
        Parameters:
            player_id: identifier of the viewing player
            
        Returns:
            Visibility token string: "none", "down", "my", or "up"
            
        Requires:
            - player_id is non-empty string
            - Representation invariants hold
            
        Effects: none (pure observation)
        
        Ensures:
            - Returns "none" if card is REMOVED
            - Returns "down" if card is DOWN  
            - Returns "my" if card is UP and controlled by player_id
            - Returns "up" if card is UP and not controlled by player_id
            - Return value follows MIT Memory Scramble protocol
        """
        self.check_rep()

        if self.state == CardState.REMOVED:
            return "none"

        if self.state == CardState.DOWN:
            return "down"

        if self.controller == player_id:
            return "my"

        if self.state == CardState.UP:
            return "up"

    def can_be_flipped_by(self, player_id: str) -> bool:
        """
        Checks if the card can be flipped by the specified player.
        
        Parameters:
            player_id: identifier of the player attempting to flip
            
        Returns:
            True if player can flip card, False otherwise
            
        Requires:
            - player_id is non-empty string
            
        Effects: none (pure observation)
        
        Ensures:
            - Returns False if card is REMOVED
            - Returns False if card is UP and controlled by another player
            - Returns True if card is DOWN
            - Returns True if card is UP and uncontrolled or controlled by player_id
        """
        if self.state == CardState.REMOVED:
            return False
            
        if self.state == CardState.UP and self.controller not in (None, player_id):
            return False
            
        return True

    def is_visible_to(self, player_id: str) -> bool:
        """
        Checks if the card's value is visible to the specified player.
        
        Parameters:
            player_id: identifier of the viewing player
            
        Returns:
            True if player can see card value, False otherwise
            
        Requires:
            - player_id is non-empty string
            
        Effects: none (pure observation)
        
        Ensures:
            - Returns True if card is UP or REMOVED
            - Returns False if card is DOWN
            - Controller status does not affect visibility of value
        """
        return self.state in (CardState.UP, CardState.REMOVED)

    def __str__(self) -> str:
        """
        Returns informal string representation for debugging.
        
        Returns: formatted string showing card state and value
        
        Requires: nothing
        
        Effects: none (pure function)
        
        Ensures:
            - Return value clearly represents current card state
            - No state modification occurs
        """
        if self._state == CardState.REMOVED:
            return f"REMOVED({self._value})"
        if self._state == CardState.DOWN:
            return f"DOWN({self._value})"
        return f"UP({self._value}, controller={self._controller})"