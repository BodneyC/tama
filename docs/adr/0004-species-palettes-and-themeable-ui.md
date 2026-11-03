# ADR 0004: Per-species base palettes, dark/light colours, and themeable UI colours

- **Status:** Accepted (amends ADR 0003)
- **Date:** 2026-11-03

## Context

ADR 0003 stored a full palette in every animation file, with a single colour per entry. That
caused three problems:

- **Duplication:** changing one colour meant editing ~90 files, or the generator.
- **Light themes:** colours chosen for dark terminals (pale shells, light sparkles, dark
  outlines) either vanish or lose contrast on light ones.
- **Fixed UI colours:** the UI used fixed Textual theme colours, so a species couldn't give
  the app its own feel.

We also want differently shaped species (an owl, a bear, ...). A single generator script with
one creature's grids hard-coded doesn't scale to that.

## Decision

**Layout.** Sprites are grouped by species:

```
src/tama/assets/ui.toml                                  # default UI colours
src/tama/assets/sprites/<species>/base.toml              # [palette] (+ optional [ui])
src/tama/assets/sprites/<species>/<variant>/<stage>/<animation>.toml
src/tama/assets/sprites/overlays/base.toml, <name>.toml  # status indicators, same scheme
```

**Colour values.** Everywhere (palettes, UI), a colour is either a string, the same in both
modes, or `{ dark = "...", light = "..." }`. `color = "..."` inside a table sets both modes.
Palette entries may also set `shade`. The active Textual theme's `dark` flag picks the mode.

**Overrides.** An animation file's `[palette]` uses the same format and overrides or extends
the species palette for that file only (e.g. a sick animation's greener skin, an elder's
faded body). Every pixel must be covered by the merged palette; otherwise the sprite falls
back to a placeholder and the problem is logged.

**UI colours.** `assets/ui.toml` defines `header-background`, `header-text`, `stat-good`,
`stat-warning`, `stat-bad`, `attention`, `accent` and `lights-off`. A value may be a Textual
theme variable (`$panel`, `$success`...), so the defaults follow the active theme. A species'
`base.toml` `[ui]` table overrides any of them. The app exposes them to CSS as `$tama-<name>`
through `App.get_theme_variable_defaults()`, resolving theme references for the current mode,
so they update when the theme changes.

**Monochrome** (`NO_COLOR`) draws the pixels that contrast with the background: light pixels
on dark themes (features show as holes), and dark pixels on light themes (line art). A test
renders every shipped sprite in every look (dark/light × colour/monochrome) and fails if any
frame draws nothing.

**Generators.** `tools/sprites/` has a shared `kit.py` (grid operations, transformations,
animation recipes, TOML writers, and a shared *pixel vocabulary*: `k` outline, `b` body, `e`
eyes, `m` mouth...). It has one module per species (`tama.py`) plus `overlays.py`.
`python -m tools.sprites.generate` rewrites only the collections it owns, so hand-drawn
species are never touched.

**Species in the domain** are *not* part of this decision. Every pet is drawn as the default
species `tama` via `tama.ui.sprites.species_of(pet)`, the single place to change when the
domain gains a species field (a save-schema bump; see the roadmap).

## Consequences

- A species is one `base.toml` of colours plus its frames. Recolouring is a one-file change,
  and light themes get colours designed for them.
- A new species is a new generator module that reuses every animation recipe, as long as it
  follows the pixel vocabulary. Different body shapes are just different base grids.
- UI colours can carry a species' identity (tama uses its orange as the accent) without
  forking Textual themes.
- Rendering keeps four pre-rendered versions of every frame (one per look). This is cheap at
  these sizes.
