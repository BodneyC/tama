# ADR 0009: The journal is written from domain events and saved with the pet

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

Players want a record of a pet's life: when it hatched, its firsts, how many games it won, how
it died (SPEC §2.9). Most of what happens to a pet happens while tama is closed and is only
simulated on the next load, so a log written by the UI would miss most of the story. The
domain already reports everything that happens as events (`Outcome(pet, events)`), including
during offline catch-up, and the away summary is built from them.

## Decision

- **The journal is derived from events.** `domain/journal.py` has a pure
  `record(journal, events, pet) -> Journal`. It decides which events become entries (life,
  firsts, moments) and keeps lifetime tallies. Nothing else writes to it.
- **It is stored next to the pet, not on it.** `SaveGame` holds `pet`, `rng_state` and
  `journal`, and `GameSession` records every outcome it produces: catch-up, ticks, actions and
  finished games. `Pet` stays the simulation state only, so `advance` and the actions don't
  carry the journal around, and their property tests are unchanged.
- **It is bounded.** Life entries and firsts are kept for ever (there are a few dozen at most);
  moments are capped at the latest 100. Tallies are counters. A whole busy life stays well under
  64 KiB of JSON.
- **Read-only views don't write it.** The pet select screen, `--status` and `tama journal` run
  the in-memory catch-up and can show the entries it would add, but never save. Catch-up is
  deterministic (ADR 0002), so when the pet's own session later catches up for real it
  produces the same events and the same entries.
- Save schema v6 adds the journal. Existing pets start with a "Journal started" entry and zero
  tallies: their past can't be reconstructed, and inventing it would be wrong.

## Consequences

- The journal inherits tick-splitting equivalence: recording the events of `advance(a + b)`
  equals recording those of `advance(a)` then `advance(b)`. A property test asserts it.
- Anything that should appear in the journal must first be a domain event. Later features
  (generations, visits, tricks) add events rather than writing entries directly.
- Entry text is produced in `services/describe.py`, as the away summary is, so the domain
  stores structured entries (kind, event data, time, age) rather than English sentences.
