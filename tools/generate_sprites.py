"""Generate tama's pixel-art sprite set (ADR 0003).

Each stage (and adult/elder variant) has one hand-drawn **base grid**; every animation is derived
from it by small, named transformations (close the eyes, open the mouth, bob, shake, sparkle,
flash, recolour). Editing a base grid or a transformation and re-running this script updates
every animation consistently:

    uv run python tools/generate_sprites.py

The output (``src/tama/assets/sprites/**/*.toml``) is committed; ``tests/unit/test_sprites.py``
fails if it is out of date with this script.

Pixel characters: ``.`` transparent, ``k`` outline, ``b`` body, ``h`` highlight, ``c`` belly,
``r`` cheeks, ``e`` eyes, ``m`` mouth, ``w`` white, ``x`` sparkle/flash, ``y`` gold,
``d`` dirt; the egg uses ``o`` outline, ``w`` shell, ``s`` speckles.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "tama" / "assets" / "sprites"

Grid = tuple[str, ...]
Palette = dict[str, str]  # pixel char -> TOML value (a quoted colour or an inline table)

# --- Palettes --------------------------------------------------------------------------------

PET: Palette = {
    "k": '"#3b2a20"',
    "b": '"#f6b26b"',
    "h": '"#ffe2b8"',
    "c": '"#fff1dc"',
    "r": '"#ef8a8a"',
    "e": '"#2b1d14"',
    "m": '"#3b2a20"',
    "x": '"#fff7c2"',
}
GOOD: Palette = {**PET, "b": '"#ffbe73"', "y": '"#f1c232"'}
SCRUFFY: Palette = {**PET, "b": '"#cf9658"', "d": '{ color = "#8b6b4a", shade = "light" }'}


def elderly(palette: Palette) -> Palette:
    """Fade the body and add white for tufts and brows."""
    faded = {'"#f6b26b"': '"#dcb68c"', '"#ffbe73"': '"#e6c193"', '"#cf9658"': '"#bf9a74"'}
    return {**palette, "b": faded[palette["b"]], "w": '"#f2f2f2"'}


def sickly(palette: Palette) -> Palette:
    """Pale green skin, no rosy cheeks."""
    return {**palette, "b": '"#c3d69b"', "r": '"#c3d69b"', "h": '"#e2ecc9"'}


EGG: Palette = {
    "o": '"#5b4a3a"',
    "w": '"#f4efe3"',
    "s": '{ color = "#7fc8b8", shade = "medium" }',
    "k": '"#5b4a3a"',
}
GRAVE: Palette = {
    "k": '"#4a4a4a"',
    "g": '"#a9a9a9"',
    "s": '{ color = "#a9a9a9", shade = "light" }',
    "d": '"#6b6b6b"',
    "f": '"#6aa84f"',
}

# --- Base grids ------------------------------------------------------------------------------


def grid(text: str) -> Grid:
    """Parse a triple-quoted grid, checking it is rectangular."""
    rows = tuple(text.strip("\n").split("\n"))
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError(f"ragged grid: {[len(r) for r in rows]}")
    return rows


EGG_GRID = grid("""
.....oooo.....
...oowwwwoo...
..owwwwwwwwo..
..owwwwwwwwo..
.owwwsswwwwwo.
.owwwsswwwwwo.
.owwwwwwwsswo.
.owwwwwwwsswo.
owsswwwwwwwwwo
owsswwwwwwwwwo
owwwwwwsswwwwo
owwwwwwsswwwwo
.owwwwwwwwwwo.
.owwwwwwwwwwo.
..oowwwwwwoo..
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
.....kkkkkk.....
...kkggggggkk...
..kggggddggggk..
..kggggddggggk..
..kggddddddggk..
..kggddddddggk..
..kggggddggggk..
..kggggddggggk..
..kssggggggssk..
..kssggggggssk..
..kggggggggggk..
..kkkkkkkkkkkk..
.ffffffffffffff.
ffffffffffffffff
""")

# --- Grid transformations --------------------------------------------------------------------


def paste(base: Grid, top: int, left: int, sprite: Grid) -> Grid:
    """Draw ``sprite``'s opaque pixels onto ``base`` at (top, left)."""
    rows = [list(row) for row in base]
    for y, row in enumerate(sprite):
        for x, pixel in enumerate(row):
            if pixel != "." and 0 <= top + y < len(rows) and 0 <= left + x < len(rows[0]):
                rows[top + y][left + x] = pixel
    return tuple("".join(row) for row in rows)


