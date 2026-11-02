---
description: Create or revise a sprite animation (e.g. "/add-sprite child eat")
---

Create or update the sprite animation described by: $ARGUMENTS

- Files live at `src/tama/assets/sprites/<variant>/<stage>/<animation>.txt`. Frames are
  separated by a line containing only `---`. Optional first line: `# fps=<n> loop=<true|false>`.
- Every frame of an animation must have the same width and height. Pad with spaces.
- Keep sprites at most 16 columns × 8 rows. Use only characters that render as single-width
  in common terminal fonts, and avoid emoji inside sprites.
- Keep the character recognisable across stages and give it a clear silhouette.
- After editing, run `uv run pytest tests/unit/test_sprites.py`. If snapshots change, review
  them, then run `uv run pytest tests/ui --snapshot-update`.
