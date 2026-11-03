# ADR 0002: Fixed one-minute steps with exact remainders

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

The pet must evolve identically whether the app is open (ticking every second) or closed
(catching up hours at once on load). ARCHITECTURE originally suggested 1-second steps for live
play, coarser steps for catch-up, and approximate equivalence between them. Approximate
equivalence is hard to test precisely and invites subtle drift bugs. Mixed step sizes also make
random rolls (sickness, misbehaviour) depend on how time was sliced.

## Decision

- One fixed step size, `Balance.step` (default 1 minute, must divide an hour), for all
  simulation. Sub-step elapsed time is carried on the pet (`Pet.carry`).
- Drift is accumulated as exact `fractions.Fraction` remainders on the pet rather than floats or
  rounded integers.
- Random rolls happen only on whole hours of the pet's age and always consume the same
  number of RNG draws.
- `advance` therefore satisfies exact equality: `advance(a + b) == advance(a) ; advance(b)`,
  including events and RNG state. This is a hypothesis property test.

## Consequences

- Live play changes the pet once per simulated minute. This is fine: the fastest stat changes
  are about 1 point a minute, and animation is independent of simulation.
- Catch-up costs one step per minute: 72 h is about 4,300 steps, and a full 18-day life is about
  26,000 steps (~1.5 s in tests). Bulk catch-up could be optimised later without changing
  results, because the semantics are pinned down by the property tests.
- Persistence must store `Fraction` values exactly (for example as `"numerator/denominator"`
  strings) along with `carry` and the RNG state.
