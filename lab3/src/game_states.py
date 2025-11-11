# ===============================================================
# 🧩 MEMORY SCRAMBLE – Core State Definitions (merged version)
# ===============================================================
# This script unifies:
#   - CardState and CardEvent (from card_states.py)
#   - PlayerState (from player_states.py)
#   - Player dataclass
#   - CardStateMachine logic
#
# Everything here is standalone and compatible with BoardOps.
# ===============================================================

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# ---------------------------------------------------------------
# 🃏 Card States and Events
# ---------------------------------------------------------------
class CardState(Enum):
    NONE = "none"   # removed
    DOWN = "down"   # face-down
    UP   = "up"     # face-up


class CardEvent(Enum):
    FLIP   = auto()
    RESET  = auto()
    REMOVE = auto()


# ---------------------------------------------------------------
# 👤 Player States
# ---------------------------------------------------------------
class PlayerState(Enum):
    IDLE          = auto()  # before flipping any card
    ONE_SELECTED  = auto()  # flipped first card
    PAIR_MATCHED  = auto()  # last two matched (cleanup next turn)
    PAIR_FAILED   = auto()  # last two mismatched (cleanup next turn)


# ---------------------------------------------------------------
# 🧑‍💻 Player Model
# ---------------------------------------------------------------
@dataclass
class Player:
    """
    Represents a player participating in the game.
    Tracks their state and which cards they've selected.
    """
    id: str
    state: PlayerState = PlayerState.IDLE
    selected: List[Tuple[int, int]] = field(default_factory=list)


# ---------------------------------------------------------------
# ♻️ Card State Machine
# ---------------------------------------------------------------
class CardStateMachine:
    """
    Defines the allowed transitions for a card.
    Controller logic (ownership, fairness, waiting queues)
    is handled in BoardOps.
    """

    @staticmethod
    def transition(card, event: CardEvent, player_id: Optional[str] = None):
        """
        Valid transitions:
            DOWN  --FLIP-->   UP
            UP    --FLIP-->   DOWN
            UP    --REMOVE--> NONE
            UP    --RESET-->  DOWN
            DOWN  --RESET-->  DOWN (no-op)
        """

        match (card.state, event):
            # DOWN → UP
            case (CardState.DOWN, CardEvent.FLIP):
                card.state = CardState.UP

            # UP → DOWN
            case (CardState.UP, CardEvent.FLIP):
                card.state = CardState.DOWN

            # UP → NONE
            case (CardState.UP, CardEvent.REMOVE):
                card.state = CardState.NONE

            # UP → DOWN (reset)
            case (CardState.UP, CardEvent.RESET):
                card.state = CardState.DOWN

            # DOWN + RESET = no-op
            case (CardState.DOWN, CardEvent.RESET):
                pass

            case _:
                raise ValueError(
                    f"Invalid transition {event.name} from {card.state.name} "
                    f"for card {getattr(card, 'value', '?')} "
                    f"(controller={getattr(card, 'controller', '?')})"
                )

        return card
