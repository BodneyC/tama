"""SVG snapshots of visits (SPEC §3.2) at the smallest supported terminal, 60x20.

Regenerate with ``uv run pytest -n0 tests/ui/snapshots --snapshot-update`` and review the diff.
"""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from textual.pilot import Pilot

from tama.domain.minigames import GameKind, Side
from tama.domain.minigames.four_in_a_row import FourInARow
from tama.domain.minigames.tic_tac_toe import TicTacToe
from tama.domain.stage import LifeStage, Variant
from tama.ui.app import TamaApp
from tama.ui.screens.games.pet_vs_pet import PetGame, PetVsPetScreen
from tama.ui.widgets.pet_view import ViewOptions
from tests.factories import FIXED_NOW, make_pet
from tests.ui.helpers import library_with, make_library_app, mono

SnapCompare = Callable[..., bool]
SIZE = (60, 20)
P, T = Side.PLAYER, Side.PET
_: Side | None = None


def visit_app(tmp_path: Path, **kwargs: Any) -> TamaApp:
    """Mochi (a chubby adult, the widest sprite) at home; Pip can visit, Bo and Cy can't."""
    library, files = library_with(
        tmp_path,
        replace(make_pet(stage=LifeStage.ADULT, variant=Variant.CHUBBY), name="Mochi"),
        replace(make_pet(stage=LifeStage.TEEN, species="owl"), name="Pip"),
        replace(make_pet(is_asleep=True, species="bear"), name="Bo"),
        replace(make_pet(paused_since=FIXED_NOW), name="Cy"),
    )
    return make_library_app(library, open_pet=files[0], **kwargs)


def test_visit_picker(snap_compare: SnapCompare, tmp_path: Path) -> None:
    assert snap_compare(visit_app(tmp_path), press=["v"], terminal_size=SIZE)


@pytest.mark.parametrize(
    ("theme", "view"),
    [(None, None), ("textual-light", None), (None, mono())],
    ids=["dark", "light", "mono"],
)
def test_visit_screen(
    snap_compare: SnapCompare, tmp_path: Path, theme: str | None, view: ViewOptions | None
) -> None:
    options: dict[str, Any] = {"view": view or ViewOptions(animate=False)}
    if theme:
        options["theme"] = theme
    app = visit_app(tmp_path, **options)
    assert snap_compare(app, press=["v", "3"], terminal_size=SIZE)


FOUR_MID = FourInARow(((), (P,), (T, P), (P, T, P), (T,), (T,), ()))
FOUR_DONE = FourInARow(((), (P, T), (P, T), (P, T), (P,), (), ()))
TIC_TAC_TOE_MID = TicTacToe((P, _, _, _, T, _, _, _, _))
TIC_TAC_TOE_DONE = TicTacToe((P, T, P, P, T, T, T, P, P))


@pytest.mark.parametrize(
    ("kind", "game"),
    [
        (GameKind.FOUR_IN_A_ROW, FOUR_MID),
        (GameKind.FOUR_IN_A_ROW, FOUR_DONE),
        (GameKind.TIC_TAC_TOE, TIC_TAC_TOE_MID),
        (GameKind.TIC_TAC_TOE, TIC_TAC_TOE_DONE),
    ],
    ids=["four-mid", "four-won", "tic-tac-toe-mid", "tic-tac-toe-draw"],
)
@pytest.mark.parametrize("view", [None, mono()], ids=["colour", "mono"])
def test_pet_vs_pet_game(
    snap_compare: SnapCompare,
    tmp_path: Path,
    kind: GameKind,
    game: PetGame,
    view: ViewOptions | None,
) -> None:
    view = view or ViewOptions(animate=False)

    async def watch(pilot: Pilot[None]) -> None:
        await pilot.press("v", "3")
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, TamaApp)
        assert app.visit is not None
        app.push_screen(PetVsPetScreen(kind, app.visit, view, game=game, autoplay=False))
        await pilot.pause()

    app = visit_app(tmp_path, view=view)
    assert snap_compare(app, run_before=watch, terminal_size=SIZE)


def test_boards_are_what_they_claim() -> None:
    assert FOUR_MID.result is None
    assert FOUR_DONE.winner is P
    assert TIC_TAC_TOE_MID.result is None
    assert TIC_TAC_TOE_DONE.is_full
    assert TIC_TAC_TOE_DONE.winner is None
