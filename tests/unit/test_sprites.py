from collections.abc import Iterator
from pathlib import Path

import pytest

from tama.domain.animation import AnimationKey
from tama.domain.stage import LifeStage, Variant
from tama.ui import sprites
from tama.ui.sprites import PLACEHOLDER, load_frames, parse_frames

MAX_WIDTH = 16
MAX_HEIGHT = 8


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    load_frames.cache_clear()
    yield
    load_frames.cache_clear()


def test_parse_single_frame() -> None:
    assert parse_frames(" .--.\n( oo )  \n") == (" .--.\n( oo )",)


def test_parse_multiple_frames() -> None:
    assert parse_frames("a\n---\nb\n  ---  \nc\n") == ("a", "b", "c")


def test_parse_drops_empty_frames() -> None:
    assert parse_frames("---\n\n---\nx\n---\n") == ("x",)


@pytest.mark.parametrize("stage", list(LifeStage))
def test_every_stage_has_an_idle_sprite_that_fits(stage: LifeStage) -> None:
    frames = load_frames(Variant.DEFAULT, stage, AnimationKey.IDLE)

    assert frames != PLACEHOLDER
    for frame in frames:
        lines = frame.splitlines()
        assert len(lines) <= MAX_HEIGHT
        assert max(len(line) for line in lines) <= MAX_WIDTH
        assert frame.isascii()


def test_missing_variant_falls_back_to_default() -> None:
    assert load_frames(Variant.GOOD, LifeStage.ADULT, AnimationKey.IDLE) == load_frames(
        Variant.DEFAULT, LifeStage.ADULT, AnimationKey.IDLE
    )


def test_missing_animation_falls_back_to_idle() -> None:
    assert load_frames(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.EAT) == load_frames(
        Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE
    )


def test_missing_art_uses_a_placeholder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "default" / "child").mkdir(parents=True)
    (tmp_path / "default" / "child" / "idle.txt").write_text("\n---\n", encoding="utf-8")
    monkeypatch.setattr(sprites, "sprite_root", lambda: tmp_path)

    assert load_frames(Variant.DEFAULT, LifeStage.CHILD, AnimationKey.IDLE) == PLACEHOLDER
    assert load_frames(Variant.DEFAULT, LifeStage.TEEN, AnimationKey.IDLE) == PLACEHOLDER
