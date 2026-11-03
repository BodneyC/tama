"""Status indicators shown under every species' pet: Zzz, sickness, poop."""

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
}

OVERLAYS: dict[str, Anim] = {
    "zzz": Anim((grid("zzzz....\n...z....\n..z.zzz.\n.z....z.\nzzzz.z..\n....zzz."),), 1),
    "sick": Anim((grid("..wwww..\n.wwwwww.\nwkkwwkkw\nwwwwwwww\n.wwkkww.\n..w.w.w."),), 1),
    "poop": Anim((grid("...pp...\n..pphp..\n..pppp..\n.pphppp.\npppppppp\n.pppppp."),), 1),
}


def build() -> Collection:
    """Every overlay file, relative to ``sprites/overlays/``."""
    files = {Path("base.toml"): base_toml(MODULE, "status overlays: shared palette", PALETTE)}
    for name, anim in OVERLAYS.items():
        files[Path(f"{name}.toml")] = anim_toml(MODULE, f"overlay: {name}", anim)
    return Collection(NAME, files)
