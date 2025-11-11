# src/board_validator.py
from src.board import Board, _Card
from src.game_states import CardState


class BoardValidator:

    @staticmethod
    def _validate_down(card: _Card) -> None:
        # DOWN cards are face-down on the board and must not be controlled
        assert card.controller is None, f"DOWN card {card.value} must not have controller"

    @staticmethod
    def _validate_none(card: _Card) -> None:
        # NONE cards are removed from the board and must not be controlled
        assert card.controller is None, f"NONE card {card.value} must not have controller"

    @staticmethod
    def _validate_up(card: _Card) -> None:
        # UP cards may or may not be controlled; if controlled, controller must be a string
        assert isinstance(card.controller, (str, type(None))), (
            f"UP card {card.value} must have string or None controller, got {card.controller!r}"
        )

    STATE_VALIDATORS = {
        CardState.DOWN: _validate_down.__func__,
        CardState.NONE: _validate_none.__func__,
        CardState.UP: _validate_up.__func__,
    }

    @staticmethod
    def assert_invariants(board: Board) -> bool:
        """
        Validate all structural and semantic invariants of the Board.

        Ground truth:
          - the grid (`board._grid`) and the per-card fields (`state`, `controller`)
        Derived:
          - `board._players`: recomputed from the grid every time.
        """

        # --- Grid shape & contents ----------------------------------------
        assert isinstance(board._grid, list), "_grid must be list"
        assert len(board._grid) == board.height, "Grid height mismatch"

        for r, row in enumerate(board._grid):
            assert isinstance(row, list), "Each row must be list"
            assert len(row) == board.width, "Grid width mismatch in row {r}"

            for c, card in enumerate(row):
                assert isinstance(card, _Card), f"Cell ({r},{c}) not a _Card"
                assert card.state in (CardState.DOWN, CardState.UP, CardState.NONE), \
                    f"Invalid state {card.state} at ({r},{c})"

                validator = BoardValidator.STATE_VALIDATORS[card.state]
                validator(card)

                # value should always be present (even for NONE, because the _Card still exists)
                assert card.value is not None

        # --- last_controller consistency ----------------------------------
        for row in board._grid:
            for card in row:
                if card.controller is not None:
                    # if currently controlled, last_controller should match or be None
                    assert card.last_controller in (None, card.controller), (
                        f"Card {card.value} inconsistent last_controller "
                        f"{card.last_controller!r} vs controller {card.controller!r}"
                    )
                if card.last_controller is not None:
                    assert isinstance(card.last_controller, str), (
                        f"Invalid last_controller type {type(card.last_controller)} "
                        f"for card {card.value}"
                    )

        # --- Recompute board._players from the grid (derived view) --------
        players: dict[str, list[tuple[int, int]]] = {}

        for r, row in enumerate(board._grid):
            for c, card in enumerate(row):
                if card.state == CardState.UP and card.controller is not None:
                    players.setdefault(card.controller, []).append((r, c))

        # per-player sanity: at most 2 cards, no duplicates
        all_seen: set[tuple[int, int]] = set()
        for pid, coords in players.items():
            assert isinstance(pid, str), f"Invalid player ID type: {pid!r}"
            assert len(coords) <= 2, f"Player {pid} controls too many cards: {coords}"

            for (r, c) in coords:
                assert 0 <= r < board.height
                assert 0 <= c < board.width
                assert (r, c) not in all_seen, f"Duplicate control at ({r},{c})"
                all_seen.add((r, c))

                card = board._grid[r][c]
                # by construction these should hold, but we assert anyway:
                assert card.state == CardState.UP, (
                    f"Player {pid} controls card ({r},{c}) not in UP state"
                )
                assert card.controller == pid, (
                    f"Mismatch: player {pid} controls card with controller {card.controller}"
                )

        # overwrite board._players with the derived mapping
        board._players = players

        return True
