"""Smoke-test an *installed* tama: hatch a pet through the real TUI, headless, then quit.

    python -I tools/smoke.py DATA_DIR

Run it with the Python of an environment where only the built wheel is installed (CI does,
after ``uv build``): it imports ``tama`` from that install, never from ``src/``, so it proves
the wheel carries its sprites, palettes and stylesheet. It leaves the pet in ``DATA_DIR`` for
``tama --status`` to find. Exits non-zero, saying why, if anything is off.
"""

import asyncio
import sys
from pathlib import Path

from tama.infra.clock import SystemClock
from tama.persistence.roster import PetRoster
from tama.services.library import PetLibrary
from tama.services.session import SessionSettings
from tama.ui.app import TamaApp
from tama.ui.screens.main import MainScreen


async def hatch_and_quit(data_dir: Path) -> None:
    """Name an egg Mochi, feed it from the menu, open the status and journal, and quit."""
    clock, settings = SystemClock(), SessionSettings()
    library = PetLibrary(PetRoster(data_dir), clock=clock, settings=settings)
    app = TamaApp(library=library, clock=clock, settings=settings, handle_signals=False)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.press(*"Mochi", "enter")
        await pilot.pause()
        if not isinstance(app.screen, MainScreen):
            raise SystemExit(f"smoke: expected the main screen, got {app.screen!r}")
        await pilot.press("f", "1", "s", "escape", "j", "escape", "q")
        await pilot.pause()
    if app.return_code not in (0, None):
        raise SystemExit(f"smoke: tama quit with {app.return_code}")


def main() -> None:
    """Hatch, play and quit in ``sys.argv[1]``."""
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    import tama  # noqa: PLC0415 - where it came from is the point

    if "site-packages" not in (tama.__file__ or ""):
        raise SystemExit(f"smoke: tama was imported from {tama.__file__}, not an install")
    asyncio.run(hatch_and_quit(Path(sys.argv[1])))
    print(f"smoke: hatched Mochi with tama {tama.__version__}")  # noqa: T201 - a CLI tool


if __name__ == "__main__":
    main()
