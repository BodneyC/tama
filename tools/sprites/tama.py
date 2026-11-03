"""The ``tama`` species: a round, cat-eared critter (the original pet).

Edit the grids or palettes here, then run ``uv run python -m tools.sprites.generate``.
See ``kit.py`` for the shared pixel vocabulary.
"""

from tools.sprites.kit import Collection, Colour, Grid, Palette, grid, paste, set_pixels
from tools.sprites.species import Look, Species, build_species

NAME = "tama"
MODULE = "tama"

# --- Palettes: Colour(dark-theme value, light-theme value) --------------------------------------

PALETTE: Palette = {
    "k": Colour("#6b4a35", "#3b2a20", note="outline"),
    "b": Colour("#f6b26b", note="body"),
    "h": Colour("#ffe2b8", "#ffd49a", note="highlight"),
    "c": Colour("#fff1dc", "#f7e1bd", note="belly"),
    "r": Colour("#ef8a8a", "#e06c6c", note="cheeks"),
    "e": Colour("#2b1d14", note="eyes"),
    "m": Colour("#3b2a20", note="mouth"),
    "x": Colour("#fff7c2", "#9a6a00", note="sparkle / evolve flash"),
    "w": Colour("#f2f2f2", "#fafafa", note="white tufts and brows (elders)"),
    "y": Colour("#f1c232", "#d4a017", note="gold crown (good adults)"),
    "d": Colour("#8b6b4a", "#7a5a3a", shade="light", note="dirt (scruffy adults)"),
    "o": Colour("#8a7560", "#5b4a3a", note="egg outline and cracks"),
    "l": Colour("#f4efe3", "#fffaf0", note="egg shell"),
    "s": Colour("#7fc8b8", "#4fa392", shade="medium", note="egg speckles"),
    "j": Colour("#6e6e6e", "#4a4a4a", note="gravestone outline"),
    "g": Colour("#a9a9a9", "#9a9a9a", note="stone"),
    "q": Colour("#a9a9a9", "#9a9a9a", shade="light", note="weathered stone"),
    "n": Colour("#6b6b6b", "#5a5a5a", note="carved cross"),
    "f": Colour("#6aa84f", "#3f7a2c", note="grass"),
}

UI: Palette = {
    "accent": Colour("#f6b26b", "#b45f06", note="dialog borders and titles in tama orange"),
}

SICK: Palette = {
    "b": Colour("#c3d69b", "#a9c47a", note="sickly green"),
    "r": Colour("#c3d69b", "#a9c47a", note="no rosy cheeks when ill"),
    "h": Colour("#e2ecc9", "#cfe0a8", note="pale highlight"),
}
ADULT_BODY: dict[str, Palette] = {
    "default": {},
    "good": {"b": Colour("#ffbe73", note="bright, well-groomed body")},
    "scruffy": {"b": Colour("#cf9658", note="dull, unkempt body")},
}
ELDER_BODY: dict[str, Palette] = {
    "default": {"b": Colour("#dcb68c", "#d4a978", note="faded with age")},
    "good": {"b": Colour("#e6c193", "#ddb07a", note="faded with age")},
    "scruffy": {"b": Colour("#bf9a74", "#b08a62", note="faded with age")},
}

# --- Base grids ---------------------------------------------------------------------------------

EGG = grid("""
.....oooo.....
...oolllloo...
..ollllllllo..
..ollllllllo..
.olllsslllllo.
.olllsslllllo.
.olllllllsslo.
.olllllllsslo.
olsslllllllllo
olsslllllllllo
olllllllsslllo
olllllllsslllo
.ollllllllllo.
.ollllllllllo.
..oolllllloo..
....oooooo....
""")

BABY = grid("""
....kkkk....
..kkbbbbkk..
.kbbhhbbbbk.
.kbhhbbbbbk.
kbbebbbbebbk
kbbebbbbebbk
kbrbbbbbbrbk
kbbbbmmbbbbk
.kbbbbbbbbk.
..kkkkkkkk..
""")

CHILD = grid("""
.....kkkkkk.....
...kkbbbbbbkk...
..kbbhhbbbbbbk..
.kbbhhbbbbbbbbk.
.kbbbebbbbebbbk.
kbbbbebbbbebbbbk
kbbrrbbbbbbrrbbk
kbbbbbbmmbbbbbbk
.kbbbbbbbbbbbbk.
.kbbccccccccbbk.
..kbccccccccbk..
...kkkkkkkkkk...
...kbbk..kbbk...
...kkkk..kkkk...
""")

