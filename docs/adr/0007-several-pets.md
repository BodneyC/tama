# ADR 0007: Several pets, one save file each, listed from a directory

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

tama has kept exactly one pet in `save.json`, and `--new` replaced it. Players want several
tamas at once, to pick which to play and to see how all of them are doing from the shell
(`tama --status`). The single-pet design is well tested: an atomic, versioned save with a
`.bak`, offline catch-up on load, and a session that owns one pet. We want to keep all of that.

## Decision

- **One file per pet** in `<data dir>/pets/<slug>-<id>.json`, each with its own `.bak`, using
  the existing save schema. `<id>` is a short random hex id chosen at hatching (in persistence,
  not the domain), so two pets never share a file even with the same name.
- **The directory listing is the list of pets.** There is no index file to fall out of step
  with the saves. Only one small piece of shared state exists, `pets/last.json` (the last
  played pet), and losing it is harmless: tama falls back to the most recently updated pet.
- **Every pet lives in real time.** Pets that aren't open are not ticked; like a closed game,
  they catch up (capped) when loaded. Anything that only *looks* at pets (the pet select
  screen, `--status`, the header's "other pets need care") runs that catch-up in memory and
  never saves, so looking can't change or corrupt a pet.
- **A lock per open pet** (`<file>.lock` with the process id; stale locks are taken over)
  stops two tama processes from saving the same pet over each other. Read-only views don't lock.
- **At most 9 pets**, so number keys can pick them, and living pets have distinct names (case-
  insensitive), so `--pet NAME` and `--status` are unambiguous.
- **Dead pets stay listed** as memorials until the player archives them; archiving moves the
  files to `pets/archive/`. tama never deletes a pet's files.
- **Upgrading** moves an existing `save.json` (+ `.bak`) into `pets/` on first run. The
  `--save-path`/`TAMA_SAVE_PATH` override keeps meaning "play exactly this one file", outside
  the pet list.

## Consequences

- The domain, the save schema, `JsonSaveRepository` and `GameSession` are unchanged; the new
  code is a roster in persistence, read-only summaries in services, and a pet select screen.
- Startup with several pets loads and simulates each of them once (up to 9 × the offline cap
  of 1-minute steps); this must stay fast enough not to be noticed, and is measured in tests.
- `--new` changes meaning (adds a pet instead of replacing the only one); the CLI help and
  SPEC §8 say so. `tama status` stays as an alias of `--status` for existing shell prompts.
- Backups, corruption recovery and newer-version protection work per pet: one unreadable pet
  doesn't stop the others from being played.
