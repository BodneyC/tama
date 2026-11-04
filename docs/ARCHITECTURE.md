# Architecture

## Overview: functional core, imperative shell

```
             ┌─────────────────────────────────────────────┐
             │                  tama.ui                    │  Textual app, screens, widgets
             │      (imperative shell: timers, input)      │
             └───────────────┬─────────────────────────────┘
                             │ calls
             ┌───────────────▼─────────────────────────────┐
             │               tama.services                 │  GameSession: orchestrates
             │   (use cases: tick, act, load, autosave)    │  domain + clock + repository
             └──────┬───────────────────────────┬──────────┘
                    │                           │
        ┌───────────▼──────────┐    ┌───────────▼───────────┐
        │     tama.domain      │◄───│   tama.persistence    │  Pydantic DTOs, JSON repo,
        │ (pure, deterministic)│    │                       │  migrations, atomic writes
        └──────────────────────┘    └───────────────────────┘
                    ▲
        ┌───────────┴──────────┐
        │      tama.infra      │  Clock impls, paths, config loading, logging setup
        └──────────────────────┘
```

Import rules (enforced by `import-linter`, see `pyproject.toml`):

- `tama.domain` imports nothing from other `tama` packages except `tama.errors`, and no
  third-party packages.
- `tama.persistence` may import `tama.domain`, never `tama.ui` / `tama.services`.
- `tama.services` may import `domain`, `persistence`, `infra`; never `ui`.
- `tama.ui` may import anything except internals of `persistence` (go through services).

## Module layout

```
src/tama/
├── __init__.py            # __version__
├── __main__.py            # python -m tama
├── cli.py                 # Typer app: parses options, picks one file or the pet list, launches
├── cli_pets.py            # what --status and --pause/--resume print, per pet
├── errors.py              # TamaError hierarchy
├── domain/
│   ├── stats.py           # Stat enum, Stats value object, clamp helper
│   ├── stage.py           # LifeStage, Variant, DeathCause enums
│   ├── pet.py             # Pet (frozen dataclass) incl. Drift/Timers; new_egg()
│   ├── balance.py         # Balance: all tunable rates/thresholds
│   ├── context.py         # Context: injected RNG, Balance and local time zone
│   ├── events.py          # Event types, Action/RefusalReason enums, Outcome(pet, events)
│   ├── simulation.py      # advance(pet, elapsed, ctx) -> Outcome
│   ├── lifecycle.py       # stage transitions, adult variant selection, death
│   ├── holiday.py         # pause/resume: settled-pet check, frozen pets (ADR 0008)
│   ├── weight.py          # healthy band per stage, weight_status (SPEC §2.7)
│   ├── journal.py         # Journal + record(journal, events, before) (ADR 0009)
│   ├── lineage.py         # heir_name, hatch_heir, is_heir_of, founder (ADR 0010)
│   ├── visit.py           # visit refusals, start_visit, visit events (ADR 0011)  [M6.12]
│   ├── tricks.py          # known_tricks from discipline (SPEC §2.10)  [M6.13]
│   ├── daylight.py        # dawn/day/dusk/night phase from local time (SPEC §5.1)  [M6.13]
│   ├── actions.py         # apply(pet, action, ctx) / apply_game_outcome() -> Outcome
│   ├── attention.py       # attention_reasons(pet, balance) (SPEC §4)
│   ├── minigames/         # pure game state machines (ADR 0006)
│   │   ├── __init__.py    # GameKind, GameResult (win/draw/loss for the player)
│   │   ├── left_right.py  # Left/Right guessing game
│   │   ├── four_in_a_row.py  # 7x6 board: drop, win/draw detection
│   │   ├── tic_tac_toe.py # 3x3 board: place, win/draw detection
│   │   └── opponent.py    # the pet's move: win, block, positional preference, mistakes
│   └── animation.py       # select_animation(pet, last_event) -> AnimationKey (pure)
├── services/
│   ├── session.py         # GameSession: create/load (+ offline catch-up), tick, act, save
│   ├── autosave.py        # AutosavePolicy: interval + immediate save on milestones
│   ├── roster.py          # PetSummary per pet "as of now" (read-only catch-up), find_pet
│   ├── library.py         # PetLibrary: the UI's entry point to several pets (open + lock,
│   │                      # hatch, archive, borrow for --pause, others needing care)
│   ├── visit.py           # VisitSession: host + guest sessions, pet-vs-pet games  [M6.12]
│   └── describe.py        # plain-text status line, event summaries and journal entries
├── persistence/
│   ├── models.py          # Pydantic SaveFileV<N>, SaveGame(pet, rng_state), to/from_domain()
│   ├── codec.py           # encode()/decode(): JSON text <-> SaveGame (incl. migration)
│   ├── migrations.py      # versioned migration steps
│   ├── repository.py      # SaveRepository protocol + JsonSaveRepository (atomic, .bak)
│   ├── roster.py          # PetRoster: list/create/archive pet files in pets/, last.json,
│   │                      # legacy save.json migration (ADR 0007)
│   └── lock.py            # per-pet lock file (pid; stale locks taken over)
├── infra/
│   ├── clock.py           # Clock protocol, SystemClock, FakeClock (tests), ScaledClock(--speed)
│   ├── paths.py           # save/config/log paths (platformdirs + CLI/env overrides)
│   ├── config.py          # Config dataclass, TOML loader, precedence merge
│   └── logging.py         # rotating file log (never the terminal)
├── ui/
│   ├── app.py             # TamaApp(App): load/hatch, tick timer, quit + signal saves
│   ├── library_flow.py    # several pets: launch into the right pet, pet list, archive
│   ├── app.tcss           # Textual CSS (theme variables only)
│   ├── screens/
│   │   ├── main.py        # MainScreen: header, stage, footer bindings for every action
│   │   ├── pet_select.py  # PetSelectScreen: every pet as of now; play, hatch, archive
│   │   ├── new_pet.py     # NewPetScreen: name prompt with domain-matching validator
│   │   ├── dialogs.py     # Help, Status, FeedMenu modals
│   │   ├── games/         # GameSelectScreen + one modal per mini-game (shared board widget)
│   │   ├── away.py        # AwaySummaryScreen: "While you were away"
│   │   ├── memorial.py    # MemorialScreen: gravestone, life story, new egg, heir's egg
│   │   ├── journal.py     # JournalScreen: tallies + entries, scrollable
│   │   ├── visit.py       # VisitPickerScreen, VisitScreen  [M6.12]
│   │   └── error.py       # ErrorScreen: unreadable save → new pet or quit
│   ├── widgets/           # pet_header, pet_stage (pet + overlay sprites), pet_view (playback)
│   ├── sprites.py         # load, validate and render pixel sprites per Look; species_of(pet)
│   ├── colours.py         # dark/light colour values, Mode, Look
│   └── theme.py           # UI colours -> $tama-* CSS variables for the active theme
└── assets/
    ├── ui.toml            # default UI colours (ADR 0004)
    └── sprites/           # <species>/base.toml + <species>/<variant>/<stage>/<animation>.toml,
                           # overlays/ (ADR 0003, 0004)

tools/sprites/             # dev only, not shipped
├── kit.py                 # grid ops, transformations, animation recipes, pixel vocabulary
├── species.py             # Species (grids + palettes) → every animation file
├── tama.py, owl.py, bear.py  # one module per species: base grids + dark/light palette
├── overlays.py
└── generate.py            # python -m tools.sprites.generate
tools/balance.py           # simulated players live whole lives; judge Balance changes on this
tools/games.py             # scripted players vs the pet at every stage: board-game win rates
```

