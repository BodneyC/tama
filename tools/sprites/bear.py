"""The ``bear`` species: a chunky cub with round ears, a pale muzzle and a button nose.

Edit the grids or palettes here, then run ``uv run python -m tools.sprites.generate``.
See ``kit.py`` for the shared pixel vocabulary. Here ``c`` is both the muzzle (so the kit can
open the mouth into it) and the belly. Other bear pixels: ``p`` inner ears, ``n`` nose,
``i``/``y`` the good adult's bow tie, ``a`` dirt.
"""

from tools.sprites.kit import Collection, Colour, Grid, Palette, chubby, grid, paste, set_pixels
from tools.sprites.species import Look, Species, build_species

NAME = "bear"
MODULE = "bear"

# --- Palettes: Colour(dark-theme value, light-theme value) --------------------------------------

PALETTE: Palette = {
    "k": Colour("#6b4430", "#3a2416", note="outline"),
    "b": Colour("#d4945a", "#c4844a", note="fur"),
    "h": Colour("#e8b582", "#dba46c", note="highlight"),
    "c": Colour("#f3dcbc", "#ecd0a8", note="muzzle and belly"),
    "p": Colour("#c27a62", "#b0654c", note="inner ears"),
    "r": Colour("#ec8f80", "#dc7262", note="cheeks"),
    "n": Colour("#3a2418", note="nose"),
    "e": Colour("#2b1a10", note="eyes"),
    "m": Colour("#4a2a1c", note="mouth"),
    "x": Colour("#fff7c2", "#9a6a00", note="sparkle / evolve flash"),
    "w": Colour("#f2f2f2", "#fafafa", note="white brows and muzzle (elders)"),
    "i": Colour("#e0605a", "#c8403a", note="bow tie (good adults)"),
    "y": Colour("#f1c232", "#d4a017", note="bow tie knot"),
    "a": Colour("#8b6b4a", "#7a5a3a", shade="light", note="dirt (scruffy adults)"),
    "o": Colour("#8a7560", "#5b4a3a", note="egg outline and cracks"),
    "l": Colour("#f4efe3", "#fffaf0", note="egg shell"),
    "s": Colour("#e8b14a", "#c98f1a", shade="medium", note="honey-coloured egg spots"),
    "j": Colour("#6e6e6e", "#4a4a4a", note="gravestone outline"),
    "g": Colour("#a9a9a9", "#9a9a9a", note="stone"),
    "q": Colour("#a9a9a9", "#9a9a9a", shade="light", note="weathered stone"),
    "t": Colour("#6b6b6b", "#5a5a5a", note="carved paw print"),
    "f": Colour("#6aa84f", "#3f7a2c", note="grass"),
}

UI: Palette = {
    "accent": Colour("#93c47d", "#38761d", note="dialog borders and titles in forest green"),
}

SICK: Palette = {
    "b": Colour("#b9c98a", "#a3b76c", note="sickly green"),
    "r": Colour("#b9c98a", "#a3b76c", note="no rosy cheeks when ill"),
    "h": Colour("#d6e4b4", "#bfd496", note="pale highlight"),
}
ADULT_BODY: dict[str, Palette] = {
    "good": {"b": Colour("#dca066", "#cc8e52", note="glossy, well-brushed fur")},
    "scruffy": {"b": Colour("#b8875a", "#a87a4e", note="dull, matted fur")},
}
ELDER_BODY: dict[str, Palette] = {
    "default": {"b": Colour("#cfae8c", "#c09c78", note="greying with age")},
    "good": {"b": Colour("#d8b894", "#c8a680", note="greying with age")},
    "scruffy": {"b": Colour("#b89e82", "#ab9076", note="greying with age")},
}

# --- Base grids ---------------------------------------------------------------------------------

EGG = grid("""
.....oooo.....
...oolllloo...
..ollllllllo..
..ollllllllo..
.olllllsslllo.
.olllllsslllo.
.ollllllllllo.
.ollllllllllo.
olsslllllssllo
olsslllllssllo
ollllllllllllo
ollllllllllllo
.ollllssllllo.
.ollllssllllo.
..oolllllloo..
....oooooo....
""")

BABY = grid("""
.kkk....kkk.
kbpbkkkkbpbk
kbhhbbbbbbbk
kbbebbbbebbk
kbbebccbebbk
kbrbcnncbrbk
.kbbcmmcbbk.
.kbbbccbbbk.
..kbbbbbbk..
...kkkkkk...
""")

