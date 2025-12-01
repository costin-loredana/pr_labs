import asyncio
import pytest
from src.board import Board
from src.commands_impl import BoardOps
from src.card import CardState, Card


class TestMapFunctionality:

    @pytest.fixture
    async def sample_board(self):
        """
        Creates the canonical 2x2 example board:

            2x2
            A B
            A C

        This board is used throughout the suite to test:
             basic map()
             pair consistency ("A" appears twice)
             interleaving with flip()
             failure cases
        """
        values = ["A", "B", "A", "C"]
        return Board(2, 2, values)

    @pytest.mark.asyncio
    async def test_map_basic_transformation(self, sample_board):
        """
        PURPOSE:
            Test that map() correctly applies an async transformer to ALL
            non-removed cards.

        SCENARIO:
            add_x_transformer appends "X" to every card value.

        POSTCONDITIONS:
            - Every card ends with "X"
            -  return contains the new values
        """
        print("\n=== Testing Basic Transformation ===")
        
        async def add_x_transformer(value):
            await asyncio.sleep(0.01)
            return value + "X"
        
        result = await BoardOps.map(sample_board, "player1", add_x_transformer)
        
        for r, c, card in sample_board.iter_positions():
            assert card.value.endswith("X"), f"Card at ({r},{c}) not transformed: {card.value}"
        
        assert "AX" in result
        assert "BX" in result
        assert "CX" in result
        print(" Basic transformation test passed")

    @pytest.mark.asyncio
    async def test_map_pairwise_consistency(self, sample_board):
        """
        PURPOSE:
            Ensure that *matching pairs transform identically*,
            even if the transformer produces different output per call.

        SCENARIO:
            counting_transformer adds a numeric suffix based on how many
            times it has been called for a given value.

        EXPECTED:
            The two "A" cards MUST receive identical transformed strings.
        """
        print("\n=== Testing Pairwise Consistency ===")
        
        call_count = {}
        async def counting_transformer(value):
            await asyncio.sleep(0.01)
            call_count[value] = call_count.get(value, 0) + 1
            return f"{value}_{call_count[value]}"
        
        await BoardOps.map(sample_board, "player1", counting_transformer)
        
        a_cards = [card.value for _, _, card in sample_board.iter_positions() if card.value.startswith("A")]
        
        assert len(a_cards) == 2
        assert a_cards[0] == a_cards[1], f"Matching cards should be same: {a_cards}"
        print(f" Pairwise consistency maintained: {a_cards}")
        print(f" Transformer call counts: {call_count}")

    @pytest.mark.asyncio
    async def test_map_preserves_card_states(self):
        """
        PURPOSE:
            map() may change card VALUE ONLY.
            It must never alter card.state or card.controller.

        SCENARIO:
            Multiple cards have different states:
                 UP     DOWN    REMOVED    UP w/controller

        POSTCONDITIONS:
            All states identical to original
             All controllers preserved
        """
        print("\n=== Testing State Preservation ===")
        
        # Create board with initial values
        board = Board(2, 2, ["A", "B", "C", "D"])
        
        # Set up desired states using public API
        positions = list(board.iter_positions())
        
        # Position (0,0): UP with controller
        positions[0][2].state = CardState.UP
        positions[0][2].controller = "player1"
        
        # Position (0,1): DOWN (default state)
        # Position (1,0): REMOVED
        positions[2][2].state = CardState.REMOVED
        
        # Position (1,1): UP with different controller
        positions[3][2].state = CardState.UP
        positions[3][2].controller = "player2"
        
        # Record original states using public API
        original_states = {(r, c): (card.state, card.controller) 
                          for r, c, card in board.iter_positions()}
        
        async def simple_transformer(value):
            await asyncio.sleep(0.01)
            return value.lower()
        
        await BoardOps.map(board, "player1", simple_transformer)
        
        # Verify states preserved using public API
        for r, c, card in board.iter_positions():
            old_state, old_ctrl = original_states[(r, c)]
            assert card.state == old_state, f"Card at ({r},{c}) state changed from {old_state} to {card.state}"
            assert card.controller == old_ctrl, f"Card at ({r},{c}) controller changed from {old_ctrl} to {card.controller}"
        
        print(" All card states preserved correctly")

    @pytest.mark.asyncio
    async def test_map_with_removed_cards(self):
        """
        PURPOSE:
            Removed cards MUST NOT change during map().

        SCENARIO:
            One card is REMOVED, others transform normally.

        EXPECTED:
            - Removed cards retain original value
            - All other cards transformed
        """
        print("\n=== Testing with Removed Cards ===")
        
        board = Board(2, 2, ["A", "B", "A", "C"])
        
        # Set one card to REMOVED state using public API
        for r, c, card in board.iter_positions():
            if r == 1 and c == 0:  # Position (1,0)
                card.state = CardState.REMOVED
                removed_original_value = card.value
        
        # Record original values using public API
        original_values = {(r, c): card.value for r, c, card in board.iter_positions()}
        
        async def transformer(v):
            await asyncio.sleep(0.01)
            return "X" + v
        
        await BoardOps.map(board, "player1", transformer)
        
        # Verify using public API
        for r, c, card in board.iter_positions():
            original_value = original_values[(r, c)]
            if card.state == CardState.REMOVED:
                assert card.value == original_value, f"Removed card at ({r},{c}) changed from {original_value} to {card.value}"
            else:
                assert card.value == "X" + original_value, f"Normal card at ({r},{c}) not transformed correctly"
        
        print(" Removed cards correctly ignored")

    @pytest.mark.asyncio
    async def test_map_interleaving_operations(self, sample_board):
        """
        PURPOSE:
            Ensure map() can run concurrently with flip() without blocking
            or corrupting state.

        WHAT WE CHECK:
            - both tasks run
            - transformer starts/ends for each card
            - flip() completes
        """
        print("\n=== Testing Operation Interleaving ===")
        
        operations_log = []
        
        async def slow_transformer(value):
            operations_log.append(f"transformer_start_{value}")
            await asyncio.sleep(0.1)
            operations_log.append(f"transformer_end_{value}")
            return value * 2
        
        async def concurrent_flip():
            operations_log.append("flip_start")
            result = await BoardOps.flip(sample_board, "player2", 0, 0)
            operations_log.append(f"flip_end_{result}")
        
        map_task = asyncio.create_task(BoardOps.map(sample_board, "player1", slow_transformer))
        flip_task = asyncio.create_task(concurrent_flip())
        
        await asyncio.gather(map_task, flip_task)
        
        print(f"Operations log: {operations_log}")
        
        assert "flip_start" in operations_log
        assert any(op.startswith("flip_end") for op in operations_log), "Flip should have completed"
        
        assert len([op for op in operations_log if "transformer_end" in op]) == 4
        print(" Operations correctly interleaved")

    @pytest.mark.asyncio
    async def test_map_error_handling(self, sample_board):
        """
        PURPOSE:
            map() must survive a transformer raising an exception for
            a particular card.

        RULE:
            - Cards whose transformation fails must remain unchanged
            - Others transform normally
            - map() must NOT crash
        """
        print("\n=== Testing Error Handling ===")
        
        async def failing_transformer(value):
            await asyncio.sleep(0.01)
            if value == "B":
                raise ValueError("Test error for card B")
            return value + "_safe"
        
        # Record original values before transformation
        original_values = {(r, c): card.value for r, c, card in sample_board.iter_positions()}
        
        await BoardOps.map(sample_board, "player1", failing_transformer)
        
        # Check results using public API
        for r, c, card in sample_board.iter_positions():
            original_value = original_values[(r, c)]
            if original_value == "B":
                # Card B should remain unchanged due to exception
                assert card.value == original_value, f"Card B at ({r},{c}) should remain unchanged"
            else:
                # Other cards should be transformed
                assert card.value == original_value + "_safe", f"Card at ({r},{c}) not transformed correctly"
        
        print(" Error handling working correctly")

    @pytest.mark.asyncio
    async def test_map_return_format(self, sample_board):
        """
        PURPOSE:
            Validate the structure of the string returned by map().

        EXPECTED FORMAT:
            2x2
            <token>
            <token>
            <token>
            <token>
        """
        print("\n=== Testing Return Format ===")
        
        async def transformer(value):
            await asyncio.sleep(0.01)
            return value + "!"
        
        result = await BoardOps.map(sample_board, "player1", transformer)
        
        lines = result.split('\n')
        assert lines[0] == "2x2"
        
        body = "\n".join(lines[1:])
        
        assert "A!" in body
        assert "B!" in body
        assert "C!" in body
        
        print(" Return format correct")

    @pytest.mark.asyncio
    async def test_map_concurrent_maps(self):
        """
        PURPOSE:
            Test two map() calls running concurrently.

        EXPECTED:
            - Both tasks finish
            - Final board values have consistent suffixes
            - No races corrupt the board
        """
        print("\n=== Testing Concurrent Maps ===")
        
        board = Board(2, 2, ["A", "B", "A", "C"])
        completion = []
        
        async def t1(v):
            await asyncio.sleep(0.05)
            completion.append("t1")
            return v + "_1"
        
        async def t2(v):
            await asyncio.sleep(0.02)
            completion.append("t2")
            return v + "_2"
        
        task1 = asyncio.create_task(BoardOps.map(board, "p1", t1))
        task2 = asyncio.create_task(BoardOps.map(board, "p2", t2))
        
        await asyncio.gather(task1, task2)
        
        vals = [card.value for _,_,card in board.iter_positions()]
        suffixes = [v.split("_")[-1] for v in vals if "_" in v]
        
        if suffixes:
            assert len(set(suffixes)) == 1
        
        print(" Concurrent maps finished")

    @pytest.mark.asyncio
    async def test_map_empty_transformation(self, sample_board):
        """
        PURPOSE:
            Identity transformer must leave all card values unchanged.

        EXPECTED:
            After map(), board identical to initial state.
        """
        print("\n=== Testing Identity Transformation ===")
        
        original = {(r,c):card.value for r,c,card in sample_board.iter_positions()}
        
        async def identity(value):
            await asyncio.sleep(0.01)
            return value
        
        await BoardOps.map(sample_board, "player1", identity)
        
        for r,c,card in sample_board.iter_positions():
            assert card.value == original[(r,c)]
        
        print(" Identity transformation preserved values")


