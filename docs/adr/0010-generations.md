# ADR 0010: Generations — an heir is a new pet that carries its family line

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

When a pet dies of old age, the only option is a new, unrelated egg. The original toys let a
well-kept pet carry on through its descendants, which rewards looking after a pet for its
whole life (SPEC §2.8). Several pets (ADR 0007) already gives each pet its own file and RNG,
and the player may archive a dead pet at any time, so the family line can't depend on the
ancestors' files still being there.

## Decision

- **The egg is a flag on the dead parent** (`heir_hatched: bool`), set by the death of old
  age (`LaidEgg`), not a pet. It takes no slot in the 9-pet limit until it is hatched, and it
  can't be neglected.
- **The heir is an ordinary new pet** with its own file, id and RNG. Domain
  `hatch_heir(parent, name, now, rng, balance)` returns the heir and the parent with its egg
  marked hatched. It inherits only the species, `generation + 1`, the ancestor records and,
  from a good parent, a head start in discipline (`Balance.heir_discipline`). Everything else
  is fresh, so an heir is never stronger than a pet in the rules that matter for survival.
- **Lineage is copied, not referenced.** `Pet.ancestors` holds small `AncestorRecord`s (name,
  generation, adult form, lifespan) for the whole line, so archived or lost ancestor files
  never break it. A line of a hundred generations is still only a few KiB.
- **The heir's RNG is seeded from the parent's RNG**, so a line started with `--seed` can be
  replayed, and the parent's RNG state (saved with it) moves on.
- **Hatching writes two files.** The heir is written first; the parent is then saved with
  `heir_hatched`. If tama stops between the two, the roster sees an heir whose newest ancestor
  is this parent and treats the egg as hatched, so a crash can never produce two heirs.
- Save schema v7 adds the fields. Pets that died of old age before v7 are migrated with
  `heir_hatched = true`: their egg was never offered, and offering it now would be surprising.

## Consequences

- Heir names follow "Mochi II", "Mochi III"; the domain parses a trailing roman numeral, so a
  name that happens to end in one ("Vi") is read as a numeral. That's acceptable: the player
  can edit the prefilled name.
- Archiving a dead pet with a waiting egg archives the egg too; the confirmation says so.
- The journal (ADR 0009) records `LaidEgg` and `HeirHatched` on the parent and "Hatched from
  Mochi's egg" on the heir.
