# ADR 0003: Colour pixel-art sprites rendered with block characters

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

M4 shipped single-frame ASCII sprites (`.txt` files of characters like `( o o )`). They are
legible but don't look like a virtual pet. The goal is pixel art: chunky, coloured, built from
the full, half and shaded block characters (`█ ▀ ▄ ░ ▒ ▓`).

Drawing directly in block glyphs plus separate colour layers is error-prone: the artist has to
think in half-cells and keep three grids in sync.

## Decision

- Sprites are authored as **pixel grids** in TOML (`<variant>/<stage>/<animation>.toml`):
  one character per pixel, a `[palette]` mapping characters to hex colours, `.` for
  transparent, plus `fps` and `loop`.
- The renderer composes **two pixel rows per terminal row** using `▀`/`▄`/`█`/space with
  foreground/background colours. This gives roughly square pixels and double vertical resolution.
- Palette entries may set `shade = "light" | "medium" | "dark"`; a cell whose two pixels are the
  same shaded entry is drawn with `░`/`▒`/`▓` for texture and dithering.
- Parsing and validation use `tomllib` plus a Pydantic model in `tama.ui.sprites`; rendered
  frames are cached as Textual `Content` (styled strips) per (variant, stage, animation).
- Under `NO_COLOR`, nothing is coloured: pixels lighter than a luminance threshold (0.45) are
  drawn in the default colour and darker ones (outline, eyes, mouth) become gaps, so features
  show as holes in the shape, like an old LCD. Drawing every opaque pixel produced a featureless
  blob.

- The shipped art is produced by `tools/generate_sprites.py` from one base grid per stage
  and variant, so all animations stay consistent. All animations of a stage share one canvas
  (2-column side margins, 2 rows of headroom), which raised the size limit to 32×20 pixels.
- Status indicators (Zzz, sickness, poop) are small pixel sprites too (`sprites/overlays/`).

## Consequences

- Sprites look like pixel art and share one consistent palette per character.
- The renderer is a small, pure function (pixels → cells) that is easy to unit-test.
- The M4 ASCII `.txt` sprites and their loader are replaced in M5; `test_sprites.py` changes
  from "ASCII and ≤ 16×8 characters" to the pixel-format rules (see `/add-sprite`).
- Truecolour looks best; Textual downsamples to 256/16 colours automatically on lesser
  terminals.
