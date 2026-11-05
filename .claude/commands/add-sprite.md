---
description: Create or revise pixel-art sprites, palettes or a whole species (e.g. "/add-sprite child eat", "/add-sprite owl species")
---

Create or update the pixel-art sprites described by: $ARGUMENTS

Sprites are **colour pixel art** drawn with block characters (ADR 0003). Colours live in
per-species palettes with dark- and light-theme values, and the UI's colours can be themed per
species (ADR 0004).

## Where things live

```
src/tama/assets/ui.toml                                   # default UI colours
src/tama/assets/sprites/<species>/base.toml               # species palette (+ [ui] overrides)
src/tama/assets/sprites/<species>/<variant>/<stage>/<animation>.toml   # frames (+ overrides)
src/tama/assets/sprites/overlays/base.toml, <name>.toml   # Zzz / sick / poop; meal / snack
tools/sprites/kit.py                                      # shared toolkit + pixel vocabulary
tools/sprites/<species>.py                                # one generator per species
tools/sprites/overlays.py, generate.py                    # overlays; the entry point
```

`<variant>` is `default`, `good`, `scruffy` or `chubby` (adults and elders). `<stage>` is `egg` …
`dead`. Every species needs every variant (`test_sprites.py`).
Required animations per stage are in SPEC §5.2 and enforced by `tests/unit/test_sprites.py`:
every living stage has `idle`, `blink`, `eat`, `play`, `happy`, `refuse`, `sleep`, `sick`,
`clean`, `look_left`, `look_right` and `misbehave`; the baby has `hatch` and the others `evolve`;
and from child to elder, the one-shot tricks `trick_wave`, `trick_spin`, `trick_dance` and
`trick_bow` (SPEC §2.10; `kit.tricks()`).

## Colours

Every colour, in palettes and UI colours alike, is either:

```toml
k = "#3b2a20"                                   # same in dark and light themes
c = { dark = "#fff1dc", light = "#f7e1bd" }     # per theme mode
s = { dark = "#7fc8b8", light = "#4fa392", shade = "medium" }   # textured with ▒
```

`color = "..."` inside a table sets both modes; add `dark`/`light` to override one of them.

**`base.toml`**: the species' whole palette, and optionally UI colour overrides:

```toml
[palette]
k = { dark = "#6b4a35", light = "#3b2a20" }   # outline
b = "#f6b26b"                                 # body

[ui]
accent = { dark = "#f6b26b", light = "#b45f06" }
```

**Animation files**: only timing, frames, and any palette **overrides** for that file (same
format), e.g. a sick animation's greener skin:

```toml
fps = 1
loop = true

[palette]
b = { dark = "#c3d69b", light = "#a9c47a" }   # sickly green

[[frames]]
pixels = """
..kkkk..
.kbbbbk.
"""
```

**UI colours** (`[ui]` keys, each becomes the CSS variable `$tama-<key>`): `header-background`,
`header-text`, `stat-good`, `stat-warning`, `stat-bad`, `attention`, `accent`, `lights-off`,
and `piece-player`/`piece-pet` (the board-game pieces).
Defaults are in `assets/ui.toml`; values there may be Textual theme variables (`$panel`,
`$success`, ...) so they follow the active theme. A species overrides only what it wants.

## How pixels become characters

Each terminal cell covers two vertically stacked pixels (top, bottom):

| top / bottom | Glyph | Colours |
| --- | --- | --- |
| transparent / transparent | space | — |
| colour / transparent | `▀` | fg = top |
| transparent / colour | `▄` | fg = bottom |
| same colour / same colour | `█` | fg = colour |
| colour A / colour B | `▀` | fg = A, bg = B |
| same shaded entry / same shaded entry | `░` `▒` `▓` (light / medium / dark) | fg = entry colour |

## Rules

- **Size:** at most 32 × 20 pixels (32 columns × 10 rows). Pixel height must be **even**.
- **Consistency:** every frame in a file is the same size, and every animation of a stage uses
  the same canvas (the kit adds 2 columns each side and 2 rows above), so the pet never jumps.
