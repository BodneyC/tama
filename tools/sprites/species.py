"""Assemble a whole species from one base grid per stage (see ``kit.py`` for the recipes).

A species module (``tama.py``, ``owl.py``, ...) draws its grids and palettes, describes them as
a :class:`Species`, and its ``build()`` returns ``build_species(SPECIES)``.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tools.sprites.kit import (
    Anim,
    Collection,
    Grid,
    Palette,
    Stage,
    anim_toml,
    base_toml,
    canvas_for,
    living,
    place,
    wobble,
)

Look = Callable[[Grid], Grid]
"""Redraws an adult or elder grid for one variant (e.g. adds a crown)."""

VARIANTS = ("default", "good", "scruffy")


def _unchanged(g: Grid) -> Grid:
    return g


@dataclass(frozen=True)
class Species:
    """Everything that differs between species; the animations are derived from it.

    Attributes:
        name: Directory name under ``sprites/`` and the name players type (``--species``).
        module: Generator module, named in each file's header.
        palette: Shared palette (``base.toml``).
        ui: UI colour overrides (``base.toml``'s ``[ui]``); empty keeps the defaults.
        sick: Palette overrides for every ``sick`` loop.
        egg, baby, child, teen, adult, elder, gravestone: One base grid per stage.
        adult_body, elder_body: Palette overrides per variant for adults and elders.
        looks: Grid changes per variant for adults and elders (missing = unchanged).
    """

    name: str
    module: str
    palette: Palette
    sick: Palette
    egg: Grid
    baby: Grid
    child: Grid
    teen: Grid
    adult: Grid
    elder: Grid
    gravestone: Grid
    ui: Palette = field(default_factory=dict)
    adult_body: Mapping[str, Palette] = field(default_factory=dict)
    elder_body: Mapping[str, Palette] = field(default_factory=dict)
    looks: Mapping[str, Look] = field(default_factory=dict)


def build_species(species: Species) -> Collection:
    """Every file for ``species``, relative to ``sprites/<name>/``."""
    name, module = species.name, species.module
    files: dict[Path, str] = {
        Path("base.toml"): base_toml(
            module, f"{name}: shared palette and UI colours", species.palette, species.ui
        )
    }

    def add(variant: str, stage: str, anims: dict[str, Anim]) -> None:
        for anim_name, anim in anims.items():
            title = f"{name} {variant} {stage}: {anim_name}"
            files[Path(variant) / stage / f"{anim_name}.toml"] = anim_toml(module, title, anim)

    egg, sick = species.egg, species.sick
    baby_canvas = canvas_for(species.baby, egg)
    add(
        "default",
        "egg",
        {"idle": Anim((place(egg, *baby_canvas),), 1), "wobble": wobble(egg, baby_canvas)},
    )
    add("default", "baby", living(Stage(species.baby, baby_canvas), sick=sick, hatch_from=egg))
    for stage, base in (("child", species.child), ("teen", species.teen)):
        add("default", stage, living(Stage(base, canvas_for(base)), sick=sick))
    for variant in VARIANTS:
        look = species.looks.get(variant, _unchanged)
        for stage, base, body in (
            ("adult", species.adult, species.adult_body),
            ("elder", species.elder, species.elder_body),
        ):
            drawn = look(base)
            overrides = body.get(variant, {})
            add(variant, stage, living(Stage(drawn, canvas_for(drawn), overrides), sick=sick))
    grave = species.gravestone
    add("default", "dead", {"idle": Anim((place(grave, *canvas_for(grave)),), 1)})
    return Collection(name, files)
