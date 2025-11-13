from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


class CardState(Enum):
    """
    Represents the possible states of a card in the memory game.
    
    Values:
      NONE: Card has been removed from the board (no longer exists)
      DOWN: Card is face-down (value hidden from players)
      UP: Card is face-up (value visible to all players)
    """
    NONE = "none"   
    DOWN = "down"   
    UP   = "up"     


class CardEvent(Enum):
    """
    Events that trigger state transitions for cards.
    
    Values:
      FLIP: Toggle between face-up and face-down states
      RESET: Return card to face-down state (no-op if already down)
      REMOVE: Remove card from the board
    """
    FLIP   = auto()
    RESET  = auto()
    REMOVE = auto()

class PlayerState(Enum):
    """
    Represents the current state of a player in the game.
    
    Values:
      IDLE: Player has no cards selected
      ONE_SELECTED: Player has one card selected and is looking for a match
      PAIR_MATCHED: Player has successfully matched a pair (handled on next turn)
      PAIR_FAILED: Player has failed to match a pair (handled on next turn)
    """
    IDLE          = auto()  
    ONE_SELECTED  = auto()  
    PAIR_MATCHED  = auto()  
    PAIR_FAILED   = auto()  

@dataclass
class Player:
    """
    Represents a player in the memory game.
    
    Representation Invariant:
      - id is a non-empty string
      - state is a valid PlayerState value
      - selected contains valid (row, col) tuples within board bounds when applicable
    
    Effects:
      - Tracks player's current game state and selected card positions
      - selected list is empty when state is IDLE, PAIR_MATCHED, or PAIR_FAILED
      - selected contains 1 position when state is ONE_SELECTED
      - selected contains 2 positions temporarily during match resolution
    """
    id: str
    state: PlayerState = PlayerState.IDLE
    selected: List[Tuple[int, int]] = field(default_factory=list)



class CardStateMachine:
    """
    State machine managing valid transitions between card states.
    Implements the game rules for card state changes.
    """

    @staticmethod
    def transition(card, event: CardEvent, player_id: Optional[str] = None):
        """
        Apply a state transition to a card based on the provided event.
        
        Requires:
          - card has a valid CardState value in its state attribute
          - event is a valid CardEvent value
          - player_id is optional and used only for error context
        
        Effects:
          - Valid transitions:
            * DOWN  --FLIP-->   UP    (reveal face-down card)
            * UP    --FLIP-->   DOWN  (hide face-up card)  
            * UP    --REMOVE--> NONE  (remove card from board)
            * UP    --RESET-->  DOWN  (return to face-down state)
            * DOWN  --RESET-->  DOWN  (no-op, already face-down)
          - Modifies card.state to the new state
          - Returns the modified card for method chaining
          - Raises ValueError for invalid state transitions
          - Preserves all other card attributes (value, controller, etc.)
        """

        match (card.state, event):
            case (CardState.DOWN, CardEvent.FLIP):
                card.state = CardState.UP

            case (CardState.UP, CardEvent.FLIP):
                card.state = CardState.DOWN

            case (CardState.UP, CardEvent.REMOVE):
                card.state = CardState.NONE

            case (CardState.UP, CardEvent.RESET):
                card.state = CardState.DOWN

            case (CardState.DOWN, CardEvent.RESET):
                pass

            case _:
                raise ValueError(
                    f"Invalid transition {event.name} from {card.state.name} "
                    f"for card {getattr(card, 'value', '?')} "
                    f"(controller={getattr(card, 'controller', '?')})"
                )

        return card
