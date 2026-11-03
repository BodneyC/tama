"""The ``owl`` species: ear tufts, a pale facial disc, a little beak and a speckled belly.

Edit the grids or palettes here, then run ``uv run python -m tools.sprites.generate``.
See ``kit.py`` for the shared pixel vocabulary. Here ``b`` is the facial disc (where the eyes
and beak sit, so the kit can blink and open them) and ``u`` the feathers around it. Other
owl pixels: ``d`` wing feathers, ``v`` belly speckles, ``t`` talons, ``z``/``y`` the good
adult's cap and tassel, ``a`` dirt.
"""

from tools.sprites.kit import Collection, Colour, Grid, Palette, grid, paste, set_pixels
from tools.sprites.species import Look, Species, build_species

NAME = "owl"
MODULE = "owl"

# --- Palettes: Colour(dark-theme value, light-theme value) --------------------------------------

PALETTE: Palette = {
    "k": Colour("#6a5038", "#33261a", note="outline"),
    "u": Colour("#c9935a", "#b98348", note="feathers"),
    "d": Colour("#9a6a3c", "#7e5530", note="wing feathers"),
    "b": Colour("#f3e3c3", "#ecd6a8", note="facial disc"),
    "h": Colour("#f2c14e", "#e0a82a", note="golden irises (the kit treats h like body)"),
    "c": Colour("#f8ecd4", "#f1dfbc", note="belly"),
    "v": Colour("#a8774a", "#8a5e33", note="belly speckles"),
    "e": Colour("#24170d", note="eyes"),
    "m": Colour("#a8682a", "#8f5420", note="beak"),
    "t": Colour("#e8a33a", "#c98618", note="talons"),
    "x": Colour("#fff7c2", "#9a6a00", note="sparkle / evolve flash"),
    "w": Colour("#f2f2f2", "#fafafa", note="white tufts and brows (elders)"),
    "z": Colour("#4a5a9a", "#2b3560", note="scholar's cap (good adults)"),
    "y": Colour("#f1c232", "#d4a017", note="cap tassel"),
    "a": Colour("#8b6b4a", "#7a5a3a", shade="light", note="dirt (scruffy adults)"),
    "o": Colour("#8a7560", "#5b4a3a", note="egg outline and cracks"),
    "l": Colour("#f4efe3", "#fffaf0", note="egg shell"),
    "s": Colour("#c49a6c", "#9a6a3a", shade="medium", note="egg speckles"),
    "j": Colour("#6e6e6e", "#4a4a4a", note="gravestone outline"),
    "g": Colour("#a9a9a9", "#9a9a9a", note="stone"),
    "q": Colour("#a9a9a9", "#9a9a9a", shade="light", note="weathered stone"),
    "n": Colour("#6b6b6b", "#5a5a5a", note="carved feather"),
    "f": Colour("#6aa84f", "#3f7a2c", note="grass"),
}

UI: Palette = {
    "accent": Colour("#9fa8da", "#3f4a96", note="dialog borders and titles in twilight indigo"),
}

SICK: Palette = {
    "b": Colour("#d6e4b4", "#bfd496", note="pale green face"),
    "u": Colour("#a9b47c", "#909c5e", note="sickly green feathers"),
}
ADULT_BODY: dict[str, Palette] = {
    "good": {"u": Colour("#d9a062", "#c48a48", note="glossy, well-preened feathers")},
    "scruffy": {"u": Colour("#a88660", "#977650", note="dull, ruffled feathers")},
}
ELDER_BODY: dict[str, Palette] = {
    "default": {"u": Colour("#c4a888", "#b09270", note="faded with age")},
    "good": {"u": Colour("#ceb08c", "#bc9a74", note="faded with age")},
    "scruffy": {"u": Colour("#a89478", "#988468", note="faded with age")},
}

# --- Base grids ---------------------------------------------------------------------------------

EGG = grid("""
.....oooo.....
...oolllloo...
..ollllllllo..
..olllllsllo..
.ollslllllllo.
.olllllllsllo.
.ollllllllllo.
.olllsllllllo.
ollllllllslllo
olsllllllllllo
ollllllslllllo
ollllllllllllo
.ollllllllslo.
.olsllllllllo.
..oolllllloo..
....oooooo....
""")

