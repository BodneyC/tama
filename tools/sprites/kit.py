"""Toolkit for generating a species' pixel art (ADR 0003, 0004).

A species module draws one base grid per stage and calls ``living()`` etc. to derive every
animation. The transformations rely on a shared **pixel vocabulary**, so a new species should
use these characters for the same roles (palettes are per species, so colours are free):

=====  =====================================  =====  ===================================
``k``  outline (also closed eyes, frowns)     ``e``  eyes (pupils; moved, closed, squinted)
``b``  body (what eyes/mouth are drawn into)  ``m``  mouth (opened when eating)
``h``  highlight (eyes may sit in it too)     ``c``  belly
``r``  cheeks                                 ``x``  sparkle / evolve flash
``o``  egg outline (and cracks)               ``l``  egg shell
=====  =====================================  =====  ===================================

Other characters are free for species-specific details (crowns, tufts, feathers...).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

Grid = tuple[str, ...]


@dataclass(frozen=True)
class Colour:
    """A palette colour: dark- and light-theme values, optional shade, and a note."""

    dark: str
    light: str | None = None
    shade: str | None = None
    note: str = ""

    def toml(self) -> str:
        """The TOML value: a plain string when both modes match, else an inline table."""
        light = self.light or self.dark
        if light == self.dark and self.shade is None:
            return f'"{self.dark}"'
        parts = [f'dark = "{self.dark}"', f'light = "{light}"']
        if self.shade:
            parts.append(f'shade = "{self.shade}"')
        return "{ " + ", ".join(parts) + " }"


Palette = dict[str, Colour]


# --- Grids --------------------------------------------------------------------------------------


def grid(text: str) -> Grid:
    """Parse a triple-quoted grid, checking it is rectangular."""
    rows = tuple(text.strip("\n").split("\n"))
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise ValueError(f"ragged grid: {[len(r) for r in rows]}")
    return rows


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


def chubby(g: Grid, extra: int = 2, *, keep: str = "ehmn", at: int | None = None) -> Grid:
    """A rounder body: widen ``g`` by ``extra`` pixels each side of its middle.

    Repeats a pair of mirrored columns: column ``at`` and its mirror if given, else the pair
    nearest the centre that holds none of ``keep`` (eyes, highlights, mouth, nose), so the face,
    belly and stance all widen while the features keep their shape.
    """
    width = len(g[0])
    lefts = [at] if at is not None else [(width - 1) // 2 - i for i in range(width // 2)]
    for left in lefts:
        right = width - 1 - left
        if at is None and any(row[left] in keep or row[right] in keep for row in g):
            continue
        return tuple(
            row[:left]
            + row[left] * extra
            + row[left : right + 1]
            + row[right] * extra
            + row[right + 1 :]
            for row in g
        )
    raise ValueError("no plain columns to widen")


def set_pixels(g: Grid, pixels: Iterable[tuple[int, int, str]]) -> Grid:
    """Set individual pixels (row, col, char)."""
    rows = [list(row) for row in g]
    for y, x, char in pixels:
        rows[y][x] = char
    return tuple("".join(row) for row in rows)


# --- Transformations ----------------------------------------------------------------------------


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


def _around(g: Grid, y: int, x: int, side: int) -> str:
    """What an eye pixel sits in (body ``b`` or, e.g. for an owl's iris, ``h``), from ``side``."""
    pixel = g[y][x + side]
    return pixel if pixel in "bh" else "b"


def _eye_line(g: Grid, *, at_top: bool) -> Grid:
    """Replace each eye with a two-pixel horizontal line at its top or bottom pixel."""
    changes: list[tuple[int, int, str]] = []
    for run in eye_runs(g):
        changes += [(y, x, _around(g, y, x, -1)) for y, x in run]
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
    vacated = [(y, x, _around(g, y, x, -dx)) for y, x in moves]
    return set_pixels(g, vacated + [(y, x + dx, "e") for y, x in moves])


def brows_angry(g: Grid) -> Grid:
    """Scowl: a brow over each eye, high on the outside and low towards the middle."""
    middle = len(g[0]) / 2
    changes: list[tuple[int, int, str]] = []
    for run in eye_runs(g):
        y, x = run[0]
        outward = -1 if x < middle else 1
        # Drawn like the eyes so they stand out (and show as gaps in monochrome, as eyes do).
        for by, bx in ((y - 2, x + outward), (y - 1, x), (y - 1, x - outward)):
            if by >= 0 and g[by][bx] in "bhu":
                changes.append((by, bx, "e"))
    return set_pixels(g, changes)


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


def narrow(g: Grid, by: int = 2) -> Grid:
    """Seen half-turned: drop ``by`` columns each side of the middle, then re-centre."""
    width = len(g[0])
    left = width // 2 - by
    rows = tuple(row[:left] + row[left + 2 * by :] for row in g)
    return paste(("." * width,) * len(g), 0, by, rows)


FRONT = "bemrhc"
"""Pixels seen only from the front by default: body, eyes, mouth, cheeks, highlight, belly."""


def back_view(g: Grid, skin: str = "b", front: str = FRONT) -> Grid:
    """From behind: every ``front`` pixel (face, belly, ...) becomes ``skin``."""
    return tuple("".join(skin if p in front else p for p in row) for row in g)


def eye_top(g: Grid) -> int:
    """The highest row any eye pixel is on (``g`` must have its eyes open)."""
    runs = eye_runs(g)
    if not runs:
        raise ValueError("no eyes to find")
    return min(run[0][0] for run in runs)


def _right_edge(g: Grid, y: int) -> int:
    """The column of the last opaque pixel in row ``y``."""
    return max(x for x, p in enumerate(g[y]) if p != ".")


PAW = grid("""
.k.
kbk
kbk
.k.
""")


def paw_raised(g: Grid, eyes: int, *, high: bool, limb: str = "b") -> Grid:
    """A paw held up beside the body, level with the eyes on row ``eyes`` (``high``) or lower.

    Its left column sits on the body's outline so it looks attached; ``g`` needs two columns
    of margin on the right (a stage canvas has them).
    """
    top = max(0, eyes - (2 if high else 0))
    paw = tuple(row.replace("b", limb) for row in PAW)
    return paste(g, top, _right_edge(g, min(len(g) - 1, top + 2)), paw)


def bowed(g: Grid, eyes: int, depth: int) -> Grid:
    """The head dipped by ``depth`` rows: rows just above the eyes (row ``eyes``) are dropped.

    Feet stay planted; only the top of the head comes down, which reads as a bow or a nod.
    """
    cut = max(1, eyes - depth)
    return ("." * len(g[0]),) * depth + g[:cut] + g[cut + depth :]


def crack(g: Grid, row: int) -> Grid:
    """A zig-zag crack across the egg shell at ``row``."""
    return set_pixels(
        g,
        [
            (row + (i % 2), x, "o")
            for i, x in enumerate(range(len(g[0])))
            if g[row + (i % 2)][x] == "l"
        ],
    )


# --- Animations ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Anim:
    """One animation file: frames, timing, and palette overrides for this file only."""

    frames: tuple[Grid, ...]
    fps: float
    overrides: Palette = field(default_factory=dict)
    loop: bool = field(default=True, kw_only=True)


@dataclass(frozen=True)
class Stage:
    """A base grid on its canvas, with the palette overrides every animation of it uses."""

    base: Grid
    canvas: tuple[int, int]
    overrides: Palette = field(default_factory=dict)
    skin: str = "b"
    """What the pet looks like from behind (a trick spins it round)."""
    front: str = FRONT
    """Pixels hidden (drawn as ``skin``) when it is seen from behind."""
    limb: str = "b"
    """What a raised paw (or wing) is drawn in."""

    def on_canvas(self, g: Grid) -> Grid:
        """Place a grid the size of ``base`` onto this stage's canvas."""
        return place(g, *self.canvas)


def canvas_for(*grids: Grid) -> tuple[int, int]:
    """A canvas fitting every grid with 2 columns of margin each side and 2 rows above."""
    return max(len(g[0]) for g in grids) + 4, max(len(g) for g in grids) + 2


def living(stage: Stage, *, sick: Palette, hatch_from: Grid | None = None) -> dict[str, Anim]:
    """Every animation of a living stage.

    Args:
        stage: The stage's base grid, canvas and palette overrides.
        sick: Palette overrides for the ``sick`` loop (e.g. greener skin).
        hatch_from: The egg grid, for the stage that hatches; other stages get ``evolve``.
    """
    o, c, base = stage.overrides, stage.on_canvas, stage.base

    def frames(*grids: Grid) -> tuple[Grid, ...]:
        return tuple(c(g) for g in grids)

    def up(g: Grid, n: int = 1) -> Grid:
        return shift(c(g), dy=-n)

    happy = eyes_happy(base)
    closed = eyes_closed(base)
    angry = brows_angry(base)
    anims = {
        "idle": Anim((c(base), up(base)), 1.25, o),
        "blink": Anim(frames(closed), 6, o, loop=False),
        "eat": Anim(frames(mouth_open(base), base, mouth_open(base), base), 4, o, loop=False),
        "happy": Anim((up(happy, 2), c(happy), up(happy, 2), c(happy)), 5, o, loop=False),
        "play": Anim(
            (
                c(eyes_look(base, -1)),
                shift(c(eyes_look(base, -1)), dx=-1),
                c(eyes_look(base, 1)),
                shift(c(eyes_look(base, 1)), dx=1),
            ),
            4,
            o,
            loop=False,
        ),
        "refuse": Anim(
            (*(shift(c(closed), dx=dx) for dx in (-1, 1, -1, 1)), c(base)), 8, o, loop=False
        ),
        "sleep": Anim(frames(closed), 1, o),
        # Poses for the Left/Right game: eyes turned and leaning that way.
        "look_left": Anim((shift(c(eyes_look(base, -1)), dx=-1),), 1, o),
        "look_right": Anim((shift(c(eyes_look(base, 1)), dx=1),), 1, o),
        "sick": Anim(frames(base, closed), 1, {**o, **sick}),
        # A tantrum while misbehaving: scowling, stamping side to side and shouting.
        "misbehave": Anim(
            (
                c(angry),
                shift(c(mouth_open(angry)), dx=-1),
                c(angry),
                shift(c(mouth_open(angry)), dx=1),
            ),
            3,
            o,
        ),
        "clean": Anim(
            (sparkles(c(base), 0), sparkles(c(base), 1), sparkles(c(base), 0), c(base)),
            4,
            o,
            loop=False,
        ),
    }
    if hatch_from is None:
        anims["evolve"] = Anim(
            frames(flash(base), base, flash(base), base, flash(base), base), 6, o, loop=False
        )
        anims |= tricks(stage)  # from CHILD on (SPEC §2.10)
    else:
        anims["hatch"] = hatch(stage, hatch_from)
    return anims


def tricks(stage: Stage) -> dict[str, Anim]:
    """The one-shot tricks a disciplined pet performs: wave, spin, dance and bow (SPEC §2.10)."""
    o, c, base = stage.overrides, stage.on_canvas, stage.base
    happy = eyes_happy(base)
    closed = eyes_closed(base)
    cheer = mouth_open(happy)
    eyes = eye_top(base)
    on_canvas = eye_top(c(base))
    wave = tuple(
        paw_raised(c(happy), on_canvas, high=high, limb=stage.limb) for high in (True, False)
    )
    back = back_view(base, stage.skin, stage.front)

    def bow(depth: int) -> Grid:
        return c(bowed(closed, eyes, depth))

    return {
        "trick_wave": Anim((*wave, *wave, c(happy)), 4, o, loop=False),
        "trick_spin": Anim(
            tuple(
                c(g)
                for g in (
                    base,
                    narrow(base),
                    narrow(back, 1),
                    back,
                    narrow(back, 1),
                    narrow(base),
                    happy,
                )
            ),
            6,
            o,
            loop=False,
        ),
        "trick_dance": Anim(
            (
                shift(c(cheer), dx=-1, dy=-1),
                sparkles(c(happy), 0),
                shift(c(cheer), dx=1, dy=-1),
                sparkles(c(happy), 1),
                shift(c(cheer), dx=-1, dy=-1),
                sparkles(c(happy), 0),
                shift(c(cheer), dx=1, dy=-1),
                c(happy),
            ),
            5,
            o,
            loop=False,
        ),
        "trick_bow": Anim(
            (c(base), bow(1), bow(2), bow(2), bow(1), c(happy)),
            3,
            o,
            loop=False,
        ),
    }


def hatch(baby: Stage, egg: Grid) -> Anim:
    """The egg cracks, splits, and the baby pops out (on the baby's canvas)."""
    width, height = baby.canvas
    whole = place(egg, width, height)
    egg_top = height - len(egg)
    middle = len(egg) // 2
    cracked = crack(whole, egg_top + middle - 1)
    cracked_more = crack(cracked, egg_top + middle - 4)
    popping_up = shift(baby.on_canvas(eyes_happy(baby.base)), dy=-5)
    peeking = paste(popping_up, egg_top + middle, (width - len(egg[0])) // 2, egg[middle:])
    return Anim(
        (
            whole,
            cracked,
            cracked_more,
            peeking,
            shift(baby.on_canvas(eyes_happy(baby.base)), dy=-2),
            baby.on_canvas(baby.base),
        ),
        3,
        baby.overrides,
        loop=False,
    )


def wobble(egg: Grid, canvas: tuple[int, int]) -> Anim:
    """The egg rocking gently from side to side."""
    placed = place(egg, *canvas)
    return Anim(tuple(shift(placed, dx=dx) for dx in (0, 0, 0, -1, 1, -1, 0)), 4)


# --- Output -------------------------------------------------------------------------------------

HEADER = "# Generated by tools/sprites/{module}.py; edit the generator, not this file."


def palette_lines(palette: Mapping[str, Colour], keys: Iterable[str] | None = None) -> str:
    """``key = value  # note`` lines for ``keys`` (default: all), aligned."""
    chosen = list(keys) if keys is not None else list(palette)
    values = {key: palette[key].toml() for key in chosen}
    width = max((len(v) for v in values.values()), default=0)
    lines = []
    for key in chosen:
        note = palette[key].note
        comment = f"  # {note}" if note else ""
        lines.append(f"{key} = {values[key]:<{width}}{comment}".rstrip())
    return "\n".join(lines)


def base_toml(module: str, title: str, palette: Palette, ui: Palette | None = None) -> str:
    """A ``base.toml``: the shared palette and optional UI colour overrides."""
    text = f"# {title}\n{HEADER.format(module=module)}\n\n[palette]\n{palette_lines(palette)}\n"
    if ui:
        text += f"\n[ui]\n{palette_lines(ui)}\n"
    return text


def anim_toml(module: str, title: str, anim: Anim) -> str:
    """An animation file: timing, overrides actually used, and frames."""
    used = {p for frame in anim.frames for row in frame for p in row}
    overrides = [key for key in anim.overrides if key in used]
    frames = "\n\n".join(
        f'[[frames]]\npixels = """\n{chr(10).join(frame)}\n"""' for frame in anim.frames
    )
    text = f"# {title}\n{HEADER.format(module=module)}\n"
    text += f"fps = {anim.fps:g}\nloop = {'true' if anim.loop else 'false'}\n\n"
    if overrides:
        text += f"[palette]\n{palette_lines(anim.overrides, overrides)}\n\n"
    return text + frames + "\n"


@dataclass(frozen=True)
class Collection:
    """Generated files for one directory under ``sprites/`` (a species, or the overlays)."""

    name: str
    files: dict[Path, str]