- **Timing:** loops (`idle`, `sleep`, `sick`, `wobble`) set `loop = true`; reactions set
  `loop = false` and play once.
- **Both themes:** pick each colour for its mode. On dark themes avoid very dark outlines (use a
  lighter brown); on light themes avoid pale fills that disappear (shells, sparkles, white tufts).
- **Monochrome (`NO_COLOR`):** only pixels that contrast with the background are drawn: light
  pixels (luminance ≥ 0.45) on dark themes, dark ones (< 0.45) on light themes, giving line
  art. Keep outline/eyes/mouth clearly dark and bodies clearly light in both modes. A test fails
  if any frame draws nothing in any look.
- **Silhouette:** clear at a glance; idle frames subtle, reactions bold.

## The pixel vocabulary (for generated species)

The kit's transformations assume these roles; keep them when drawing a new species:
`k` outline (closed eyes, frowns), `b` body, `e` eyes, `m` mouth, `h` highlight, `c` belly,
`r` cheeks, `x` sparkle/flash, `o` egg outline/cracks, `l` egg shell. Any other character is
free for species-specific details (crowns, feathers, stripes...). Colours are per species.
Eyes (`e`) must be one pixel wide and sit in `b` or `h`: blinking and glancing fill the eye's
old spot with whatever it sat in, so an owl's golden `h` irises stay intact. The mouth (`m`)
opens downwards into `b`, `c` or `r`, so keep one of those below it (the bear's bow tie sits
lower for this reason).

## Workflows

**Change a colour:** edit the species' palette in `tools/sprites/<species>.py` (or its
`base.toml` if hand-drawn), then regenerate. One file changes for every animation.

**Change a stage's look or an animation:** edit the base grid in `tools/sprites/<species>.py`,
or a recipe in `kit.py` (`living()`, `hatch()`, `wobble()`, transformations), then regenerate.

**Add a species (owl, bear, ...):**
1. Copy `tools/sprites/owl.py` or `bear.py` to `tools/sprites/<species>.py`; set `NAME`, draw
   base grids for every stage (egg → dead) using the pixel vocabulary, and give it a `PALETTE`
   with dark and light values (plus `UI` overrides if it should theme the app). Describe it as
   a `Species` (`tools/sprites/species.py`): sick and per-variant palette overrides, and
   `looks` that redraw good/scruffy adults (owl: scholar's cap; bear: bow tie). `chubby`
   defaults to `kit.chubby()`, which widens the grid by repeating the plain columns nearest the
   centre; override it if that stretches a feature (owl: evens out belly feathers; bear:
   `chubby(g, at=8)` widens the cheeks, not the snout). The tricks need two more pixels:
   `skin`, what its back is drawn in when it spins round, and `limb`, what a raised paw is
   drawn in when it waves (both default to body `b`; the owl turns to `u` feathers and waves a
   `d` wing).
2. Add its `build` to `COLLECTIONS` in `tools/sprites/generate.py`.
3. Regenerate. The tests require every SPEC §5.2 animation for every species directory; update
   `test_shipped_species` in `tests/unit/test_sprites.py`.
4. Snapshot it: `test_species_lineup` picks up every species automatically (dark/light ×
   colour/monochrome); add it to nothing, but review the new snapshots as images.
5. Play it: `tama --new --species <species>`, or `↑`/`↓` on the name prompt (it appears in
   `tama --list-species` as soon as `sprites/<species>/base.toml` exists).

Hand-drawn species are fine too: create `sprites/<species>/` with `base.toml` and files by hand,
and don't add it to the generator (which only rewrites collections it owns).

**Then always:**
1. `uv run python -m tools.sprites.generate` (never hand-edit generated files;
   `test_generated_art_is_up_to_date` fails if they disagree with the generator).
2. `uv run pytest tests/unit/test_sprites.py tests/unit/test_theme.py`.
3. Review: render a contact sheet of every frame from the pixel grids, in both modes, and the
   affected snapshots as images (`docs/TESTING.md`, "Reviewing snapshots"); then
   `uv run pytest -n0 tests/ui/snapshots --snapshot-update` and accept only what you have looked at.