BABY = grid("""
.kk......kk.
.kuk....kuk.
.kuukkkkuuk.
kuhhhuuhhhuk
kbhehbbhehbk
kbhehmmhehbk
kuhhhbbhhhuk
kuuccvvccuuk
.kuccccccuk.
..kkkkkkkk..
""")

CHILD = grid("""
..kk........kk..
..kuk......kuk..
.kuuukkkkkkuuuk.
.kuubbbuubbbuuk.
kuuhhhbbbbhhhuuk
kubhehbbbbhehbuk
kubhehbmmbhehbuk
kuuhhhbmmbhhhuuk
kduuuccccccuuudk
kdduccvccvccuddk
kdduccccccccuddk
.kdducvccvcuddk.
..kkkkkkkkkkkk..
....ttt..ttt....
""")

TEEN = grid("""
.kk............kk.
.kuk..........kuk.
.kuuk........kuuk.
.kuuukkkkkkkkuuuk.
kuuuuuuuuuuuuuuuuk
kuubbbbbuubbbbbuuk
kubbhhhbbbbhhhbbuk
kubbhehbbbbhehbbuk
kubbhehbmmbhehbbuk
kuubhhhbmmbhhhbuuk
kduuuubbbbbbuuuudk
kdduuccccccccuuddk
kdducvccvvccvcuddk
.kdduccccccccuddk.
..kkkkkkkkkkkkkk..
....ttt....ttt....
""")

ADULT = grid("""
.kk..............kk.
.kuk............kuk.
.kuuk..........kuuk.
.kuuukkkkkkkkkkuuuk.
kuuuuuuuuuuuuuuuuuuk
kuubbbbbbuubbbbbbuuk
kubbhhhbbbbbbhhhbbuk
kubbhehbbbbbbhehbbuk
kubbhehbbmmbbhehbbuk
kuubhhhbbmmbbhhhbuuk
kduuuubbbbbbbbuuuudk
kdduuccccccccccuuddk
kdducvccvccvccvcuddk
.kdduccvccccvccuddk.
..kkkkkkkkkkkkkkkk..
.....ttt....ttt.....
""")

ELDER = grid("""
.ww..............ww.
.kwk............kwk.
.kuuk..........kuuk.
.kuuukkkkkkkkkkuuuk.
kuuuuuuuuuuuuuuuuuuk
kuubwwwbbuubbwwwbuuk
kubbhhhbbbbbbhhhbbuk
kubbhehbbmmbbhehbbuk
kubbhhhbbmmbbhhhbbuk
kuubbbbbbbbbbbbbbuuk
kduuuubbbbbbbbuuuudk
kdduuccccccccccuuddk
kdducvccvccvccvcuddk
.kdduccvccccvccuddk.
..kkkkkkkkkkkkkkkk..
.....ttt....ttt.....
""")

GRAVESTONE = grid("""
.....jjjjjj.....
...jjggggggjj...
..jggggggnnggj..
..jgggggnnnggj..
..jggggnnngggj..
..jgggnnnngggj..
..jggnnngggggj..
..jgnngggggggj..
..jqqggggggqqj..
..jqqggggggqqj..
..jggggggggggj..
..jjjjjjjjjjjj..
.ffffffffffffff.
ffffffffffffffff
""")


def capped(g: Grid) -> Grid:
    """A well-raised owl wears a scholar's cap with a gold tassel."""
    return paste(g, 0, 5, grid("....zz....\nzzzzzzzzzz\n..zzzzzz.y"))


def scruffy(g: Grid) -> Grid:
    """A poorly-raised owl: a cowlick, a drooping tuft, and a dirty belly."""
    g = paste(g, 1, 8, grid("k..k\n.kk."))
    g = set_pixels(g, [(0, 17, "."), (0, 18, "."), (1, 17, "k"), (1, 18, "k"), (2, 19, "k")])
    return paste(g, 12, 6, grid("aa\naa"))


VARIANT_LOOKS: dict[str, Look] = {"good": capped, "scruffy": scruffy}

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
    """Every file for this species, relative to ``sprites/owl/``."""
    return build_species(SPECIES)
