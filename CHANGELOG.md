# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-05

The first release.

### Added

- **A pet that lives in real time**: hunger, happiness, energy, hygiene, health and discipline;
  poop, sickness and medicine; sleep, lights and a night window in your local time; care
  mistakes; life stages from egg to elder, and good, scruffy or chubby adult forms decided by
  how it was raised. Time away is simulated on the next launch, capped at 72 hours (a "pet
  sitter" covers the rest), with a summary of what happened.
- **Weight**: a healthy band per stage; snacks fatten, games trim, and a heavy teen grows into a
  chubby adult.
- **Discipline and tantrums**: misbehaviour to catch, a grumpy pet if you wake it early, and
  tricks (wave, spin, dance, bow) for a well-disciplined pet, shown off when it is content.
- **Mini-games**: Left/Right, Four in a Row and Tic-Tac-Toe against the pet, which plays
  better as it grows up.
- **Several pets**: up to nine, a pet list with who needs care, `t` to switch, archiving the
  dead, and `⚠ +N` when another pet needs you.
- **Visits** (`v`): invite another of your pets over and watch the two of them play a board
  game.
- **Holiday** (`h`, `tama --pause`/`--resume`): freeze a settled pet in time while you are
  away.
- **Journal** (`j`, `tama journal`): each pet's life story and lifetime tallies, written from
  what happened even while tama was closed; highlights on the memorial.
- **Generations**: a pet that dies of old age leaves an egg; its heir (Mochi II, Mochi III …)
  carries on the family line, of the same species, with a little discipline from a good
  parent.
- **Colour pixel-art sprites** for three species (tama, owl, bear), with palettes for dark and
  light themes, a monochrome look for `NO_COLOR`, idle blinking and wandering, and a reaction
  to every action; `--reduced-motion` for static frames.
- **A stage that follows the time of day**: tinted for dawn, day, dusk and night.
- **Command line**: `tama`, `--pet`, `--new`, `--species`, `--list-species`, `--status` (one
  coloured line per pet, for shell prompts), `--pause`, `--resume`, `journal`,
  `--save-path`, `--quiet`, `--version`; an optional `config.toml` (bell, reduced motion,
  night window, offline cap, theme).
- **Safe saves**: one versioned JSON file per pet, written atomically with a `.bak`, migrated
  from every older schema, recovered from the backup when damaged, and locked so a pet can't
  be open in two windows.

[Unreleased]: https://github.com/BodneyC/tama/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/BodneyC/tama/releases/tag/v1.0.0
