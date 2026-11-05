# Product Specification

## 1. Vision

A cosy, charming terminal pet. Launch `tama`, see your pet bobbing on screen, look after it
with single keystrokes, close the terminal, and come back hours later to find it has been
living (and getting hungry) in the meantime. It should feel alive: idle animations, blinking,
reaction animations to every action, and visible mood.

Non-goals (v1): networking, sound, mouse-only interactions (mouse support is a bonus;
everything must be keyboard-driven). Several pets live side by side (§6.1) and can visit each
other in one window (§3.2), but never across machines.

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

Plus non-stat fields: `weight` (grams, int; §2.7), `age` (`timedelta` of simulated life),
`poop_count` (0..4), `is_sick`, `is_asleep`, `lights_on`, `name`, `species` (the animal, fixed
at hatching; default `tama`), `variant` (adult form),
`born_at`, `last_updated_at`, `care_mistakes` (int), `paused_since` (when the pet went on
holiday, §2.6; empty while it is living normally), `stay_awake` (how much longer a pet the
player woke stays up, §2.4), `woken_tantrum` (its current tantrum came from being woken),
`weight_progress` (fraction of a gram burned, §2.7) and `timers.weight` (how long its weight has
been outside the healthy band),
`generation`, `ancestors` and `heir_hatched` (its family line, §2.8) and `last_visit` (pet
age at its last visit, §3.2). Each pet also keeps a **journal** (§2.9) beside it in the save.

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
| `ADULT` | 3 days | Adult form chosen by weight, `care_mistakes` and `discipline`: "chubby" if overweight on the day it grows up (§2.7), else "good" if ≤ 3 mistakes and discipline ≥ 50, else "scruffy". Elders keep their adult form. |
| `ELDER` | 10 days | Slower decay (×0.75); eventually passes away peacefully of old age (14–18 days, seeded). |
| `DEAD` | — | Terminal. Memorial screen with lifespan summary and journal highlights (§2.9); option to start a new egg, and after a death of old age, to hatch the egg it left (§2.8). |

### 2.3 Health, sickness, death

- Each simulated hour: chance of becoming sick = base 1% + 5% per poop + 10% if hygiene < 20 +
  10% if hunger < 20 + 5% if overweight (§2.7). Rolled using the injected RNG.
- While sick: health −1 per 10 min; happiness decays 1.5× faster. Cured by `medicine` (1–2 doses).
- If any of hunger/happiness/hygiene is at 0, health −1 per 8 min.
- Otherwise (not sick, no need at 0), health regenerates +1 per 10 min, except while
  underweight (§2.7), when it doesn't regenerate at all.
- Health 0 → `DEAD`.
- A **care mistake** is recorded when a need sits at 0 for > 15 consecutive minutes (once per
  episode), the pet is left with lights on while asleep for > 30 min, or its weight stays
  outside the healthy band for > 12 h (once per episode, §2.7).

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
  to dodge a need that is already low. Eggs and dead pets can't be paused. The weight call
  (§2.7) is the one exception: weight changes over days, so it doesn't stop a holiday (and
  its 12-hour episode timer is frozen with everything else).
- **Resuming is always explicit** (`h` again, or `tama --resume`), so opening tama to look
  doesn't wake a pet. On resume the pet picks up exactly where it was, re-anchored to now, and
  living time starts again; a pet paused during the night wakes on the normal schedule.
- **Showing it:** the header reads `⏸ on holiday since <date>`, the stage shows the pet's
  sleep frame dimmed with a small suitcase overlay sprite, and every care action is refused
  with "on holiday" (status, help, switching pets and quit still work). Paused pets raise no
  attention calls and are never counted as "needing care".
