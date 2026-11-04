# ADR 0011: Visits open a second pet's session in the same window

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

Players keep several pets (ADR 0007), but each one is played on its own and they never meet.
A visit (SPEC §3.2) puts two pets on the stage and lets them play a board game against each
other. Until now tama has held at most one pet's lock and one `GameSession` at a time, and
the domain knows nothing about more than one pet.

## Decision

- **Two ordinary sessions.** A visit borrows the guest through `PetLibrary`, which loads it
  with the usual capped catch-up and takes its lock, exactly as opening it would. A
  `VisitSession` in `services/visit.py` holds the host's and the guest's `GameSession` and
  ticks both. Each pet still has one file, one RNG and one autosave policy.
- **The domain sees one pet at a time.** `visit.py` has per-pet functions (`visit_refusals`,
  `start_visit`) and events (`Visited(friend)`, `PlayedWith(friend, game, result)`) carrying the
  other pet's name only. There is no two-pet state in the domain, and nothing is saved about
  a visit except each pet's `last_visit`.
- **Each pet moves with its own RNG** and its own stage's mistake chance, so a pet-vs-pet game
  replays from the two pets' saved RNG states, and a visit can't change how one pet's future
  rolls would have gone except through what it actually did.
- **The guest is always given back.** Every way out of a visit (ending it, the visit ending by
  itself, `t`, `q`, SIGTERM/SIGHUP, an exception in the UI) saves the guest and releases its
  lock, through one `VisitSession.close()`. A stale lock left by a crash is taken over as before.
- **Visits can't be farmed.** The happiness bonus is given at most once per
  `Balance.visit_cooldown` per pet (`Pet.last_visit`, save schema v8), and game effects are
  the same as playing with the player.

## Consequences

- One process may hold two locks; the lock code must allow that and release both on exit.
- The header's "other pets need care" count still reads the guest's saved file, which is at
  most one autosave behind while it visits.
- `tools/games.py` gains pet-vs-pet win rates, so the opponent's mistake chances are judged
  from both sides.
- The "multiple simultaneous pets" non-goal in the SPEC is dropped; networking stays out.
