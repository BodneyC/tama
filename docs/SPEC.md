# Product Specification

## 1. Vision

A cosy, charming terminal pet. Launch `tama`, see your pet bobbing on screen, look after it
with single keystrokes, close the terminal, and come back hours later to find it has been
living (and getting hungry) in the meantime. It should feel alive: idle animations, blinking,
reaction animations to every action, and visible mood.

Non-goals (v1): networking, multiple simultaneous pets, sound, mouse-only interactions
(mouse support is a bonus; everything must be keyboard-driven).

## 2. Pet model

### 2.1 Stats

All stats are integers clamped to `0..100`.

| Stat | Meaning | Natural drift (awake) | Natural drift (asleep) |
| --- | --- | --- | --- |
| `hunger` | 100 = full, 0 = starving | −1 per 3 min | −1 per 10 min |
| `happiness` | 100 = elated | −1 per 4 min | −1 per 12 min |
| `energy` | 100 = rested | −1 per 5 min | +1 per 1 min |
| `hygiene` | 100 = clean | −1 per 6 min; −15 per uncleaned poop per hour | −1 per 15 min; poop as awake |
| `health` | 100 = healthy | see 2.3 | see 2.3 |
| `discipline` | 0..100, affects obedience | no drift | no drift |

Plus non-stat fields: `weight` (grams, int), `age` (`timedelta` of simulated life),
`poop_count` (0..4), `is_sick`, `is_asleep`, `lights_on`, `name`, `species_variant`,
`born_at`, `last_updated_at`, `care_mistakes` (int).

Awake decay is scaled by life stage (BABY ×1.5, ELDER ×0.75); asleep drift is not. Asleep
rates are deliberately gentle so a well-fed pet survives a 9-hour night.

The pet poops every 2 h awake (scaled by the stage multiplier), up to 4 poops.

Time is simulated in fixed 1-minute steps; sub-minute remainders and fractional stat
progress are carried on the pet, so the result never depends on how time was sliced.

All rates live in **one** tunable `Balance` config object (frozen dataclass) with these as
defaults, so balancing never requires touching logic. A `--speed N` CLI debug flag multiplies
simulated time (e.g. `--speed 60` = one hour per minute) for manual testing.

### 2.2 Life stages

| Stage | Enters at age | Notes |
| --- | --- | --- |
| `EGG` | 0 | No needs. Hatches after 1 min (wobble animation, then hatch animation). |
| `BABY` | 1 min | Needs decay ×1.5 faster. |
| `CHILD` | 1 h | |
| `TEEN` | 1 day | |
| `ADULT` | 3 days | Adult form chosen by `care_mistakes` + `discipline`: "good" if ≤ 3 mistakes and discipline ≥ 50, else "scruffy". |
| `ELDER` | 10 days | Slower decay (×0.75); eventually passes away peacefully of old age (14–18 days, seeded). |
| `DEAD` | — | Terminal. Memorial screen with lifespan summary; option to start a new egg. |

### 2.3 Health, sickness, death

- Each simulated hour: chance of becoming sick = base 2% + 5% per poop + 10% if hygiene < 20 +
  10% if hunger < 20. Rolled using the injected RNG.
- While sick: health −1 per 2 min; happiness decays 2× faster. Cured by `medicine` (1–2 doses).
- If any of hunger/happiness/hygiene is at 0, health −1 per min.
- Otherwise (not sick, no need at 0), health regenerates +1 per 10 min.
- Health 0 → `DEAD`.
- A **care mistake** is recorded when a need sits at 0 for > 15 consecutive minutes (once per
  episode), or the pet is left with lights on while asleep for > 30 min.

### 2.4 Sleep

- Pet gets sleepy when energy < 20 or during its "night" (22:00–07:00 local time, configurable).
- Asleep: most actions are refused (pet stays asleep), stats drift per the asleep column.
- Player should turn the lights off; it wakes when energy reaches 100 and it's day.
  (v1 has no action to wake the pet early; it would just fall asleep again.)

### 2.5 Offline progression

On load, simulate from `last_updated_at` to now. Cap simulated offline time at **72 hours**
(configurable); beyond that, the pet is assumed to have been looked after by a "pet sitter"
for the remainder (stats frozen). Show a "While you were away…" summary dialog listing
notable events (got hungry, pooped ×3, fell asleep, got sick, evolved, ...).

Clock going backwards (system clock change) must not crash or rewind the pet: treat negative
elapsed time as zero, re-anchor the pet to the new "now", and log a warning.

The same capped catch-up applies to large gaps while the game is open (e.g. a laptop sleeping).

## 3. Actions (player verbs)

| Key | Action | Effect | Refused when |
| --- | --- | --- | --- |
| `f` | Feed → submenu: **Meal** / **Snack** | Meal: hunger +30, weight +1g. Snack: happiness +15, hunger +5, weight +2g. >3 snacks/hour → may get sick. | Asleep, egg, dead, (meal) hunger ≥ 95 |
| `p` | Play → mini-game | Win: happiness +20, energy −10, weight −1g. Lose: happiness +5, energy −10. | Asleep, energy < 10 |
| `c` | Clean | Removes all poop, hygiene → 100 | — |
| `m` | Medicine | Cures one dose of sickness | Not sick |
| `l` | Lights on/off | Toggles lights | — |
| `d` | Discipline | If pet is "misbehaving" (random attention call with no real need): discipline +25. Otherwise: happiness −20. | Asleep |
| `s` | Status | Opens stats panel (hearts/bars, age, weight, stage) | — |
| `?` | Help | Key bindings overlay | — |
| `q` / `ctrl+c` | Quit | Saves and exits | — |

