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
| `hunger` | 100 = full, 0 = starving | −1 per 5 min | −1 per 10 min |
| `happiness` | 100 = elated | −1 per 6 min | −1 per 12 min |
| `energy` | 100 = rested | −1 per 5 min | +1 per 1 min |
| `hygiene` | 100 = clean | −1 per 6 min; −15 per uncleaned poop per hour | −1 per 15 min; poop as awake |
| `health` | 100 = healthy | see 2.3 | see 2.3 |
| `discipline` | 0..100, affects obedience | no drift | no drift |

Plus non-stat fields: `weight` (grams, int), `age` (`timedelta` of simulated life),
`poop_count` (0..4), `is_sick`, `is_asleep`, `lights_on`, `name`, `species` (the animal, fixed
at hatching; default `tama`), `variant` (adult form),
`born_at`, `last_updated_at`, `care_mistakes` (int), `paused_since` (when the pet went on
holiday, §2.6; empty while it is living normally), `stay_awake` (how much longer a pet the
player woke stays up, §2.4) and `woken_tantrum` (its current tantrum came from being woken).

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

- Each simulated hour: chance of becoming sick = base 1% + 5% per poop + 10% if hygiene < 20 +
  10% if hunger < 20. Rolled using the injected RNG.
- While sick: health −1 per 10 min; happiness decays 1.5× faster. Cured by `medicine` (1–2 doses).
- If any of hunger/happiness/hygiene is at 0, health −1 per 8 min.
- Otherwise (not sick, no need at 0), health regenerates +1 per 10 min.
- Health 0 → `DEAD`.
- A **care mistake** is recorded when a need sits at 0 for > 15 consecutive minutes (once per
  episode), or the pet is left with lights on while asleep for > 30 min.

### 2.4 Sleep

- Pet gets sleepy when energy < 20 or during its "night" (22:00–07:00 local time, configurable).
- Asleep: most actions are refused (pet stays asleep), including medicine: a pet that falls
  sick in the night can be left to sleep it off or woken for its dose. Stats drift per the
  asleep column.
- Player should turn the lights off; it wakes when energy reaches 100 and it's day.
- **Waking it early** (`w`): the pet wakes grumpy: happiness −20, energy −20, and it throws a
  tantrum (as misbehaviour, §3; a tantrum it was already having carries on unchanged). It
  then stays up for 30 min whatever the time or its energy, after which the normal rules
  apply: at night it drops straight back off, and by day the lost energy brings its next
  sleep forward. Disciplining a tantrum the player caused this way ends it but earns no
  discipline, so waking can't be used to raise a well-behaved adult; ignoring it still costs
  discipline −10 after 30 min.

### 2.5 Offline progression

On load, simulate from `last_updated_at` to now. Cap simulated offline time at **72 hours**
(configurable); beyond that, the pet is assumed to have been looked after by a "pet sitter"
for the remainder (stats frozen). Show a "While you were away…" summary dialog listing
notable events (got hungry, pooped ×3, fell asleep, got sick, evolved, ...).

Clock going backwards (system clock change) must not crash or rewind the pet: treat negative
elapsed time as zero, re-anchor the pet to the new "now", and log a warning.

The same capped catch-up applies to large gaps while the game is open (e.g. a laptop sleeping).

A pet on holiday (§2.6) is not simulated at all: catch-up skips the paused time, and the
"While you were away…" dialog only covers time the pet was living.

### 2.6 Holiday (pause)

A pet left alone dies in about 12–16 hours (§2.3), so a player going away for a day or more can
put a pet **on holiday**: it is frozen in time until they resume it.

- **While on holiday nothing happens:** no aging (the 14–18-day lifespan counts only living
  time), no drift, poop, sickness, misbehaviour, sleep changes or care mistakes. The pet keeps
  its stats, timers and fractional progress exactly, and the RNG is not used.