TEEN = grid("""
..kk..........kk..
.kbbk........kbbk.
.kbbbkkkkkkkkbbbk.
..kbbbbbbbbbbbbk..
.kbbhhbbbbbbbbbbk.
.kbhhbbbbbbbbbbbk.
kbbbbebbbbbbebbbbk
kbbbbebbbbbbebbbbk
kbbrrbbbbbbbbrrbbk
kbbbbbbbmmbbbbbbbk
.kbbbbbbbbbbbbbbk.
.kbbbccccccccbbbk.
..kbbccccccccbbk..
...kkkkkkkkkkkk...
...kbbk....kbbk...
...kkkk....kkkk...
""")

ADULT = grid("""
..kk..............kk..
.kbbk............kbbk.
.kbbbkkkkkkkkkkkkbbbk.
..kbbbbbbbbbbbbbbbbk..
.kbbhhbbbbbbbbbbbbbbk.
.kbhhbbbbbbbbbbbbbbbk.
kbbbbbebbbbbbbbebbbbbk
kbbbbbebbbbbbbbebbbbbk
kbbbrrbbbbbbbbbbrrbbbk
kbbbbbbbbbmmbbbbbbbbbk
kkbbbbbbbbbbbbbbbbbbkk
kbkbbbccccccccccbbbkbk
.k.kbbccccccccccbbk.k.
...kkkkkkkkkkkkkkkk...
....kbbk......kbbk....
....kkkk......kkkk....
""")

ELDER = grid("""
..kk..............kk..
.kwwk............kwwk.
.kwwbkkkkkkkkkkkkbwwk.
..kbbbbbbbbbbbbbbbbk..
.kbbhhbbbbbbbbbbbbbbk.
.kbhhbbbbbbbbbbbbbbbk.
kbbbbwwbbbbbbbbwwbbbbk
kbbbbbebbbbbbbbebbbbbk
kbbbrrbbbbbbbbbbrrbbbk
kbbbbbbbbmmmmbbbbbbbbk
kkbbbbbbbbbbbbbbbbbbkk
kbkbbbccccccccccbbbkbk
.k.kbbccccccccccbbk.k.
...kkkkkkkkkkkkkkkk...
....kbbk......kbbk....
....kkkk......kkkk....
""")

GRAVESTONE = grid("""
.....jjjjjj.....
...jjggggggjj...
..jggggnnggggj..
..jggggnnggggj..
..jggnnnnnnggj..
..jggnnnnnnggj..
..jggggnnggggj..
..jggggnnggggj..
..jqqggggggqqj..
..jqqggggggqqj..
..jggggggggggj..
..jjjjjjjjjjjj..
.ffffffffffffff.
ffffffffffffffff
""")


def crowned(g: Grid) -> Grid:
    """A well-raised adult wears a little gold crown."""
    return paste(g, 0, 8, grid("y.yy.y\nyyyyyy"))


def scruffy(g: Grid) -> Grid:
    """A poorly-raised adult: messy tuft, a droopy ear, and a dirty belly."""
    g = paste(g, 0, 9, grid("k..k\n.kk."))
    g = paste(g, 0, 17, grid("....\n...."))
    g = set_pixels(g, [(1, 17, "k"), (1, 18, "k")])
    return paste(g, 11, 7, grid("dd\ndd"))


VARIANT_LOOKS: dict[str, Look] = {
    "good": crowned,
    "scruffy": scruffy,
}

# --- Assembly -----------------------------------------------------------------------------------

SPECIES = Species(
    name=NAME,
    module=MODULE,
    palette=PALETTE,
    ui=UI,
    sick=SICK,
    egg=EGG,
    baby=BABY,
    child=CHILD,
    teen=TEEN,
    adult=ADULT,
    elder=ELDER,
    gravestone=GRAVESTONE,
    adult_body=ADULT_BODY,
    elder_body=ELDER_BODY,
    looks=VARIANT_LOOKS,
)


def build() -> Collection:
    """Every file for this species, relative to ``sprites/tama/``."""
    return build_species(SPECIES)