Dialog keys: Feed menu `m` meal / `s` snack / `Esc` cancel. Mini-game `←`/`→` guess, `Enter`
when finished, `Esc` gives up (no effect on the pet). Status/Help close with `Esc` (or their own
key). On the name prompt, `Esc` quits without creating a pet.

Refused actions play a short "shake head" animation and show a toast explaining why.
A dead pet refuses everything; an egg refuses feeding, play, discipline and medicine.

**Misbehaviour:** each simulated hour, an awake, healthy pet of CHILD stage or older has a 15%
chance to start misbehaving (an attention call with no real need). Disciplining it then gives
discipline +25. Ignoring it for > 5 min costs discipline −10 and the pet gives up.

### Mini-game: "Left or Right"

Classic Tamagotchi guessing game. Five rounds; pet will look left or right (seeded RNG);
player presses `←`/`→`. Win ≥ 3 rounds. Animated pet turn + result per round.

## 4. Attention calls

When a need drops below 25, the pet becomes sick, poops, or misbehaves, raise an
**attention call**: an icon in the header blinks and a terminal bell (`\a`) sounds once
(bell configurable / off by default via `--quiet`). Calls clear when resolved.

## 5. UI

### 5.1 Layout (min 60×20; must degrade gracefully and show a "terminal too small" notice below that)

```
┌ tama ─────────────────────────────── 🍖 😊 ⚡ 🧼 ┐
│ Mochi · CHILD · 2d 4h                         ⚠ (blink) │
│                                                         │
│                      (pet sprite,                       │
│                   animated, centred)          💩 💩      │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [f]eed [p]lay [c]lean [m]edicine [l]ights [d]iscipline   │
│ [s]tatus [?]help [q]uit                                  │
└─────────────────────────────────────────────────────────┘
```

- **Header:** name, stage, age, compact stat icons (colour-coded by level), attention indicator.
- **Stage:** the animated pet, poops, sickness skull/bubbles, Zzz when asleep; dimmed when
  lights off (via Textual CSS class on the stage).
- **Footer:** key bindings (Textual `Footer`).
- **Screens:** `NewPetScreen` (name entry + egg), `MainScreen`, `StatusScreen` (modal),
  `FeedMenu` (modal), `MiniGameScreen`, `AwaySummaryScreen` (modal), `MemorialScreen`,
  `HelpScreen` (modal), `ErrorScreen` (corrupt save recovery).

### 5.2 Animation

- Sprites are colour pixel art rendered with block characters (`█ ▀ ▄ ░ ▒ ▓`, two pixels per
  cell; see ADR 0003), one file per `(species_variant, stage, animation)`; animations include at least
  `idle` (2–4 frames, ~2 fps), `blink`, `eat`, `play`, `happy`, `refuse`, `sleep`, `sick`,
  `clean`, `evolve`, `hatch`, `wobble` (egg), `dead`.
- Idle animation includes random blinks and small horizontal wandering across the stage.
- One-shot animations (eat, refuse, …) play once, then return to the state-appropriate loop.
- Frame timing is driven by Textual `set_interval`; the animation *selection* is a pure
  function of pet state (testable without a UI).
- Status indicators (Zzz, sickness, poop) are small pixel sprites under the pet.
- The egg on the name prompt wobbles; hatching cracks the egg and the baby pops out; evolving
  flashes the new form.
- Theme: uses Textual themes (config `theme`); must look good on both dark and light terminals.
  Respect `NO_COLOR` (monochrome sprites). A `--reduced-motion` flag (and config option) shows
  static key frames only: no reactions, blinking or wandering.

## 6. Persistence

- Location: `platformdirs.user_data_path("tama") / "save.json"`; overridable with
  `--save-path PATH` or `TAMA_SAVE_PATH` env var (CLI wins).
- Format: JSON, human-readable, Pydantic model with `schema_version: int`.
- Autosave every 60 s, after every player action, on stage change, and on quit/SIGTERM/SIGHUP.
- Atomic write + `save.json.bak` rotation. On a missing, corrupt or unreadable primary, try
  the backup (and tell the player it was recovered); if both fail, show `ErrorScreen`
  offering: start new pet (moves bad files to `save.json[.bak].corrupt-<timestamp>`) or quit.
- A save from a *newer* schema version is never replaced by the backup or overwritten: the
  player is told to upgrade tama.
- Migrations: `persistence/migrations.py` holds `dict[int, Callable[[dict], dict]]` stepping
  `vN → vN+1`. Every schema bump adds a migration and a fixture test from a real old save.
- RNG state is persisted so a reloaded game continues deterministically.

## 7. Config

`platformdirs.user_config_path("tama") / "config.toml"` (overridable with `TAMA_CONFIG_PATH`),
read with `tomllib`. All keys optional:

```toml
bell = false              # ring the terminal bell on new attention calls
reduced_motion = false
night_start = 22:00:00    # TOML local time, or a string like "22:00"
night_end = 07:00:00
offline_cap_hours = 72    # >= 0; 0 freezes the pet while tama is closed
theme = "nord"            # any Textual theme name
```

Unknown keys or wrong types are an error (reported, not silently ignored). CLI flags override
config, which overrides defaults.

## 8. CLI

```
tama                       # play (load or create)
tama --new                 # start over (confirmation prompt if a live pet exists)
tama --save-path PATH
tama --speed 60            # debug time multiplier (hidden in --help)
tama --seed 1234           # deterministic RNG for new pets (debug)
tama --reduced-motion / --quiet
tama status                # print one-line pet status without the TUI (good for shell prompts);
                           # read-only. Exit 0 ok, 1 no pet yet, 2 unreadable save / bad config
tama --version
```
