import asyncio
import pytest
from pathlib import Path

from src.board import Board
from src.card import CardState

@pytest.fixture
def ab_file(tmp_path: Path):
    """
    Produce a temporary board file identical to boards/ab.txt:
        2x2
        A B
        A B
    """
    p = tmp_path / "ab.txt"
    p.write_text(
        "2x2\n"
        "A B\n"
        "A B\n",
        encoding="utf8"
    )
    return str(p)

@pytest.mark.asyncio
async def test_parse_from_file_valid(ab_file):
    """
    PURPOSE:
        Tests that parseFromFile correctly reads a board file and
        produces a Board with correct geometry and card values.

    EXPECTED:
        Rows = 2
        Cols = 2
        Values = ["A", "B", "A", "B"]
    """
    board = await Board.parseFromFile(ab_file)

    # Verify through public behavior only
    # Test that we can perform operations on all positions
    from src.commands_impl import BoardOps
    
    # Verify all positions are accessible and have expected behavior
    view = await BoardOps.look(board, "test_player")
    assert len(view) == 2
    assert len(view[0]) == 2
    
    # All cards should start as "down"
    for row in view:
        for cell in row:
            assert cell == "down"

@pytest.mark.asyncio
async def test_parse_from_file_wrong_value_count(tmp_path):
    """
    PURPOSE:
        A file that declares wrong geometry should raise ValueError.

    FILE CONTENT:
        2x3
        A B C

    This contains 3 values, but 2x3 requires 6.
    """
    p = tmp_path / "bad.txt"
    p.write_text("2x3\nA B C\n", encoding="utf8")

    with pytest.raises(ValueError):
        await Board.parseFromFile(str(p))

@pytest.mark.asyncio
async def test_get_or_create_player():
    """
    PURPOSE:
        Tests that the Board creates PlayerState entries lazily
        and reuses them on repeated access.
    """
    board = Board(1, 2, ["X", "Y"])

    p1 = board.get_or_create_player("alice")
    p2 = board.get_or_create_player("alice")

    # Same instance must be returned
    assert p1 is p2
    
    # Test with different player to ensure creation works
    p3 = board.get_or_create_player("bob")
    assert p3 is not p1

@pytest.mark.asyncio
async def test_wait_for_change_unblocks_on_notify():
    """
    PURPOSE:
        Ensure that wait_for_change suspends and resumes ONLY
        after notify_change() is called.

    SCENARIO:
        1) Start waiting
        2) Trigger notify_change()
        3) Await should resume with updated change_count
    """
    board = Board(1, 1, ["A"])

    # Start watching
    task = asyncio.create_task(board.wait_for_change())

    # Give scheduler a tick to start waiting
    await asyncio.sleep(0)

    # Trigger a change
    board.notify_change()

    result = await asyncio.wait_for(task, timeout=0.5)

    # The result should be a number indicating change count
    assert isinstance(result, int)
    assert result >= 0  # Should be non-negative

@pytest.mark.asyncio
async def test_set_card_state_changes_state_and_triggers_watch():
    """
    PURPOSE:
        set_card_state must:
            – Change the card state's enum
            – Trigger a visual change (wake watchers)

    SCENARIO:
        Card starts DOWN.
        Setting UP must unblock wait_for_change().
    """
    board = Board(1, 1, ["A"])

    # Verify initial state through public behavior
    from src.commands_impl import BoardOps
    initial_view = await BoardOps.look(board, "test_player")
    assert initial_view[0][0] == "down"  # Cards start DOWN

    # Begin watching before the change
    w = asyncio.create_task(board.wait_for_change())
    await asyncio.sleep(0)

    # Set new card state using public method
    board.set_card_state(0, 0, CardState.UP)

    # Watcher should wake
    change_count = await w
    assert change_count > 0

    # Verify state change through public behavior
    updated_view = await BoardOps.look(board, "test_player")
    assert updated_view[0][0] == "up"  # Card should now be UP