def place(sprite: Grid, width: int, height: int) -> Grid:
    """Put ``sprite`` bottom-centred on a transparent canvas."""
    blank = ("." * width,) * height
    return paste(blank, height - len(sprite), (width - len(sprite[0])) // 2, sprite)


def shift(g: Grid, dx: int = 0, dy: int = 0) -> Grid:
    """Move every pixel right by ``dx`` and down by ``dy`` (clipping at the edges)."""
    return paste(("." * len(g[0]),) * len(g), dy, dx, g)


def recolour(g: Grid, mapping: dict[str, str]) -> Grid:
    """Replace pixel characters."""
    return tuple("".join(mapping.get(p, p) for p in row) for row in g)


def eye_runs(g: Grid) -> list[list[tuple[int, int]]]:
    """Vertical runs of eye pixels, as lists of (row, col) from top to bottom."""
    runs: list[list[tuple[int, int]]] = []
    for x in range(len(g[0])):
        run: list[tuple[int, int]] = []
        for y in range(len(g) + 1):
            if y < len(g) and g[y][x] == "e":
                run.append((y, x))
            elif run:
                runs.append(run)
                run = []
    return runs


def set_pixels(g: Grid, pixels: Iterable[tuple[int, int, str]]) -> Grid:
    """Set individual pixels (row, col, char)."""
    rows = [list(row) for row in g]
    for y, x, char in pixels:
        rows[y][x] = char
    return tuple("".join(row) for row in rows)


def _eye_line(g: Grid, *, at_top: bool) -> Grid:
    """Replace each eye with a two-pixel horizontal line at its top or bottom pixel."""
    changes: list[tuple[int, int, str]] = []
    for run in eye_runs(g):
        changes += [(y, x, "b") for y, x in run]
        y, x = run[0] if at_top else run[-1]
        changes.append((y, x, "k"))
        if g[y][x + 1] in "bh":
            changes.append((y, x + 1, "k"))
    return set_pixels(g, changes)


def eyes_closed(g: Grid) -> Grid:
    """Close each eye to a short line at its lowest pixel."""
    return _eye_line(g, at_top=False)


def eyes_happy(g: Grid) -> Grid:
    """Squint each eye into a short line at its highest pixel (a smile-y look)."""
    return _eye_line(g, at_top=True)


def eyes_look(g: Grid, dx: int) -> Grid:
    """Move the pupils sideways by ``dx`` where there is body to move into."""
    moves = [(y, x) for run in eye_runs(g) for y, x in run if g[y][x + dx] in "bh"]
    return set_pixels(g, [(y, x, "b") for y, x in moves] + [(y, x + dx, "e") for y, x in moves])


def mouth_open(g: Grid) -> Grid:
    """Drop the jaw: extend each mouth pixel down one row."""
    return set_pixels(
        g,
        [
            (y + 1, x, "m")
            for y, row in enumerate(g)
            for x, p in enumerate(row)
            if p == "m" and y + 1 < len(g) and g[y + 1][x] in "bcr"
        ],
    )


def flash(g: Grid) -> Grid:
    """A bright silhouette."""
    return tuple("".join("." if p == "." else "x" for p in row) for row in g)


def sparkles(g: Grid, phase: int) -> Grid:
    """Twinkles in the canvas margins, alternating between two patterns."""
    h, w = len(g), len(g[0])
    spots = [(0, 1), (1, w - 2), (h // 2, 0), (h // 2 + 1, w - 1)]
    if phase:
        spots = [(1, 0), (0, w - 1), (h // 2 + 2, 1), (h // 2 - 1, w - 2)]
    return set_pixels(g, [(y, x, "x") for y, x in spots if g[y][x] == "."])


def decorate(base: Grid, *, crown: bool = False, scruffy: bool = False) -> Grid:
    """Variant touches for adults and elders: a little crown, or a messy tuft and dirt."""
    if crown:
        base = paste(base, 0, 8, grid("y.yy.y\nyyyyyy"))
    if scruffy:
        base = paste(base, 0, 9, grid("k..k\n.kk."))
        base = paste(base, 0, 17, grid("....\n...."))  # a droopy right ear: no tip
        base = set_pixels(base, [(1, 17, "k"), (1, 18, "k")])
        base = paste(base, 11, 7, grid("dd\ndd"))
    return base


# --- Animation sets --------------------------------------------------------------------------


@dataclass(frozen=True)
class Anim:
    """One animation file: frames plus timing."""

    frames: tuple[Grid, ...]
    fps: float
    palette: Palette
    loop: bool = field(default=True, kw_only=True)


@dataclass(frozen=True)
class Stage:
    """A base grid on its canvas, with its palette."""

    base: Grid
    palette: Palette
    canvas: tuple[int, int]

    def on_canvas(self, g: Grid) -> Grid:
        """Place a grid the size of ``base`` onto this stage's canvas."""
        return place(g, *self.canvas)


def canvas_for(base: Grid, at_least: Grid | None = None) -> tuple[int, int]:
    """Room for 2 columns of margin each side and 2 rows above (for bobbing and sparkles)."""
    width, height = len(base[0]) + 4, len(base) + 2
    if at_least is not None:
        width, height = max(width, len(at_least[0]) + 4), max(height, len(at_least) + 2)
    return width, height


def living(stage: Stage, *, arrival: str) -> dict[str, Anim]:
    """Every animation for a living stage. ``arrival`` is ``hatch`` or ``evolve``."""
    p, c = stage.palette, stage.on_canvas
    base = stage.base

    def frames(*grids: Grid) -> tuple[Grid, ...]:
        return tuple(c(g) for g in grids)

    def up(g: Grid, n: int = 1) -> Grid:
        return shift(c(g), dy=-n)

    anims = {
        "idle": Anim((c(base), up(base)), 1.25, p),
        "blink": Anim(frames(eyes_closed(base)), 6, p, loop=False),
        "eat": Anim(frames(mouth_open(base), base, mouth_open(base), base), 4, p, loop=False),
        "happy": Anim(
            (
                up(eyes_happy(base), 2),
                c(eyes_happy(base)),
                up(eyes_happy(base), 2),
                c(eyes_happy(base)),
            ),
            5,
            p,
            loop=False,
        ),
        "play": Anim(
            (
                c(eyes_look(base, -1)),
                shift(c(eyes_look(base, -1)), dx=-1),
                c(eyes_look(base, 1)),
                shift(c(eyes_look(base, 1)), dx=1),
            ),
            4,
            p,
            loop=False,
        ),
        "refuse": Anim(
            (
                shift(c(eyes_closed(base)), dx=-1),
                shift(c(eyes_closed(base)), dx=1),
                shift(c(eyes_closed(base)), dx=-1),
                shift(c(eyes_closed(base)), dx=1),
                c(base),
            ),
            8,
            p,
            loop=False,
        ),
        "sleep": Anim(frames(eyes_closed(base)), 1, p),
        "sick": Anim(frames(base, eyes_closed(base)), 1, sickly(p)),
        "clean": Anim(
            (sparkles(c(base), 0), sparkles(c(base), 1), sparkles(c(base), 0), c(base)),
            4,
            p,
            loop=False,
        ),
    }
    if arrival == "evolve":
        anims["evolve"] = Anim(
            frames(flash(base), base, flash(base), base, flash(base), base), 6, p, loop=False
        )
    else:
        anims["hatch"] = hatch(stage)
    return anims


def crack(g: Grid, row: int) -> Grid:
    """A zig-zag crack across the shell at ``row``."""
    return set_pixels(
        g,
        [
            (row + (i % 2), x, "k")
            for i, x in enumerate(range(len(g[0])))
            if g[row + (i % 2)][x] == "w"
        ],
    )


def hatch(baby: Stage) -> Anim:
    """Egg wobbles, cracks, splits, and the baby pops out."""
    width, height = baby.canvas
    egg = place(EGG_GRID, width, height)
    egg_top = height - len(EGG_GRID)
    cracked = crack(egg, egg_top + 7)
    cracked_more = crack(cracked, egg_top + 4)
    bottom_half = tuple(EGG_GRID[8:])
    # The baby pops up so its face shows over the bottom half of the shell.
    popping_up = shift(baby.on_canvas(eyes_happy(baby.base)), dy=-5)
    peeking = paste(popping_up, egg_top + 8, (width - len(EGG_GRID[0])) // 2, bottom_half)
    return Anim(
        (
            egg,
            cracked,
            cracked_more,
            peeking,
            shift(baby.on_canvas(eyes_happy(baby.base)), dy=-2),
            baby.on_canvas(baby.base),
        ),
        3,
        {**baby.palette, **EGG},
        loop=False,
    )


# --- Overlays --------------------------------------------------------------------------------

OVERLAYS: dict[str, Anim] = {
    "zzz": Anim(
        (grid("zzzz....\n...z....\n..z.zzz.\n.z....z.\nzzzz.z..\n....zzz."),),
        1,
        {"z": '"#9fc5e8"'},
    ),
    "sick": Anim(
        (grid("..wwww..\n.wwwwww.\nwkkwwkkw\nwwwwwwww\n.wwkkww.\n..w.w.w."),),
        1,
        {"w": '"#e8e8e8"', "k": '"#333333"'},
    ),
    "poop": Anim(
        (grid("...pp...\n..pphp..\n..pppp..\n.pphppp.\npppppppp\n.pppppp."),),
        1,
        {"p": '"#8b5a2b"', "h": '"#b07a45"'},
    ),
}

# --- Output ----------------------------------------------------------------------------------


def toml(anim: Anim, title: str) -> str:
    """Serialise an animation as a sprite file."""
    used = sorted({p for frame in anim.frames for row in frame for p in row} - {"."})
    palette = "\n".join(f"{key} = {anim.palette[key]}" for key in used)
    frames = "\n\n".join(
        f'[[frames]]\npixels = """\n{chr(10).join(frame)}\n"""' for frame in anim.frames
    )
    loop = "true" if anim.loop else "false"
    return (
        f"# {title}\n# Generated by tools/generate_sprites.py; edit the generator, not this file.\n"
        f"fps = {anim.fps:g}\nloop = {loop}\n\n[palette]\n{palette}\n\n{frames}\n"
    )


def sprite_set() -> dict[Path, str]:
    """Every generated file, keyed by path relative to the sprites root."""
    files: dict[Path, str] = {}

    def add(variant: str, stage: str, anims: dict[str, Anim]) -> None:
        for name, anim in anims.items():
            files[Path(variant) / stage / f"{name}.toml"] = toml(anim, f"{variant} {stage}: {name}")

    baby = Stage(BABY, PET, canvas_for(BABY, at_least=EGG_GRID))
    egg = Stage(EGG_GRID, EGG, baby.canvas)
    add(
        "default",
        "egg",
        {
            "idle": Anim((egg.on_canvas(EGG_GRID),), 1, EGG),
            "wobble": Anim(
                tuple(shift(egg.on_canvas(EGG_GRID), dx=dx) for dx in (0, 0, 0, -1, 1, -1, 0)),
                4,
                EGG,
            ),
        },
    )
    add("default", "baby", living(baby, arrival="hatch"))
    for name, base in (("child", CHILD), ("teen", TEEN)):
        add("default", name, living(Stage(base, PET, canvas_for(base)), arrival="evolve"))
    variants: dict[str, tuple[Palette, Callable[[Grid], Grid]]] = {
        "default": (PET, lambda g: g),
        "good": (GOOD, lambda g: decorate(g, crown=True)),
        "scruffy": (SCRUFFY, lambda g: decorate(g, scruffy=True)),
    }
    for variant, (palette, touch) in variants.items():
        for name, base, pal in (("adult", ADULT, palette), ("elder", ELDER, elderly(palette))):
            decorated = touch(base)
            add(
                variant,
                name,
                living(Stage(decorated, pal, canvas_for(decorated)), arrival="evolve"),
            )
    grave = Stage(GRAVESTONE, GRAVE, canvas_for(GRAVESTONE))
    add("default", "dead", {"idle": Anim((grave.on_canvas(GRAVESTONE),), 1, GRAVE)})
    for name, anim in OVERLAYS.items():
        files[Path("overlays") / f"{name}.toml"] = toml(anim, f"overlay: {name}")
    return files


def generate(root: Path = ROOT) -> list[Path]:
    """Write every sprite file under ``root``, removing stale generated ones."""
    files = sprite_set()
    for stale in root.rglob("*.toml"):
        if stale.relative_to(root) not in files:
            stale.unlink()
    written = []
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    paths = generate()
    print(f"Wrote {len(paths)} sprite files under {ROOT}")  # noqa: T201 - CLI output