Modules marked `[M6.x]` are planned in that roadmap milestone and don't exist yet.

Tests mirror this: `tests/unit/domain/...`, `tests/unit/persistence/...`, `tests/ui/...`,
`tests/integration/...`. See `TESTING.md`.

## Key design decisions

### Deterministic simulation

`advance(pet, elapsed, ctx)` is the single entry point for the passage of time. `ctx` carries
`Balance`, a `random.Random`, and the player's time zone (only used for day/night). See
[ADR 0002](adr/0002-fixed-step-exact-simulation.md):

- Time is simulated in fixed steps of `Balance.step` (1 minute), for live play and offline
  catch-up alike. Elapsed time shorter than a step is kept on the pet as `carry`.
- Stat drift is accumulated as exact `Fraction`s on the pet (`Pet.drift`, `poop_progress`), so
  nothing is lost to rounding.
- Random rolls happen only on whole hours of the pet's age, and always draw the same number
  of values, so how time is sliced never changes the RNG sequence.

Together these make `advance(a + b)` **exactly** equal to `advance(a)` then `advance(b)`, the
same events, the same pet, and the same RNG state. Property tests (hypothesis) assert this, plus
stats always in range, dead pets never change, and age is monotonic. A 72-hour catch-up is
~4,300 steps (well under a second).

### Events, not callbacks

Domain functions return an `Outcome(pet, events)`; a refused action is an `Outcome` with a
single `Refused` event. The UI reacts to events (play animation, toast,
bell); the away-summary is just the events from the catch-up `advance`, aggregated. The domain
knows nothing about how events are presented.

### Animation

- `domain/animation.py` decides *which* animation should be playing (pure, unit-tested).
- `ui/widgets/pet_view.py` (a `Static` subclass) owns *frame playback*: a 0.1 s `set_interval`
  timer calls `step()`, which advances frames at each sprite's `fps`; the latest reaction plays
  once before reverting to the state's loop. Idle pets blink and wander using a UI-only RNG
  (cosmetic, never game state). `ViewOptions` turns animation off (tests/snapshots) or to
  static key frames (reduced motion), and selects monochrome.
- Sprites are pixel grids rendered to block characters, two pixels per cell (ADR 0003). Each
  species has a `base.toml` palette with dark- and light-theme colours; animation files only
  override entries. Sprites are pre-rendered per `Look` (theme mode × colour/monochrome) and
  `PetView` picks the look from the app's current theme (ADR 0004).
