"""Every species' art as players see it, its tricks, and each species' themed status dialog.

The line-ups render each stage (and the adult variants) side by side in one snapshot per
species and look, which is far cheaper than a whole app per stage. Regenerate with
``uv run pytest -n0 tests/ui/snapshots --snapshot-update`` and review the images.
"""

from collections.abc import Callable
from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from tama.domain.animation import AnimationKey, trick_animation
from tama.domain.stage import LifeStage, Trick, Variant
from tama.ui.colours import Look, Mode
from tama.ui.sprites import available_species, hstack, load_sprite, to_content
from tests.ui.helpers import make_app, repo_with

SnapCompare = Callable[..., bool]

D, G, S, C = Variant.DEFAULT, Variant.GOOD, Variant.SCRUFFY, Variant.CHUBBY
LINEUP: tuple[tuple[tuple[Variant, LifeStage], ...], ...] = (
    ((D, LifeStage.EGG), (D, LifeStage.BABY), (D, LifeStage.CHILD), (D, LifeStage.TEEN)),
    ((D, LifeStage.ADULT), (G, LifeStage.ADULT), (S, LifeStage.ADULT), (C, LifeStage.ADULT)),
    ((D, LifeStage.ELDER), (G, LifeStage.ELDER), (C, LifeStage.ELDER), (D, LifeStage.DEAD)),
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
    assert snap_compare(LineupApp(species, theme=theme, color=color), terminal_size=(120, 32))


@pytest.mark.parametrize("species", [s for s in available_species() if s != "tama"])
def test_status_screen_per_species(snap_compare: SnapCompare, species: str) -> None:
    app = make_app(repo_with(species=species, stage=LifeStage.ADULT))
    assert snap_compare(app, press=["s"])


TRICK_KEY_FRAMES = {Trick.WAVE: 0, Trick.SPIN: 3, Trick.DANCE: 0, Trick.BOW: 2}
"""The frame that best shows each trick: paw up, seen from behind, mid-hop, head down."""


class TricksApp(App[None]):
    """One species' tricks as a child and as a good adult, each at its key frame."""

    CSS = "Static { margin-bottom: 1; }"

    def __init__(self, species: str) -> None:
        super().__init__()
        self._species = species

    @override
    def compose(self) -> ComposeResult:
        look = Look(Mode.of(dark=self.current_theme.dark), color=True)
        for variant, stage in ((D, LifeStage.CHILD), (G, LifeStage.ADULT)):
            frames = [
                load_sprite(self._species, variant, stage, trick_animation(trick)).cells(look)[
                    frame
                ]
                for trick, frame in TRICK_KEY_FRAMES.items()
            ]
            yield Static(to_content(hstack(frames, gap=2)))


@pytest.mark.parametrize("species", available_species())
def test_trick_key_frames(snap_compare: SnapCompare, species: str) -> None:
    """Wave, spin, dance and bow (SPEC §2.10), for every species."""
    assert snap_compare(TricksApp(species), terminal_size=(120, 24))
