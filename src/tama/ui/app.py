"""The Textual application."""

import asyncio
import logging
import signal
from typing import ClassVar, override

from textual.app import App
from textual.binding import Binding, BindingType

from tama.errors import SaveError, SaveWriteError
from tama.infra.clock import Clock
from tama.persistence.repository import SaveRepository
from tama.services.session import GameSession, SessionSettings
from tama.ui.colours import Mode
from tama.ui.screens.main import MainScreen
from tama.ui.screens.new_pet import NewPetScreen
from tama.ui.sprites import DEFAULT_SPECIES
from tama.ui.theme import css_variables, ui_palette
from tama.ui.widgets.pet_view import ViewOptions

logger = logging.getLogger(__name__)

EXIT_ERROR = 2
_TERMINATION_SIGNALS = ("SIGTERM", "SIGHUP")


class TamaApp(App[None]):
    """Loads or hatches a pet, ticks it every second, and saves on the way out.

    Args:
        repo: Where the game is saved.
        clock: Source of time (a ``ScaledClock`` for ``--speed``, a ``FakeClock`` in tests).
        settings: Balance, time zone, offline cap and autosave policy.
        seed: RNG seed for a newly created pet (``None`` for a random one).
        start_new: Hatch a new pet even if a save exists (``--new``).
        tick_interval: Seconds between ticks; ``None`` disables the timer (tests tick by hand).
        handle_signals: Save and exit on SIGTERM/SIGHUP (POSIX only).
        bell: Ring the terminal bell on new attention calls (used from M6).
        view: How the pet is drawn (colour, animation, reduced motion).
        theme: Textual theme name from the config (unknown names are ignored).
    """

    CSS_PATH = "app.tcss"
    TITLE = "tama"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit_game", "Quit", show=False, priority=True)
    ]

    def __init__(  # noqa: PLR0913 - explicit dependencies, all keyword-only
        self,
        *,
        repo: SaveRepository,
        clock: Clock,
        settings: SessionSettings,
        seed: int | None = None,
        start_new: bool = False,
        tick_interval: float | None = 1.0,
        handle_signals: bool = True,
        bell: bool = False,
        view: ViewOptions | None = None,
        theme: str | None = None,
    ) -> None:
        """Wire the app to its dependencies."""
        super().__init__()
        self._repo = repo
        self._clock = clock
        self._settings = settings
        self._seed = seed
        self._start_new = start_new
        self._tick_interval = tick_interval
        self._handle_signals = handle_signals
        self.bell_enabled = bell
        self.view = view or ViewOptions()
        if theme is not None:
            if theme in self.available_themes:
                self.theme = theme
            else:
                logger.warning("Unknown theme %r; using the default", theme)
        self._quit_failed = False
        self._installed_signals: list[signal.Signals] = []
        self.session: GameSession | None = None
        self.main: MainScreen | None = None

    species: str = DEFAULT_SPECIES
    """Whose UI colours (``base.toml`` ``[ui]``) to use; set before CSS is built."""

    @override
    def get_theme_variable_defaults(self) -> dict[str, str]:
        """The ``$tama-*`` UI colours for the active theme's mode (ADR 0004)."""
        theme = self.current_theme
        return css_variables(
            ui_palette(self.species),
            mode=Mode.of(dark=theme.dark),
            theme_colours=theme.to_color_system().generate(),
        )

    def on_mount(self) -> None:
        """Load the saved pet, or ask for a name for a new one."""
        if self._handle_signals:
            self._install_signal_handlers()
        if self._repo.exists() and not self._start_new:
            self._load()
        else:
            self.push_screen(NewPetScreen(self.view), self._hatch)

    def on_unmount(self) -> None:
        """Remove signal handlers."""
        loop = asyncio.get_running_loop()
        for sig in self._installed_signals:
            loop.remove_signal_handler(sig)

    def tick(self) -> None:
        """Bring the pet up to date and redraw it (the main screen's timer does this)."""
        if self.main is not None:
            self.main.tick()

    def action_quit_game(self) -> None:
        """Save and quit. If saving fails, warn once; quitting again exits without saving."""
        if self.session is not None and not self._quit_failed:
            try:
                self.session.close()
            except SaveWriteError as exc:
                logger.exception("Could not save on quit")
                self._quit_failed = True
                self.notify(
                    f"Couldn't save: {exc}\nQuit again to exit without saving.",
                    severity="error",
                    timeout=10,
                )
                return
        self.exit()

    def save_and_exit(self) -> None:
        """Save if possible and exit (on a termination signal there's no one to ask)."""
        if self.session is not None:
            try:
                self.session.close()
            except SaveWriteError:
                logger.exception("Could not save on termination signal")
        self.exit()

    # --- Internals ------------------------------------------------------------------------

    def _load(self) -> None:
        try:
            loaded = GameSession.load(repo=self._repo, clock=self._clock, settings=self._settings)
        except SaveError as exc:
            logger.exception("Could not load the save")
            self.exit(return_code=EXIT_ERROR, message=f"tama: could not load your pet: {exc}")
            return
        self._start(loaded.session)
        if loaded.recovered_from_backup:
            self.notify("Your save was damaged; recovered from the backup.", severity="warning")
        if loaded.away.summary:
            self.notify(
                "\n".join(loaded.away.summary),
                title="While you were away",
                timeout=15,
            )

    def _hatch(self, name: str | None) -> None:
        if name is None:
            self.exit()
            return
        try:
            session = GameSession.create(
                name, repo=self._repo, clock=self._clock, settings=self._settings, seed=self._seed
            )
        except SaveWriteError as exc:
            self.exit(return_code=EXIT_ERROR, message=f"tama: could not save your new pet: {exc}")
            return
        self._start(session)

    def _start(self, session: GameSession) -> None:
        self.session = session
        self.main = MainScreen(session, tick_interval=self._tick_interval, view=self.view)
        self.push_screen(self.main)

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for name in _TERMINATION_SIGNALS:
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                loop.add_signal_handler(sig, self.save_and_exit)
            except (NotImplementedError, RuntimeError):  # Windows / non-main thread
                continue
            self._installed_signals.append(sig)
