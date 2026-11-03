"""Every species' art as players see it, plus each species' themed status dialog.

The line-ups render each stage (and the adult variants) side by side in one snapshot per
species and look, which is far cheaper than a whole app per stage. Regenerate with
``uv run pytest -n0 tests/ui/snapshots --snapshot-update`` and review the images.
"""

from collections.abc import Callable
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from tama.domain.animation import AnimationKey
from tama.domain.stage import LifeStage, Variant
from tama.ui.colours import Look, Mode
from tama.ui.sprites import available_species, hstack, load_sprite, to_content
from tests.ui.helpers import make_app, repo_with

SnapCompare = Callable[..., bool]

D, G, S = Variant.DEFAULT, Variant.GOOD, Variant.SCRUFFY
LINEUP: tuple[tuple[tuple[Variant, LifeStage], ...], ...] = (
    ((D, LifeStage.EGG), (D, LifeStage.BABY), (D, LifeStage.CHILD), (D, LifeStage.TEEN)),
    ((D, LifeStage.ADULT), (G, LifeStage.ADULT), (S, LifeStage.ADULT)),
    ((D, LifeStage.ELDER), (G, LifeStage.ELDER), (D, LifeStage.DEAD)),
)
"""Rows of (variant, stage) to show, each as its first idle frame."""


class LineupApp(App[None]):
    """One species' idle sprites in rows, without the game around them."""

    CSS = "Static { margin-bottom: 1; }"

    def __init__(self, species: str, *, theme: str, color: bool) -> None:
        super().__init__()
        self.theme = theme
        self._species = species
        self._color = color

    @override
    def compose(self) -> ComposeResult:
        look = Look(Mode.of(dark=self.current_theme.dark), color=self._color)
        for row in LINEUP:
            frames = [
                load_sprite(self._species, variant, stage, AnimationKey.IDLE).cells(look)[0]
                for variant, stage in row
            ]
            yield Static(to_content(hstack(frames, gap=2)))


@pytest.mark.parametrize("color", [True, False], ids=["colour", "mono"])
@pytest.mark.parametrize("theme", ["textual-dark", "textual-light"])
@pytest.mark.parametrize("species", available_species())
def test_species_lineup(snap_compare: SnapCompare, species: str, theme: str, color: bool) -> None:
    assert snap_compare(LineupApp(species, theme=theme, color=color), terminal_size=(90, 32))


@pytest.mark.parametrize("species", [s for s in available_species() if s != "tama"])
def test_status_screen_per_species(snap_compare: SnapCompare, species: str) -> None:
    app = make_app(repo_with(species=species, stage=LifeStage.ADULT))
    assert snap_compare(app, press=["s"])