CHILD = grid("""
.kkk........kkk.
kbppk......kppbk
kbppbkkkkkkbppbk
.kbbhhbbbbbbbbk.
kbbhhbbbbbbbbbbk
kbbbebbbbbbebbbk
kbbbebbccbbebbbk
kbrrbbccccbbrrbk
kbbbbbcnncbbbbbk
.kbbbbcmmcbbbbk.
.kbbbbbccbbbbbk.
..kkkkkkkkkkkk..
...kbbk..kbbk...
...kkkk..kkkk...
""")

TEEN = grid("""
.kkk..........kkk.
kbppk........kppbk
kbppbkkkkkkkkbppbk
.kbbhhbbbbbbbbbbk.
kbbhhbbbbbbbbbbbbk
kbbbbbbbbbbbbbbbbk
kbbbbebbbbbbebbbbk
kbbbbebbccbbebbbbk
kbbrrbbccccbbrrbbk
kbbbbbbcnncbbbbbbk
kbbbbbbcmmcbbbbbbk
.kbbbbbbccbbbbbbk.
.kbbbccccccccbbbk.
..kkkkkkkkkkkkkk..
...kbbk....kbbk...
...kkkk....kkkk...
""")

ADULT = grid("""
.kkkk............kkkk.
kbppbk..........kbppbk
kbpppbkkkkkkkkkkbpppbk
.kbbbbbbbbbbbbbbbbbbk.
.kbhhbbbbbbbbbbbbbbbk.
kbhhbbbbbbbbbbbbbbbbbk
kbbbbebbbbbbbbbbebbbbk
kbbbbebbbbccbbbbebbbbk
kbbrrbbbbccccbbbbrrbbk
kbbbbbbbbcnncbbbbbbbbk
kkbbbbbbbcmmcbbbbbbbkk
kbkbbbccccccccccbbbkbk
.k.kbbccccccccccbbk.k.
...kkkkkkkkkkkkkkkk...
....kbbk......kbbk....
....kkkk......kkkk....
""")

ELDER = grid("""
.kkkk............kkkk.
kbppbk..........kbppbk
kbpppbkkkkkkkkkkbpppbk
.kbbbbbbbbbbbbbbbbbbk.
.kbhhbbbbbbbbbbbbbbbk.
kbhhbwwbbbbbbbbwwbbbbk
kbbbbebbbbbbbbbbebbbbk
kbbbbbbbbbwwbbbbbbbbbk
kbbrrbbbbwwwwbbbbrrbbk
kbbbbbbbbwnnwbbbbbbbbk
kkbbbbbbbwmmwbbbbbbbkk
kbkbbbccccccccccbbbkbk
.k.kbbccccccccccbbk.k.
...kkkkkkkkkkkkkkkk...
....kbbk......kbbk....
....kkkk......kkkk....
""")

GRAVESTONE = grid("""
.....jjjjjj.....
...jjggggggjj...
..jggggggggggj..
..jggtggggtggj..
..jgtggggggtgj..
..jggggttggggj..
..jgggttttgggj..
..jgggttttgggj..
..jqqggttggqqj..
..jqqggggggqqj..
..jggggggggggj..
..jjjjjjjjjjjj..
.ffffffffffffff.
ffffffffffffffff
""")


def bow_tie(g: Grid) -> Grid:
    """A well-raised bear wears a red bow tie (below the mouth, so it can still open)."""
    return paste(g, 11, 8, grid("ii..ii\niiyyii"))


def scruffy(g: Grid) -> Grid:
    """A poorly-raised bear: stray hairs, a nibbled ear, and a dirty belly."""
    g = paste(g, 0, 9, grid("k..k\n.kk."))
    g = set_pixels(g, [(0, 18, "."), (0, 19, "."), (1, 18, "k"), (1, 19, "k")])
    return paste(g, 11, 6, grid("aa\naa"))


def plump(g: Grid) -> Grid:
    """A chubby bear: fuller cheeks and belly, its snout the same size."""
    return chubby(g, at=8)


VARIANT_LOOKS: dict[str, Look] = {"good": bow_tie, "scruffy": scruffy, "chubby": plump}

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
    front="bemrhcniyw",  # the nose, bow tie and an elder's white muzzle too
)


def build() -> Collection:
    """Every file for this species, relative to ``sprites/bear/``."""
    return build_species(SPECIES)
