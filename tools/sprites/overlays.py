"""Shared sprites for every species: status indicators (Zzz, sickness, poop, holiday) and food."""

from pathlib import Path

from tools.sprites.kit import Anim, Collection, Colour, Palette, anim_toml, base_toml, grid

NAME = "overlays"
MODULE = "overlays"

PALETTE: Palette = {
    "z": Colour("#9fc5e8", "#2f6fad", note="sleepy Zs"),
    "w": Colour("#e8e8e8", "#4d4d4d", note="skull"),
    "k": Colour("#333333", "#f5f5f5", note="skull eyes, nose and teeth"),
    "p": Colour("#a0703f", "#7a4f25", note="poop"),
    "h": Colour("#c99560", "#a0703f", note="poop highlight"),
    "q": Colour("#d9d9d9", "#9a9a9a", shade="light", note="steam"),
    "i": Colour("#fbf6e9", "#efe4c8", note="rice"),
    "u": Colour("#d0605c", "#a83a37", note="bowl"),
    "v": Colour("#f2d16b", "#c99a1a", note="bowl band"),
    "f": Colour("#f7a8c8", "#e57fa8", note="frosting"),
    "r": Colour("#d62d3a", "#c0202d", note="cherry"),
    "c": Colour("#7fb3e0", "#3f78b0", note="cupcake case"),
    "m": Colour("#cfe3f5", "#a9c9e8", note="case stripes"),
    "x": Colour("#fff7c2", "#9a6a00", note="sparkle"),
    "a": Colour("#c0823e", "#8f5a24", note="suitcase"),
    "g": Colour("#6b4423", "#4a2c14", note="suitcase handle and straps"),
    "l": Colour("#f2d16b", "#c99a1a", note="suitcase latches"),
}

BOWL = "\n.iiiiiiii.\nuuuuuuuuuu\n.uvvvvvvu.\n..uuuuuu..\n...uuuu..."
CUPCAKE = "\n....rr....\n...ffff...\n..ffffff..\n.ffffffff.\n..cmcmcm..\n..mcmcmc..\n...cmcm..."
FOOD: dict[str, Anim] = {
    "meal": Anim(
        (
            grid("..q....q..\n...q....q.\n..q....q.." + BOWL),
            grid("...q....q.\n..q....q..\n...q....q." + BOWL),
        ),
        2,
    ),
    "snack": Anim((grid("x........." + CUPCAKE), grid(".........x" + CUPCAKE)), 2),
}

OVERLAYS: dict[str, Anim] = {
    "zzz": Anim((grid("zzzz....\n...z....\n..z.zzz.\n.z....z.\nzzzz.z..\n....zzz."),), 1),
    "sick": Anim((grid("..wwww..\n.wwwwww.\nwkkwwkkw\nwwwwwwww\n.wwkkww.\n..w.w.w."),), 1),
    "suitcase": Anim((grid("..gggg..\n..g..g..\naaaaaaaa\nagaaaaga\nagallaga\naaaaaaaa"),), 1),
    "poop": Anim((grid("...pp...\n..pphp..\n..pppp..\n.pphppp.\npppppppp\n.pppppp."),), 1),
}


def build() -> Collection:
    """Every overlay file, relative to ``sprites/overlays/``."""
    files = {Path("base.toml"): base_toml(MODULE, "status overlays: shared palette", PALETTE)}
    for name, anim in (OVERLAYS | FOOD).items():
        files[Path(f"{name}.toml")] = anim_toml(MODULE, f"overlay: {name}", anim)
    return Collection(NAME, files)