class TestMapEdgeCases:
    """
    PURPOSE:
        Validate corner cases:
             single-card boards
             all-removed boards
    """

    @pytest.mark.asyncio
    async def test_map_single_card_board(self):
        """
        PURPOSE:
            map() must work even for trivial 1×1 boards.

        TRANSFORMER:
            value → value repeated 3 times
        """
        print("\n=== Testing Single Card Board ===")
        
        board = Board(1, 1, ["X"])
        
        async def transformer(value):
            await asyncio.sleep(0.01)
            return value * 3
        
        result = await BoardOps.map(board, "player1", transformer)
        
        # Use public API to check the result
        for _, _, card in board.iter_positions():
            assert card.value == "XXX"
        
        assert "XXX" in result
        
        print(" Single card board handled correctly")

    @pytest.mark.asyncio 
    async def test_map_all_removed_board(self):
        """
        PURPOSE:
            If *all* cards are removed, map() must:
                - Not attempt transformations
                - Leave all values unchanged
                - Not crash
        """
        print("\n=== Testing All Removed Board ===")
        
        board = Board(2, 2, ["A", "B", "A", "B"])
        original = {}
        
        for r,c,card in board.iter_positions():
            original[(r,c)] = card.value
            card.state = CardState.REMOVED
        
        async def transformer(v):
            await asyncio.sleep(0.01)
            return "SHOULD_NOT_CHANGE"
        
        await BoardOps.map(board, "player1", transformer)
        
        for r,c,card in board.iter_positions():
            assert card.value == original[(r,c)]
        
        print(" All removed board handled correctly")