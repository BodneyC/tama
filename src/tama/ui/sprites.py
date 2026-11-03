"""Loading sprite frames from package data (``tama/assets/sprites``).

Layout: ``<variant>/<stage>/<animation>.txt``. Frames within a file are separated by a line
containing only ``---``. Missing art falls back to the default variant, then to the
``idle`` animation, then to a placeholder, so missing art never crashes the game.
"""

from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable

from tama.domain.animation import AnimationKey
from tama.domain.stage import LifeStage, Variant

FRAME_SEPARATOR = "---"
PLACEHOLDER: tuple[str, ...] = ("?",)


def sprite_root() -> Traversable:
    """The directory holding all sprite files."""
    return files("tama.assets") / "sprites"


def parse_frames(text: str) -> tuple[str, ...]:
    """Split a sprite file into frames, dropping trailing whitespace and empty frames."""
    frames: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.strip() == FRAME_SEPARATOR:
            frames.append([])
        else:
            frames[-1].append(line.rstrip())
    return tuple("\n".join(lines) for lines in frames if any(lines))


@cache
def load_frames(variant: Variant, stage: LifeStage, animation: AnimationKey) -> tuple[str, ...]:
    """Return the frames for an animation, falling back as described in the module docstring."""
    candidates = (
        (variant, animation),
        (Variant.DEFAULT, animation),
        (variant, AnimationKey.IDLE),
        (Variant.DEFAULT, AnimationKey.IDLE),
    )
    for candidate_variant, candidate_animation in candidates:
        resource = sprite_root() / candidate_variant / stage / f"{candidate_animation}.txt"
        if resource.is_file():
            frames = parse_frames(resource.read_text(encoding="utf-8"))
            if frames:
                return frames
    return PLACEHOLDER