- **Only a settled pet can go on holiday:** it must be hatched and alive, with no attention
  calls (§4): every need at 25 or more, not sick, no poop, not misbehaving, and lights off if
  it is asleep. Otherwise the request is refused with the reasons, so pausing can't be used
  to dodge a need that is already low. Eggs and dead pets can't be paused.
- **Resuming is always explicit** (`h` again, or `tama --resume`), so opening tama to look
  doesn't wake a pet. On resume the pet picks up exactly where it was, re-anchored to now, and
  living time starts again; a pet paused during the night wakes on the normal schedule.
- **Showing it:** the header reads `⏸ on holiday since <date>`, the stage shows the pet's
  sleep frame dimmed with a small suitcase overlay sprite, and every care action is refused
  with "on holiday" (status, help, switching pets and quit still work). Paused pets raise no
  attention calls and are never counted as "needing care".
- **Events:** `PausedForHoliday` and `ResumedFromHoliday` (with the holiday's length) appear in
  toasts and the "While you were away" summary ("Was on holiday for 3d 2h").

## 3. Actions (player verbs)

| Key | Action | Effect | Refused when |
| --- | --- | --- | --- |
| `f` | Feed → submenu: **Meal** / **Snack** | Meal: hunger +30, weight +1g. Snack: happiness +15, hunger +5, weight +2g. >3 snacks/hour → may get sick. | Asleep, egg, dead, misbehaving, (meal) hunger ≥ 95 |
| `p` | Play → choose a mini-game (§3.1) | Win: happiness +20, energy −10, weight −1g. Draw: happiness +10, energy −10. Lose: happiness +5, energy −10. | Asleep, misbehaving, energy < 10 |
| `c` | Clean | Removes all poop, hygiene → 100 | — |
| `m` | Medicine | Cures one dose of sickness | Asleep, not sick |
| `l` | Lights on/off | Toggles lights | — |
| `d` | Discipline | If pet is "misbehaving" (random attention call with no real need): discipline +25 (+0 for a tantrum from being woken). Otherwise: happiness −20. | Asleep |
| `w` | Wake | Wakes a sleeping pet early (§2.4): happiness −20, energy −20, a tantrum, stays up 30 min. Not shown in the footer (no room); listed in Help. | Awake, egg |
| `s` | Status | Opens stats panel (hearts/bars, age, weight, stage) | — |
| `h` | Holiday | Puts a settled pet on holiday (frozen in time), or brings it back (§2.6) | Egg, dead, (to pause) any attention call |
| `t` | Tamas | Saves, then opens the pet select screen to switch pets (§6.1) | — |
| `?` | Help | Key bindings overlay | — |
| `q` / `ctrl+c` | Quit | Saves and exits | — |

Dialog keys: Feed menu `m` meal / `s` snack / `Esc` cancel. Mini-game keys are in §3.1; in
every game `Enter` closes the finished game and `Esc` gives up (no effect on the pet). Status/Help
close with `Esc` (or their own key). On the name prompt, `↑`/`↓` choose the animal (starting from `--species`, else `tama`;
the egg changes to match) and `Esc` quits without creating a pet.

Refused actions play a short "shake head" animation and show a toast explaining why.
A dead pet refuses everything; an egg refuses feeding, play, discipline, medicine and waking.

**Misbehaviour:** each simulated hour, an awake, healthy pet of CHILD stage or older has a 15%
chance to start misbehaving (an attention call with no real need). While misbehaving it throws
a tantrum: it loops the `misbehave` animation (scowling and stamping) and refuses meals,
snacks and play ("Turned its nose up at a meal: misbehaving", "Sulked and wouldn't play"),
though it still accepts medicine, cleaning and the lights. Disciplining it then gives
discipline +25. Ignoring it for > 30 min costs discipline −10 and the pet gives up. (30 min
lets a player who checks in about every half hour catch most tantrums: `tools/balance.py`.)

### 3.1 Mini-games

`p` first checks the play refusals (asleep, energy < 10). If the pet is willing, a **game
select** dialog lists the games; `↑`/`↓` + `Enter` or the number keys `1`–`3` start one, and
`Esc` closes it without playing (no effect on the pet). The last game chosen this session is
pre-selected. Every game ends in a **win, draw or loss** for the player, applied as in the `p`
row of §3; the pet shows its sprite beside the game and reacts when it ends (`happy` when the
player wins, `play` otherwise). Games are not saved: quitting tama mid-game abandons it with no
effect. All randomness (the pet's choices) comes from the session's seeded RNG.

1. **Left or Right** — the classic Tamagotchi guessing game. Five rounds; the pet will look left
   or right; the player presses `←`/`→` to guess. Win ≥ 3 rounds (no draws). The pet turns the
   way it looked (`look_left`/`look_right` poses) and the result is shown each round.
2. **Four in a Row** (connect-four style) — a 7-column × 6-row board, played against the pet.
   The player always moves first. `←`/`→` move a marker (`▼`) above the columns (wrapping
   at the edges; full columns are skipped), `↓` or `Enter` drops a piece, which falls to the
   lowest empty cell. Pieces are circles: the player's `●` in `$tama-piece-player`, the pet's
   `●` in `$tama-piece-pet`; empty cells are a dim `·`. In monochrome the pet's pieces are `○`
   so the two sides differ by shape. Four in a row horizontally, vertically or diagonally
   wins; a full board with no line is a draw. The winning four are highlighted.
3. **Tic-Tac-Toe** — a 3×3 board against the pet; the player is `✕` (`$tama-piece-player`),
   the pet `◯` (`$tama-piece-pet`), and the player always moves first. Arrow keys move a
   highlighted cursor and `Enter`/`Space` place a mark in an empty cell; `1`–`9` place
   directly, laid out like a numeric keypad (`7` top-left, `3` bottom-right). Three in a row
   wins (highlighted); a full board without one is a draw.

**The pet as an opponent** (both board games): after a short "thinking" pause it picks, in
order: a move that wins now; a move that blocks the player's immediate win; in Four in a Row,
a column that doesn't let the player win directly on top of it; otherwise the best-placed
move (Four in a Row: nearest the centre column; Tic-Tac-Toe: centre, then corners, then
edges), ties broken at random. With a per-stage **mistake chance** it instead plays a random
legal move, so young pets are easy and grown-ups put up a fight (defaults in `Balance`:
baby 60%, child 40%, teen 25%, adult 15%, elder 20%: elders get a little rusty).

## 4. Attention calls

A pet on holiday raises no calls (§2.6). Otherwise, when a need drops below 25, the pet
becomes sick, poops, or misbehaves, raise an
**attention call**: an icon in the header blinks and a terminal bell (`\a`) sounds once
(bell configurable / off by default via `--quiet`). Calls clear when resolved; a call that
comes back later rings again. Calls already active when tama opens don't ring (the player is
there), and with reduced motion the icon is steady instead of blinking.

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

- **Header:** name, stage, age, compact stat icons (colour-coded by level), attention indicator
  (plus `⚠ +N` when other pets need care, §6.1), or `⏸ on holiday since <date>` (§2.6).
- **Stage:** the animated pet, poops, sickness skull/bubbles, Zzz when asleep; dimmed when
  lights off (via Textual CSS class on the stage).
- **Footer:** key bindings (Textual `Footer`).
- **Screens:** `PetSelectScreen` (§6.1), `NewPetScreen` (name entry + egg), `MainScreen`,
  `StatusScreen` (modal),
  `FeedMenu` (modal), `GameSelectScreen` (modal), one modal per mini-game (`LeftRightScreen`,
  `FourInARowScreen`, `TicTacToeScreen`), `AwaySummaryScreen` (modal), `MemorialScreen`,
  `HelpScreen` (modal), `ErrorScreen` (corrupt save recovery). Every game fits the minimum
  60×20 terminal with the pet beside the board.

### 5.2 Animation

- Sprites are colour pixel art rendered with block characters (`█ ▀ ▄ ░ ▒ ▓`, two pixels per
  cell; see ADR 0003). Each species has its own palette with colours for dark and light themes,
  and may theme the UI's colours (ADR 0004). One file per `(species, variant, stage,
  animation)`; animations include at least
  `idle` (2–4 frames, ~2 fps), `blink`, `eat`, `play`, `happy`, `refuse`, `sleep`, `sick`,
  `clean`, `evolve`, `hatch`, `wobble` (egg), `dead`, `misbehave` (a tantrum loop: angry
  brows, stamping and shouting), and the poses `look_left`/`look_right` (the Left/Right game). The feed menu shows small animated meal and snack sprites.
- Board games: while "thinking" the pet alternates `look_left`/`look_right` (~0.6 s); a dropped
  Four in a Row piece falls row by row (~40 ms per row). With reduced motion the pet's move
  appears at once and pieces land without falling.
- Idle animation includes random blinks and small horizontal wandering across the stage.
- One-shot animations (eat, refuse, …) play once, then return to the state-appropriate loop.
- Frame timing is driven by Textual `set_interval`; the animation *selection* is a pure
  function of pet state (testable without a UI).
- Status indicators (Zzz, sickness, poop, and a suitcase for a pet on holiday) are small pixel
  sprites under the pet.
- The egg on the name prompt wobbles; hatching cracks the egg and the baby pops out; evolving
  flashes the new form.
- Theme: uses Textual themes (config `theme`); must look good on both dark and light terminals.
  Respect `NO_COLOR` (monochrome sprites). A `--reduced-motion` flag (and config option) shows
  static key frames only: no reactions, blinking or wandering.

## 6. Persistence

- Location: one file per pet in `platformdirs.user_data_path("tama") / "pets/"` (§6.1);
  `--save-path PATH` or the `TAMA_SAVE_PATH` env var (CLI wins) instead plays exactly one save
  file, outside the pet list (handy for experiments and tests). In this section, `save.json`
  stands for any one pet's file.
- Format: JSON, human-readable, Pydantic model with `schema_version: int` (v3 adds
  `paused_since`; the v2 → v3 migration sets it to empty, i.e. not on holiday. v4 adds
  `stay_awake` and `woken_tantrum`; the v3 → v4 migration sets them to zero and false).
- Autosave every 60 s, after every player action, on stage change, and on quit/SIGTERM/SIGHUP.
- Atomic write + `save.json.bak` rotation. On a missing, corrupt or unreadable primary, try
  the backup (and tell the player it was recovered); if both fail, show `ErrorScreen`
  offering: start new pet (moves bad files to `save.json[.bak].corrupt-<timestamp>`) or quit.
- A save from a *newer* schema version is never replaced by the backup or overwritten: the
  player is told to upgrade tama.
- Migrations: `persistence/migrations.py` holds `dict[int, Callable[[dict], dict]]` stepping
  `vN → vN+1`. Every schema bump adds a migration and a fixture test from a real old save.
- RNG state is persisted so a reloaded game continues deterministically.

### 6.1 Several tamas

A player can keep up to **9 tamas** at once (so `1`–`9` can pick them). Each is an
independent pet with its own species, RNG and save file, and **all of them live in real time**:
a pet that isn't open ages and gets hungry exactly as if tama were closed (§2.5, with its own
offline cap), so neglecting one costs that pet, not the others. Pets on holiday (§2.6) are
the exception: they stay frozen until resumed.

- **Storage:** `pets/<slug>-<id>.json` (+ its own `.bak`), where `<slug>` is the pet's name made
  filename-safe and `<id>` a short random hex id fixed at hatching. The directory listing *is*
  the list of pets; there is no index to fall out of step. `pets/last.json` remembers which pet
  was played last (if it is missing or unreadable, the most recently updated pet is used).
  Pet files keep the existing save schema; no schema bump is needed.
- **Names:** living pets have distinct names (compared case-insensitively); the name prompt
  explains a clash ("You already have a Mochi"). A dead pet's name may be reused.
- **Launching:** with no pets, `tama` shows the name prompt. With exactly one pet, it opens
  it. With several, it shows the **pet select** screen with the last-played pet pre-selected,
  so `Enter` continues where you left off. `tama --pet NAME` skips the screen.
- **Pet select screen:** one row per pet, each simulated up to now in memory (not saved):
  name (cut short with `…` past 11 characters), stage, age and a mark: `⚠` needs care, `⏸`
  on holiday, `✝` passed away, `?` can't be read. Beside the list, the highlighted pet's
  sprite (idle, asleep, or its gravestone) and details: full name, stage and species, and
  the `⚠` reasons, `⏸ on holiday since <date>`, "passed away (…) at <age>" or "can't be
  read". (One sprite beside the list, rather than one per row, fits nine pets in 60×20.) Keys: `↑`/`↓` or `1`–`9` select, `Enter` plays,
  `n` hatches a new egg (name prompt; refused at 9 pets, saying so), `a` archives the
  selected pet (dead pets only, after a `y`/`n` confirmation), `Esc`/`q` quit. An unreadable
  pet opens the `ErrorScreen` for that file only; the other pets are unaffected.
- **Switching while playing:** `t` on the main screen saves the current pet and opens the pet
  select screen. The UI colours follow whichever pet is open (ADR 0004).
- **Other pets needing care:** while one pet is open, the header also shows `⚠ +N` when N
  other living pets need attention (re-checked every minute from their saves, read-only); the
  bell does not ring for other pets.
- **Death:** the memorial's "new egg" adds a new pet; the dead one stays in the list as a
  memorial until archived. **Archiving** moves its files to `pets/archive/` (never deleted),
  where tama no longer lists them.
- **One window per pet:** opening a pet takes a lock (`pets/<file>.lock` holding the process
  id); a second tama asked for the same pet says it's already open elsewhere. Stale locks
  (process gone) are taken over. `--status` never takes locks.
- **Where:** the user data directory, or `TAMA_DATA_DIR` if set.
- **Upgrading:** on first run with the new layout, an existing `save.json` (+ `.bak`) in the
  data directory is moved into `pets/` and becomes the last-played pet; nothing is lost.

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
tama                       # play: name prompt, the only pet, or the pet select screen (§6.1)
tama --pet NAME            # play this pet (case-insensitive; a unique prefix is enough;
                           # living pets win over dead ones of the same name)
tama --new                 # hatch an additional egg (refused at 9 pets)
tama --species owl         # which animal the name prompt starts on; a pet can't change
                           # species (with --pet, naming another species is an error). Default: tama
tama --status              # one line per pet, as of now (read-only, no TUI): the status line
                           # below, last-played pet first and marked `*`, then by name;
                           # pets on holiday read "Mochi · adult owl · on holiday since 3 Nov";
                           # with --pet, just that pet. Exit 0 ok, 1 no pets yet,
                           # 2 if any pet's save is unreadable (its line says so) / bad config
tama --list-species        # the animals that have art
tama --pause               # put every living pet on holiday without opening the TUI (§2.6);
                           # with --pet, just that pet. Prints one line per pet: paused, already
                           # paused, or refused with the reasons (exit 2 if any was refused or
                           # is open in another tama)
tama --resume              # bring every pet on holiday back (or just --pet NAME); one line
                           # per pet resumed, or "No pets are on holiday."
tama --save-path PATH      # play exactly this one save file, outside the pet list
tama --speed 60            # debug time multiplier (hidden in --help)
tama --seed 1234           # deterministic RNG for new pets (debug)
tama --reduced-motion / --quiet
tama status                # same as --status (kept for existing shell prompts). Status line,
                           # e.g. "Mochi · child owl · 1h 0m · hunger 80 · ..."
tama --version
```
