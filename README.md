# tama

A terminal virtual pet. Hatch it, feed it, play with it, clean up after it — and come back
later to find it has been living while you were away.

> 🚧 In development. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for progress.

## Install & run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run tama
```

## Playing

Keep up to nine pets. Each lives in real time whether or not tama is open, so check in on them.

```sh
uv run tama                  # pick a pet (or hatch your first one)
uv run tama --pet mochi      # open one pet straight away (any case, or the start of a name)
uv run tama --new            # hatch another egg; --species owl for a different animal
uv run tama --status         # one line per pet, as of now (handy in a shell prompt)
uv run tama --pause          # going away? put every settled pet on holiday (--resume after)
```

In the game, `?` lists the keys: `f` feed, `p` play, `c` clean, `m` medicine, `l` lights,
`d` discipline, `h` holiday, `t` switch pets, `q` save and quit.

Pets are saved in your user data directory (`TAMA_DATA_DIR` to move it). An older single
`save.json` is moved into the pet list automatically. `--save-path FILE` plays exactly one
save file instead, outside the pet list.

## Development

See [`CLAUDE.md`](CLAUDE.md) for commands and conventions. Design docs are in [`docs/`](docs/).

## License

MIT
