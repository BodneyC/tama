---
description: Create or revise a pixel-art sprite animation (e.g. "/add-sprite child eat")
---

Create or update the pixel-art sprite animation described by: $ARGUMENTS

Sprites are **colour pixel art**, not ASCII. You draw a grid of pixels; the renderer turns each
pair of pixel rows into one terminal row of block characters (see ADR 0003).

## File format

`src/tama/assets/sprites/<variant>/<stage>/<animation>.toml`:

```toml
fps = 2          # frames per second
loop = true      # false = one-shot reaction (eat, refuse, hatch, ...)

[palette]        # one character per colour; "." is always transparent (terminal background)
k = "#2b1d14"                                    # outline
b = "#f4b860"                                    # body
h = "#ffe3a3"                                    # highlight
c = "#e86a6a"                                    # cheeks
s = { color = "#f4b860", shade = "medium" }      # textured body: drawn with a shade glyph

[[frames]]
pixels = """
....kkkkkk....
..kkbbbbbbkk..
.kbbhhbbbbbbk.
.kbkbbbbbbkbk.
kbbcbbbbbbcbbk
kbbbbkkkkbbbbk
.kbbbbbbbbbbk.
..kkkkkkkkkk..
"""

[[frames]]
pixels = """
...
"""
```

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

A shaded entry that shares a cell with a different pixel is drawn as its plain colour.

## Rules

- **Size:** at most 32 pixels wide × 16 pixels tall, i.e. at most 32 columns × 8 terminal rows
  (around 24×16 pixels suits most stages). The pixel height must be **even**; pad with a row
  of `.`.
- **Consistency:** every frame in a file has the same width and height. Pad with `.`.
- **Palette:** every character used in `pixels` must be in `[palette]` (or be `.`). Use hex
  colours only; keep a sprite to about 8 colours. Reuse the character's established palette
  across stages and animations so it stays recognisable.
- **Light and dark terminals:** transparent pixels show the terminal background. Give the pet a
  dark outline and avoid relying on pure black or pure white for anything that must be seen.
- **Silhouette:** the outline should read clearly at a glance; keep idle frames subtle (1–2 pixel
  shifts, blinking eyes) and reactions bold.
- **No colour (NO_COLOR):** in monochrome, light pixels (relative luminance ≥ 0.45) are drawn
  in the default colour and dark ones become gaps. Keep eyes, mouth and outline clearly darker
  than the body (and the body clearly lighter), so features show as holes in the shape.

## Workflow

1. Edit the `.toml` file(s). Required animations per stage are listed in SPEC §5.2.
2. Run `uv run pytest tests/unit/test_sprites.py`: it parses every sprite, checks the palette,
   sizes and frame consistency, and that every required animation exists.
3. Look at the result. Snapshot it, then render to PNG and inspect it (see `docs/TESTING.md`,
   "Reviewing snapshots"):
   `uv run pytest tests/ui/snapshots --snapshot-update`.
4. Only accept snapshot changes you have looked at.
