# ADR 0008: Holiday pause freezes a pet in the domain

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

Pets live in real time, and a pet left alone dies in about 12–16 hours (SPEC §2.3). That is the
point of a virtual pet, but it means a day away from the computer kills it, and with several
pets (ADR 0007) every one of them needs looking after. The offline cap (72 h) doesn't help: the
pet is dead long before it applies. We want players to be able to go away on purpose without
making neglect free.

## Decision

- A pet can be put **on holiday**: `Pet.paused_since: datetime | None`. While it is set the
  simulation does nothing but re-anchor the pet to the current time: no aging, drift, rolls,
  events or RNG use. Resuming clears it; the pet continues exactly where it stopped.
- Pausing is a **domain action with preconditions**: only a hatched, living pet with no
  attention calls (needs ≥ 25, not sick, no poop, not misbehaving, lights off when asleep) can be
  paused. This keeps the pause a tool for planned absences rather than an escape from a need
  that is already low. Resuming is always allowed and always explicit.
- Care actions on a paused pet are refused (`ON_HOLIDAY`), and a paused pet raises no attention
  calls, so the UI, the CLI (`tama --pause`/`--resume`) and read-only summaries all behave
  consistently without special cases.
- Save schema v3 adds `paused_since`; the v2 → v3 migration sets it to empty.

## Consequences

- Lifespan counts living time only, so a pet that takes long holidays lives longer in calendar
  time. That is intended: holiday is "not playing", not "aging off screen".
- Players can still lose a pet by forgetting to pause; the game stays a game.
- A fixture test from a real v2 save guards the migration, and property tests check that any
  amount of paused time leaves a pet byte-for-byte unchanged apart from `updated_at`.
- Pausing at bedtime is allowed and makes nights free. That's acceptable: nights are already
  survivable (SPEC §2.3), and the lights-off rule still applies before pausing.
