import pytest
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.board import Board
from src.card import CardState
from src.commands_impl import BoardOps
from src.commands import look, flip


class TestBoardOps:

    @pytest.mark.asyncio
    async def test_look_operation(self):
        """
        PURPOSE:
            Ensure BoardOps.look returns a 2D matrix of visibility tokens.

        PRECONDITIONS:
            Board is newly created → all cards DOWN.

        POSTCONDITIONS:
            Returned view must be a fresh matrix of strings, not card objects.
            All entries must be "down".
        """
        board = Board(2, 2, ["A", "B", "C", "D"])
        view = await BoardOps.look(board, "test_player")

        assert len(view) == 2
        assert len(view[0]) == 2
        # All cards should be "down" initially
        for row in view:
            for cell in row:
                assert cell == "down"

    @pytest.mark.asyncio
    async def test_flip_first_card_success(self):
        """
        PURPOSE:
            Test correct behaviour for the *first flip* of a round.

        EXPECTED:
            • Flip succeeds
            • Card becomes UP
            • Controller assigned to flipping player
            • Player auto-created if missing

        VERIFICATION:
            • Check flip result is "success"
            • Verify player sees card as "my" via look operation
            • Verify other players see card as "up"
        """
        board = Board(2, 2, ["A", "B", "C", "D"])

        # No explicit player registration: should auto-create
        result = await BoardOps.flip(board, "player1", 0, 0)
        assert result == "success"

        # Verify through public look operations only
        player1_view = await BoardOps.look(board, "player1")
        assert player1_view[0][0] == "my"  # Player sees controlled card as "my"
        
        player2_view = await BoardOps.look(board, "player2") 
        assert player2_view[0][0] == "up"  # Others see it as "up"

    @pytest.mark.asyncio
    async def test_flip_removed_card_fail(self):
        """
        PURPOSE:
            A removed card cannot be flipped (legal fail).

        SCENARIO:
            Card is REMOVED, then player tries to flip.
            Must return "fail".

        VERIFICATION:
            • Check flip result is "fail"
            • Verify board state unchanged via look operation
        """
        board = Board(2, 2, ["A", "B", "C", "D"])
        
        # Set up REMOVED card using public API
        board.set_card_state(0, 0, CardState.REMOVED)

        # Get initial state
        initial_view = await BoardOps.look(board, "player1")
        
        result = await BoardOps.flip(board, "player1", 0, 0)
        assert result == "fail"
        
        # Verify no state change occurred
        final_view = await BoardOps.look(board, "player1")
        assert initial_view == final_view

    @pytest.mark.asyncio
    async def test_flip_new_player_auto_created(self):
        """
        PURPOSE:
            flip() must lazily auto-create PlayerState entries.

        EXPECTED:
            Previously nonexistent player can successfully flip cards.

        VERIFICATION:
            • Check flip result is "success" for new player
            • Verify new player can control cards via look operation
        """
        board = Board(2, 2, ["A", "B", "C", "D"])

        # Test that nonexistent player can successfully flip
        result = await BoardOps.flip(board, "nonexistent_player", 0, 0)
        assert result == "success"
        
        # Verify the flip worked through public look operation
        view = await BoardOps.look(board, "nonexistent_player")
        assert view[0][0] == "my"  # New player sees their controlled card

    @pytest.mark.asyncio
    async def test_flip_invalid_coordinates_fail(self):
        """
        PURPOSE:
            Flip must validate coordinates and fail safely.

        SCENARIO:
            Flip (5,5) on a 2x2 board → invalid → must return "fail".

        VERIFICATION:
            • Check flip result is "fail" for invalid coordinates
            • Verify board state unchanged via look operation
        """
        board = Board(2, 2, ["A", "B", "C", "D"])

        # Get initial state
        initial_view = await BoardOps.look(board, "player1")
        
        result = await BoardOps.flip(board, "player1", 5, 5)
        assert result == "fail"
        
        # Verify no state change occurred
        final_view = await BoardOps.look(board, "player1")
        assert initial_view == final_view


class TestCommands:
    """
    PURPOSE:
        Ensures the commands in src/commands.py are intentionally minimal
        and delegate *all real logic* to BoardOps.

        THIS IS A DESIGN REQUIREMENT:
            look() and flip() must remain tiny wrappers:
                look(board,pid) → BoardOps.look
                flip(board,pid,r,c) → BoardOps.flip
    """

    @pytest.mark.asyncio
    async def test_look_command_simplicity(self):
        """
        PURPOSE:
            look() returns a standard board view (simple delegation).

        VERIFICATION:
            • Check return type is list
            • Check dimensions match board size
        """
        board = Board(2, 2, ["A", "B", "C", "D"])
        view = await look(board, "test_player")

        assert isinstance(view, list)
        assert len(view) == 2
        assert len(view[0]) == 2

    @pytest.mark.asyncio
    async def test_flip_command_simplicity(self):
        """
        PURPOSE:
            flip() delegates to BoardOps.flip and returns:
                "success", "fail", or "wait"

        VERIFICATION:
            • Check return value is valid status string
        """
        board = Board(2, 2, ["A", "B", "C", "D"])

        result = await flip(board, "player1", 0, 0)
        assert result in ["success", "fail", "wait"]


@pytest.mark.asyncio
async def test_integration():
    """
    PURPOSE:
        Test integration between commands and BoardOps.

    BOARD:
        2x2 board with symmetric matching pairs:
            A B
            B A
        (Same pattern as ab.txt-style minimal boards)

    EXPECTED:
        • look() produces a 2x2 view
        • flip() produces valid statuses

    VERIFICATION:
        • Check look() returns correct dimensions
        • Check flip() returns valid status
    """
    print("\nTesting integration between commands and BoardOps...")

    board = Board(2, 2, ["A", "B", "B", "A"])

    # Test look through commands
    view = await look(board, "player1")
    assert len(view) == 2
    assert len(view[0]) == 2

    # Test flip through commands
    result = await flip(board, "player1", 0, 0)
    assert result in ["success", "fail", "wait"]

    print(" Integration test passed")


if __name__ == "__main__":
    asyncio.run(test_integration())
    print("\nRunning all tests with pytest...")
    pytest.main([__file__, "-v"])