- UI colours are CSS variables `$tama-*`, produced by `TamaApp.get_theme_variable_defaults()`
  from `assets/ui.toml` plus the species' `[ui]` overrides, so CSS never hard-codes a colour.
- `ui/sprites.py` parses sprite files once (`functools.cache`) into `tuple[Frame, ...]`, validating
  that all frames of an animation share dimensions (a test asserts this for every asset).
- Missing sprite for a variant falls back to the default variant, then a placeholder — never crash.

### Mini-games

Each game is a frozen state object in `domain/minigames/` whose moves return a new state
(`drop(column)`, `place(cell)`, `guess(direction, rng)`), with `result` set once it is over.
The pet's moves come from `opponent.py`, a pure function of the board, the pet's stage
(its mistake chance in `Balance`) and the injected RNG, so any game can be replayed from a
seed (ADR 0006). The UI only renders a state and turns keys into moves; `GameSession` supplies
the RNG (`pet_move(game)`) and applies the finished game's `GameResult` with
`finish_game(result)`, which is the only point where a game touches the pet. The "thinking"
pause and falling pieces are UI timers and are skipped with reduced motion.

### Time in the UI

`TamaApp` runs a 1 s `set_interval` that calls `session.tick()`. The session reads its injected
`Clock` and catches up from `pet.updated_at`, using the same capped catch-up path as loading
(so a laptop sleeping with the game open behaves like the game being closed). With
`ScaledClock`, `--speed` just scales elapsed time. Actions don't tick first; the pet is at most
one tick old.

Save failures during ticks and actions are logged and exposed as `session.save_error` for the
UI to show, rather than crashing the game; `session.close()` raises so shutdown can report.

### Persistence boundary

The domain `Pet` is not a Pydantic model. `persistence/models.py` maps between the domain and
versioned DTOs. This keeps the domain dependency-free and lets the file format evolve
independently (migrations operate on raw dicts before validation).

### Holiday (pause)

A paused pet is ordinary domain state (`Pet.paused_since`), not a UI or session trick, so every
path agrees: `advance` on a paused pet only re-anchors `updated_at` (no steps, no RNG, no
events), actions are refused with `RefusalReason.ON_HOLIDAY`, and `attention_reasons` is empty.
`holiday.py` decides whether a pet may be paused (the same checks as attention calls) and
produces the pause/resume events. Because it lives in the domain, the TUI, `tama --pause` and
the read-only pet summaries need no special cases (ADR 0008).

### Several pets

Each pet is still exactly one `SaveRepository` (one file + `.bak`) and one `GameSession`;
nothing in the domain knows there is more than one pet. `persistence/roster.py` owns the
`pets/` directory: it lists pet files (the listing is the source of truth), creates a file
for a new pet, archives one, remembers the last-played pet and moves a legacy `save.json` in.
`services/roster.py` turns the listing into `PetSummary` values by loading each pet and
running the same capped catch-up as `GameSession.load` **without saving**, so `--status`,
the pet select screen and the header's "other pets need care" count all agree and never
write. Only the pet that is open is saved, and only while its lock is held (ADR 0007).
`--save-path` bypasses the roster and plays a single file, as before.

### Journal

The journal (ADR 0009) is a second product of the events every domain call already returns.
`journal.record(journal, events, before)` is pure, and `GameSession` applies it to every outcome
it takes (`_take`), so the journal covers offline catch-up as well as live play. `before` is the
pet as it was before the call: events only carry the pet's age, and the wall-clock time of an
event is the pet's last step boundary (`updated_at - carry`) plus how far its age is past
`before.age`. Measuring from the pet *after* the call would be wrong for a pet that died (its
clock moves on, its age doesn't) and would break tick-splitting equivalence. Catch-up records
before skipping ahead for the pet sitter, so entries keep their own times. It is saved beside
the pet in `SaveGame`, not on `Pet`, so the simulation never carries it around. Entries are
structured (kind, event data, time, age); `services/describe.py` turns them into text, as it
does for the away summary. Read-only views can preview entries but never save them.

### Generations

An egg left by a pet that died of old age is a flag on the dead pet, and its heir is an
ordinary new pet (ADR 0010). `lineage.hatch_heir` returns both the heir and the updated parent;
`PetLibrary` writes the heir first, then the parent, and treats an heir that names the parent
as proof the egg is hatched. Ancestor records are copied into each heir, so the line never
depends on other files.

### Visits

A visit is two ordinary `GameSession`s, the guest borrowed through `PetLibrary` with its lock
(ADR 0011). `VisitSession` ticks both, moves each pet in a pet-vs-pet game with its own RNG and
mistake chance, and ends the visit when either pet can't go on. The domain only ever sees one
pet at a time; the other appears as a name in events. One `close()` path saves and unlocks the
guest whichever way the visit ends.

### Error handling

- Expected failures (corrupt save, unwritable dir) → typed exceptions from `tama.errors`, caught
  in services/UI and surfaced as screens/toasts.
- Unexpected exceptions in the TUI → logged with traceback to the log file; Textual shows its
  error; the last good save is left untouched (saves are atomic).