- **Events:** `PausedForHoliday` and `ResumedFromHoliday` (with the holiday's length) appear in
  toasts and the "While you were away" summary ("Was on holiday for 3d 2h").

### 2.7 Weight

Weight used to be a number on the status panel and nothing more. It now matters, so the
choice between a meal and a snack is a real one.

- **Gaining and losing:** a meal adds 2 g, a snack 2 g, a stuffed meal (§3) 4 g, and a won game
  takes 1 g off. Awake, the pet also burns **1/64 of its own weight per hour** (scaled by the
  stage multiplier, like the other awake drift; fractions of a gram are carried in
  `weight_progress`), never going below `min_weight`. Because the burn grows with the weight,
  weight settles where diet and burn meet instead of climbing for ever: about 20 g for a pet
  fed meals when hungry, over 80 g for one kept happy with snacks.
- **Healthy band per stage** (in `Balance`): baby 4–10 g, child 4–16 g, teen 7–24 g, adult
  12–44 g, elder 18–50 g. The bands rise from stage to stage, so a growing pet has to eat to
  stay in them; elders burn more slowly (×0.75) and are allowed to be heavier.
- **Overweight** (above the band): +5% hourly sickness chance (§2.3) and awake energy drift
  ×1.25. **Underweight** (below the band): health doesn't regenerate (§2.3). Either one raises
  a `weight` attention call (§4), and **12 h** outside the band in a row is a care mistake
  (once per episode; the timer resets when weight is back in the band and is frozen on
  holiday). A pet that grows up while overweight becomes a **chubby** adult (§2.2).
- **Showing it:** the status panel shows the weight with its healthy band ("23 g (12-44)") and,
  outside it, the weight and a `▲` over or `▼` under in the warning colour. Leaving the band is
  announced ("Got overweight", "Got underweight") and the header's attention reasons say
  "overweight" or "underweight".
- **Balance:** `tools/balance.py` reports time out of band, weight at adulthood and chubby
  adults, and has a "casual snacker" who cheers the pet up with snacks instead of games.
  Results (20 lives each): diligent, casual and busy players spend 0% of life out of band and
  reach adulthood at 14-24 g, with every other result as before weight mattered; the snacker's
  pet is out of band 98% of its life, reaches adulthood at 84-92 g, is always chubby and falls
  sick about 21 times a life (casual: 5). At 1 g a meal, won games kept every pet underweight,
  so meals add 2 g. Tune the bands and the burn rate, not the logic.

### 2.8 Generations

A pet that dies of **old age** leaves an egg. Its heir starts a new life in the same family,
so a well-kept line can go on as long as the player keeps it. A pet that dies of poor health
leaves no egg.

- **The egg** belongs to the dead pet until it is hatched (`heir_hatched` is false). The
  memorial offers "Hatch Mochi's egg" (`e`) beside "New egg", and the pet select screen offers
  `e` on a dead pet whose egg is waiting. An egg can be hatched once.
- **Hatching the heir** opens the name prompt with the name filled in as the next in line
  ("Mochi" → "Mochi II" → "Mochi III", counting from the parent's numeral; left empty if it
  wouldn't fit in 16 characters) and the species fixed to the parent's (`↑`/`↓` do nothing).
  The heir is a new pet with its own file and counts towards the 9-pet limit (refused at 9,
  saying so; archiving another pet makes room).
- **What it inherits:** the species; `generation` = parent's + 1; `ancestors` = the parent's
  ancestors plus a record of the parent (name, birth time, generation, adult form, lifespan;
  name and birth time together identify it); and a head
  start of discipline 25 if the parent was a good adult (`Balance.heir_discipline`), else 0.
  Stats, weight and lifespan are fresh. The heir's RNG is seeded from the parent's, so a line
  started with `--seed` is reproducible.
- **Lineage travels with the heir:** the ancestor records are copied into the heir's save, so
  archiving (or losing) an ancestor's file never breaks the family line.
- **Archiving** a dead pet whose egg is still waiting says so in the confirmation ("Its egg
  will be archived with it"); an archived egg can't be hatched.
- **Showing it:** the status panel and the pet select details show "Generation 3 · founded by
  Mochi" from generation 2 on, and the pet select details say "left an egg (e to hatch)"; the
  memorial lists the family line under the name ("… → Bao → Mochi II → Mochi III": the last
  three ancestors, then the pet) and shows one first fewer to stay within 60×20. `e` is only
  offered while an egg is waiting.
- **One save file** (`--save-path`): there is no pet list, so the heir takes the parent's place
  in the same file (the parent lives on in its family line and the file's backup).
- **If tama stops mid-hatch:** the heir is saved before the parent; an heir whose newest
  ancestor is this pet means its egg has hatched, whatever the parent's file says.
- **Balance:** `tools/generations.py` keeps lines going for a month: with 14–18-day lives every
  player profile reaches generation 2 and no line ends.
- **Events:** `LaidEgg` (on the parent, at death of old age) and `HeirHatched(heir_name)` (on
  the parent's journal, §2.9).

### 2.9 Journal

Each pet keeps a journal: a diary of its life written from the domain's events, so it records
what happened while tama was closed as well as while it was open.

- **Entries** have the local date and time, the pet's age and a line of text
  (`3 Nov 14:05  1d 2h   First win at Four in a Row`). The time comes from the pet's own clock:
  each event's age is measured from the pet's last simulated step before it, so entries written
  during a catch-up keep the times they happened, even when a pet sitter covered the rest
  (§2.5). They come in three kinds:
  - **Life:** hatched (and from whose egg, §2.8), evolved, its adult form, became an elder,
    went on and came back from holiday, laid an egg, its heir hatched, died (with cause).
  - **Firsts:** first meal, snack, tantrum, sickness, care mistake, game won (per game), visit
    (§3.2) and trick learned (§2.10).
  - **Moments:** recovered from sickness, care mistakes after the first (with the reason),
    tantrums caught or ignored, visits and their results, and round-number tallies (the 10th,
    50th, 100th, 250th, 500th and 1000th game won or meal eaten).
- **Tallies** are kept for the whole life: meals, snacks, games won/drawn/lost per game,
  tantrums caught/ignored, sicknesses, medicine doses, poops cleaned, holidays, visits and care
  mistakes.
- **Bounded:** life and first entries are always kept; moments are kept for the last 100, so
  a save stays small however long the pet lives.
- **Showing it:** `j` opens the journal: the tallies at the top, then entries newest first
  (`↑`/`↓`, `PgUp`/`PgDn`, `Home`/`End` scroll; `Esc` or `j` closes; "Nothing written yet."
  when empty). It works on holiday and for dead pets (`j` on the memorial). The memorial sets
  the gravestone beside the **highlights**: the story (hatched and each stage; the death is
  said above it, holidays are left out), up to three happy firsts (meal, snack, win, tantrum,
  sickness; not the first care mistake) and one line in numbers ("82 meals, 3 snacks, 40
  wins"), so it fits 60×20. `tama journal` prints it from the shell (§8).
- Looking at a journal never changes it: the pet select screen, `--status` and `tama journal`
  build entries for the in-memory catch-up but don't save them; the pet's own session writes
  them when it next catches up for real (the same events, so the same entries).

### 2.10 Tricks

A disciplined pet learns tricks. They are for show: nothing in the game depends on them.

- **Known tricks follow current discipline:** 25 wave, 50 spin, 75 dance, 100 bow
  (`Balance.trick_thresholds`), from CHILD stage on. Discipline lost to ignored tantrums can
  drop the pet below a threshold, and it forgets that trick until it climbs back.
- **Learning:** when discipline rises past a threshold, the pet shows the new trick at once
  and a toast says "Mochi learned to spin!" (`LearnedTrick(trick)`; it is a journal first the
  first time ever, "Learned to spin"). An heir that starts with discipline (§2.8) learns its
  trick the moment it grows into a child.
- **Showing off:** an idle pet that is awake, content (happiness ≥ 75,
  `Balance.show_off_happiness`), not sick or
  misbehaving and with the lights on now and then (every 1–3 min, chosen by the cosmetic UI
  RNG, like blinking) performs one of its tricks in place of a blink. With reduced motion it
  never does.
- **Status panel:** lists the tricks it knows ("Tricks: wave, spin").

## 3. Actions (player verbs)

| Key | Action | Effect | Refused when |
| --- | --- | --- | --- |
| `f` | Feed → submenu: **Meal** / **Snack** | Meal: hunger +30, weight +2g. At hunger ≥ 95 the pet eats it anyway but is **stuffed**: hunger 100, weight +4g, happiness −5. Snack: happiness +15, hunger +5, weight +2g. >3 snacks/hour → may get sick. Weight matters (§2.7). | Asleep, egg, dead, misbehaving |
| `p` | Play → choose a mini-game (§3.1) | Win: happiness +20, energy −10, weight −1g. Draw: happiness +10, energy −10. Lose: happiness +5, energy −10. | Asleep, misbehaving, energy < 10 |
| `c` | Clean | Removes all poop, hygiene → 100 | — |
| `m` | Medicine | Cures one dose of sickness | Asleep, not sick |
| `l` | Lights on/off | Toggles lights | — |
| `d` | Discipline | If pet is "misbehaving" (random attention call with no real need): discipline +25 (+0 for a tantrum from being woken); passing a trick threshold teaches a trick (§2.10). Otherwise: happiness −20. | Asleep |
| `w` | Wake | Wakes a sleeping pet early (§2.4): happiness −20, energy −20, a tantrum, stays up 30 min. Not shown in the footer (no room); listed in Help. | Awake, egg |
| `s` | Status | Opens stats panel (hearts/bars, age, weight, stage) | — |
| `h` | Holiday | Puts a settled pet on holiday (frozen in time), or brings it back (§2.6) | Egg, dead, (to pause) any attention call |
| `t` | Tamas | Saves, then opens the pet select screen to switch pets (§6.1) | — |
| `v` | Visit | Invites another of your pets over to play (§3.2). Not in the footer; listed in Help. | Asleep, egg, dead, on holiday, sick, misbehaving, energy < 10, no other pets |
| `j` | Journal | Opens the pet's journal (§2.9). Not in the footer; listed in Help. | — |
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

### 3.2 Visits

With several pets (§6.1), the open pet can invite another one round to play.

- **Inviting:** `v` checks the host's refusals (§3), then opens a **visit picker** listing the
  other pets. Those that can't come are greyed out with the reason: an egg, dead, on holiday,
  asleep, sick, misbehaving, too tired (energy < 10), can't be read, or open in another tama.
  The same rule ends a visit (below), so a sick pet stays home rather than leaving at once.
  `↑`/`↓` + `Enter` or `1`–`9` invite one; `Esc` closes. With no other pets, `v` just says so.
- **The guest** is loaded like any pet (capped catch-up; its events go into its own journal),
  locked for the length of the visit, and lives in real time beside the host: both pets are
  ticked every second and both save on the usual autosave policy.
- **Visit screen:** both pets on the stage, host on the left, guest on the right, each with
  its name under it; they greet each other (`happy`). Each pet's happiness rises by 10
  (`Balance.visit_happiness`) unless it had a visit in the last 4 h (`Balance.visit_cooldown`),
  so visits can't be farmed. Keys: `g` (or `Enter`) watch them play, `s` either pet's status
  (it asks whose: `1` host, `2` guest), `Esc` or `v` end the visit.
- **Watching them play:** a choice of Four in a Row or Tic-Tac-Toe (Left or Right needs a
  player). The host moves first; each pet picks its moves as in §3.1, with its own stage's
  mistake chance and its own RNG, one move about every 0.8 s (`Space` skips to the end;
  with reduced motion the game plays out at once). The board shows the host's pieces in
  `$tama-piece-player` and the guest's in `$tama-piece-pet` (monochrome `●`/`○`). When it ends,
  each pet gets the `p` row's effect from its own side (win/draw/loss, energy −10) and reacts.
  `Esc` mid-game abandons it with no effect. They can play again while both have energy ≥ 10.
- **Ending:** `Esc`/`v` ends the visit; the guest is saved, unlocked and "went home" (toast).
  The visit also ends by itself, abandoning any game in progress, as soon as either pet can no
  longer visit (falls asleep, gets sick, starts misbehaving, dies, runs out of energy), with a
  toast saying why ("Pip got sleepy and went home", or "Mochi got sleepy, so Pip went home"
  when it's the host). `t`, `q` and SIGTERM/SIGHUP end the visit first, saving both pets; so
  does tama stopping for any other reason, a crash included.
- **Care during a visit:** the visit screen has only the keys above; the care actions wait on
  the main screen, where they apply to the host once the visit ends. To look after the guest,
  end the visit and switch to it. The guest's attention calls count in the header's
  `⚠ +N` as usual (§6.1).
- **Events:** `Visited(friend, cheered)` on both pets (once per visit; `cheered` if it gave
  happiness) and `PlayedWith(friend, game,
  result)` per finished game, which the journal records ("Beat Pip at Four in a Row").
- **Balance:** `tools/games.py` also plays pet against pet for every pair of stages, and the
  result is reported (an adult should usually beat a baby).

## 4. Attention calls

A pet on holiday raises no calls (§2.6). Otherwise, when a need drops below 25, the pet
becomes sick, poops, misbehaves, or its weight leaves the healthy band (§2.7), raise an
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
  lights off (via Textual CSS class on the stage). Its background follows the player's local
  time of day: **dawn** (the hour after `night_end`), **day**, **dusk** (the hour before
  `night_start`) and **night**, using the UI colours `stage-dawn`, `stage-day`, `stage-dusk` and
  `stage-night` (`assets/ui.toml`, dark and light; species may override). The phase is a pure
  function of local time and the night window, re-checked every tick; lights-off dimming
  applies on top, and with `NO_COLOR` there is no tint. It shows the player's time, so it
  changes for a pet on holiday too.
- **Two pets on stage** during a visit (§3.2): host left, guest right, each wandering in its
  own half. Both must fit side by side at 60×20; when a half is too narrow for its sprite to
  wander, the pets stand still instead.
- **Footer:** key bindings (Textual `Footer`).
- **Screens:** `PetSelectScreen` (§6.1), `NewPetScreen` (name entry + egg), `MainScreen`,
  `StatusScreen` (modal),
  `FeedMenu` (modal), `GameSelectScreen` (modal), one modal per mini-game (`LeftRightScreen`,
  `FourInARowScreen`, `TicTacToeScreen`), `AwaySummaryScreen` (modal), `MemorialScreen`,
  `HelpScreen` (modal), `ErrorScreen` (corrupt save recovery), `JournalScreen` (modal, §2.9),
  `VisitPickerScreen` (modal) and `VisitScreen` (§3.2). Every game fits the minimum
  60×20 terminal with the pet beside the board; a pet-vs-pet game shows both pets, one each
  side of the board, as small idle sprites (the pet's own art at half size).

### 5.2 Animation

- Sprites are colour pixel art rendered with block characters (`█ ▀ ▄ ░ ▒ ▓`, two pixels per
  cell; see ADR 0003). Each species has its own palette with colours for dark and light themes,
  and may theme the UI's colours (ADR 0004). One file per `(species, variant, stage,
  animation)`; animations include at least
  `idle` (2–4 frames, ~2 fps), `blink`, `eat`, `play`, `happy`, `refuse`, `sleep`, `sick`,
  `clean`, `evolve`, `hatch`, `wobble` (egg), `dead`, `misbehave` (a tantrum loop: angry
  brows, stamping and shouting), the poses `look_left`/`look_right` (the Left/Right game),
  and from CHILD on the tricks `trick_wave`, `trick_spin`, `trick_dance` and `trick_bow`
  (one-shot, §2.10). Adults and elders have a third variant, `chubby` (§2.7), beside `good`
  and `scruffy`: a rounder body, drawn by each species' generator. The feed menu shows small
  animated meal and snack sprites.
- Board games: while "thinking" the pet alternates `look_left`/`look_right` (~0.6 s); a dropped
  Four in a Row piece falls row by row (~40 ms per row). With reduced motion the pet's move
  appears at once and pieces land without falling.
- Idle animation includes random blinks, small horizontal wandering across the stage and, for
  a content pet that knows some, the odd trick (§2.10).
- One-shot animations (eat, refuse, …) play once, then return to the state-appropriate loop.
- Frame timing is driven by Textual `set_interval`; the animation *selection* is a pure
  function of pet state (testable without a UI).
- Status indicators (Zzz, sickness, poop, and a suitcase for a pet on holiday) are small pixel
  sprites under the pet.
- The egg on the name prompt wobbles; hatching cracks the egg and the baby pops out; evolving
  flashes the new form.
- Theme: uses Textual themes (config `theme`); must look good on both dark and light terminals.
  Respect `NO_COLOR` (monochrome sprites). A `--reduced-motion` flag (and config option) shows
  static key frames only: no reactions, blinking, wandering or tricks.

## 6. Persistence

- Location: one file per pet in `platformdirs.user_data_path("tama") / "pets/"` (§6.1);
  `--save-path PATH` or the `TAMA_SAVE_PATH` env var (CLI wins) instead plays exactly one save
  file, outside the pet list (handy for experiments and tests). In this section, `save.json`
  stands for any one pet's file.
- Format: JSON, human-readable, Pydantic model with `schema_version: int` (v3 adds
  `paused_since`; the v2 → v3 migration sets it to empty, i.e. not on holiday. v4 adds
  `stay_awake` and `woken_tantrum`; the v3 → v4 migration sets them to zero and false.
  v5 adds `weight_progress` and `timers.weight` (migrated to zero). v6 adds the journal (§2.9); the v5 → v6
  migration starts it with one life entry, "Journal started", and zero tallies, since the
  past can't be reconstructed. v7 adds `generation`, `ancestors` and `heir_hatched` (migrated
  to 1, none and false; a pet that already died of old age before v7 has no egg to hatch, so
  `heir_hatched` is true for it). v8 adds `last_visit` (migrated to empty: never visited).
  v9 lets the journal say a trick was learned (§2.10); a v8 save needs no change, but the
  version moves on so an older tama calls a v9 save newer rather than corrupt.
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
- **Pet select screen:** one row per pet, each simulated up to now in memory (not saved), the
  last played first, then by name, and pets that have passed away after all the rest (the
  last-played pet stays pre-selected even then):
  name (cut short with `…` past 11 characters), stage, age and a mark: `⚠` needs care, `⏸`
  on holiday, `✝` passed away, `?` can't be read. Beside the list, the highlighted pet's
  sprite (idle, asleep, or its gravestone) and details: full name, stage and species, and
  the `⚠` reasons, `⏸ on holiday since <date>`, "passed away (…) at <age>" or "can't be
  read". (One sprite beside the list, rather than one per row, fits nine pets in 60×20.) Keys: `↑`/`↓` or `1`–`9` select, `Enter` plays,
  `n` hatches a new egg (name prompt; refused at 9 pets, saying so), `e` hatches a dead pet's
  waiting egg (§2.8; the details say "left an egg"), `a` archives the
  selected pet (dead pets only, after a `y`/`n` confirmation), `Esc`/`q` quit. An unreadable
  pet opens the `ErrorScreen` for that file only; the other pets are unaffected.
- **Switching while playing:** `t` on the main screen saves the current pet and opens the pet
  select screen. The UI colours follow whichever pet is open (ADR 0004).
- **Other pets needing care:** while one pet is open, the header also shows `⚠ +N` when N
  other living pets need attention (re-checked every minute from their saves, read-only); the
  bell does not ring for other pets.
- **Death:** the memorial's "new egg" (or "hatch Mochi's egg", §2.8) adds a new pet; the dead
  one stays in the list as a memorial until archived. **Archiving** moves its files to `pets/archive/` (never deleted),
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
                           # below, last-played pet first and marked `*`, then by name, and
                           # pets that have passed away last (even the last played). On a
                           # terminal it is coloured (names bold; needs green ≥ 50, yellow
                           # ≥ 25, red below; "needs:" bold red; holiday cyan; the dead
                           # dimmed) in the terminal's own ANSI colours; plain when piped or
                           # with NO_COLOR;
                           # pets on holiday read "Mochi · adult owl · on holiday since 3 Nov";
                           # with --pet, just that pet. Exit 0 ok, 1 no pets yet,
                           # 2 if any pet's save is unreadable (its line says so) / bad config
tama --list-species        # the animals that have art
tama journal               # the last-played pet's journal as plain text (§2.9), as of now
                           # (read-only, like --status); --pet NAME for another pet.
                           # Exit codes as --status
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
