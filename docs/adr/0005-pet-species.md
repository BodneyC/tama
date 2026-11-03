# ADR 0005: A pet's species is part of the pet, chosen at hatching

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

ADR 0004 organised art by species but left every pet drawn as a `tama`. Players want to pick
the animal (owl, bear, ...). If the animal were only a display setting, a pet could change
species between launches. A pet's look also depends on its species' palette and UI colours.

## Decision

- `Pet.species` is a domain field: a lowercase identifier (`tama`, `owl`, `polar-bear`),
  default `tama`, set by `new_egg(species=...)` and never changed afterwards. The domain only
  checks the name's shape; which species have art is a UI concern (`available_species()`
  lists the sprite directories that have a `base.toml`).
- The save schema is now v2. The v1 → v2 migration sets `species = "tama"`, the literal value
  rather than a constant, so the migration stays correct if the default ever changes.
- The player picks the species with `tama --species ANIMAL`, which applies when hatching a new
  egg (no save yet, or `--new`). Naming a different species for an existing pet is an error
  that explains how to start over. `tama --list-species` lists the choices.
- The UI draws each pet with its own species' art, and the app switches its `$tama-*` UI
  colours to the loaded pet's species.

## Consequences

- Adding a species is purely an art change (ADR 0004). It becomes selectable as soon as its
  directory exists.
- Old saves keep working: they load as tamas.
- The name prompt also lets the player choose the species (`↑`/`↓`), starting from
  `--species`. This needed no domain or persistence change.
