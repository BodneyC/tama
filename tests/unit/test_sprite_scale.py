from tama.domain.animation import AnimationKey
from tama.domain.stage import LifeStage, Variant
from tama.ui.colours import Look, Mode
from tama.ui.sprite_scale import halve
from tama.ui.sprites import load_sprite


def test_halving_keeps_one_pixel_features_inside_the_body() -> None:
    rows = (
        "kkkk",
        "kbek",
        "kbbk",
        "kkkk",
    )

    assert halve(rows) == ("be", "bb")  # inside, the rarer body and eye beat the outline


def test_edges_take_the_most_common_colour_or_stay_clear() -> None:
    rows = (
        "..kk",
        ".kbb",
    )

    assert halve(rows) == ("..", ".b")  # one inked pixel of four stays clear; padded to even


def test_odd_sizes_are_padded() -> None:
    assert halve(("kkk",) * 3) == ("kk", "k.")


def test_small_sprites_are_half_the_size() -> None:
    look = Look(Mode.DARK, color=True)
    full = load_sprite("tama", Variant.CHUBBY, LifeStage.ADULT, AnimationKey.IDLE).cells(look)[0]
    small = load_sprite(
        "tama", Variant.CHUBBY, LifeStage.ADULT, AnimationKey.IDLE, small=True
    ).cells(look)[0]

    assert len(small[0]) == len(full[0]) // 2
    assert len(small) <= (len(full) + 1) // 2 + 1
