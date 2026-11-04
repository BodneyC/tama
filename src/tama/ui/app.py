"""The Textual application."""

import asyncio
import logging
import signal
from functools import partial
from typing import ClassVar, override

from textual.app import App
from textual.binding import Binding, BindingType

from tama.domain.pet import DEFAULT_SPECIES
from tama.domain.stage import LifeStage
from tama.errors import InvalidArgumentError, SaveError, SaveWriteError
from tama.infra.clock import Clock
from tama.persistence.repository import SaveRepository
from tama.persistence.roster import PetFile
from tama.services.library import PetLibrary
from tama.services.session import GameSession, LoadedSession, SessionSettings
from tama.ui.colours import Mode
from tama.ui.heir_flow import ask_for_heir
from tama.ui.library_flow import LibraryFlow
from tama.ui.screens.away import AwaySummaryScreen
from tama.ui.screens.error import ErrorScreen
from tama.ui.screens.main import MainScreen
from tama.ui.screens.memorial import MemorialChoice, MemorialScreen
from tama.ui.screens.new_pet import NewPet, NewPetScreen
from tama.ui.theme import css_variables, ui_palette
from tama.ui.widgets.pet_view import ViewOptions

logger = logging.getLogger(__name__)

EXIT_ERROR = 2
_TERMINATION_SIGNALS = ("SIGTERM", "SIGHUP")


class TamaApp(App[None]):
    """Opens or hatches a pet, ticks it every second, and saves on the way out.

    It plays either one save file (``repo``: ``--save-path``) or a library of several pets
    (``library``: SPEC §6.1), where it offers the pet select screen and ``t`` to switch.

    Args:
        repo: The single save file to play (mutually exclusive with ``library``).
        library: Several pets (mutually exclusive with ``repo``).
        open_pet: In a library, the pet to open straight away (``--pet``).
        clock: Source of time (a ``ScaledClock`` for ``--speed``, a ``FakeClock`` in tests).
        settings: Balance, time zone, offline cap and autosave policy.
        seed: RNG seed for a newly created pet (``None`` for a random one).
        start_new: Hatch a new pet (``--new``): in a library, an additional one.
        new_pet_species: The animal the name prompt starts on (``--species``).
        tick_interval: Seconds between ticks; ``None`` disables the timer (tests tick by hand).
        handle_signals: Save and exit on SIGTERM/SIGHUP (POSIX only).
        bell: Ring the terminal bell once for each new attention call.
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
        repo: SaveRepository | None = None,
        library: PetLibrary | None = None,
        open_pet: PetFile | None = None,
        clock: Clock,
        settings: SessionSettings,
        seed: int | None = None,
        start_new: bool = False,
        new_pet_species: str = DEFAULT_SPECIES,
        tick_interval: float | None = 1.0,
        handle_signals: bool = True,
        bell: bool = False,
        view: ViewOptions | None = None,
        theme: str | None = None,
    ) -> None:
        """Wire the app to its dependencies."""
        super().__init__()
        if (repo is None) == (library is None):
            raise InvalidArgumentError("give the app either one save file or a pet library")
        self._repo = repo
        self.library = library
        self.flow = LibraryFlow(self, library) if library is not None else None
        self.open_pet = open_pet
        self._clock = clock
        self._settings = settings
        self._seed = seed
        self.start_new = start_new
        self.species = new_pet_species
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
    """Whose UI colours (``base.toml`` ``[ui]``) to use: the new pet's, then the open pet's."""

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
        """Open a pet, offer the pet list, or ask for a name for a new one."""
        if self._handle_signals:
            self._install_signal_handlers()
        if self.flow is not None:
            self.flow.launch()
        elif self._repo is not None and self._repo.exists() and not self.start_new:
            self._load_single(self._repo)
        else:
            self.ask_for_new_pet()

    def on_unmount(self) -> None:
        """Remove signal handlers and let go of the open pet."""
        loop = asyncio.get_running_loop()
        for sig in self._installed_signals:
            loop.remove_signal_handler(sig)
        if self.library is not None:
            self.library.close()

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

    # --- One save file --------------------------------------------------------------------

    def _load_single(self, repo: SaveRepository) -> None:
        try:
            loaded = GameSession.load(repo=repo, clock=self._clock, settings=self._settings)
        except SaveError as exc:
            logger.exception("Could not load the save")
            self.push_screen(ErrorScreen(exc), partial(self._recover_single, repo, exc))
            return
        self.show_loaded(loaded)

    def _recover_single(
        self,
        repo: SaveRepository,
        error: SaveError,
        start_new: bool | None,  # noqa: FBT001 - screen result
    ) -> None:
        if not start_new:
            self.exit(return_code=EXIT_ERROR, message=f"tama: could not load your pet: {error}")
            return
        try:
            GameSession.discard_save(repo=repo, clock=self._clock)
        except SaveWriteError as exc:
            self.exit(return_code=EXIT_ERROR, message=f"tama: {exc}")
            return
        self.ask_for_new_pet()

    # --- Several pets (SPEC §6.1; see library_flow.py) -----------------------------------

    def on_main_screen_switch_pet(self, _message: MainScreen.SwitchPet) -> None:
        """Save the open pet and go back to the pet list (``t``)."""
        if self.flow is None or self.library is None or self.session is None:
            return
        try:
            self.session.save()
        except SaveWriteError as exc:
            self.notify(f"Couldn't save: {exc}", severity="error")
            return
        previous = self.library.open_file
        self._close_main()
        self.session = None
        self.library.close()
        self.flow.show_pets(selected=previous)

    # --- Hatching, playing and dying ------------------------------------------------------

    def ask_for_new_pet(self) -> None:
        """Show the name prompt for a new egg (in a library, names must not clash)."""
        library = self.library
        taken = library.name_taken if library is not None else None
        self.push_screen(NewPetScreen(self.view, self.species, taken=taken), self._hatch)

    def _hatch(self, chosen: NewPet | None) -> None:
        if chosen is None:
            if self.flow is not None and self.flow.library.summaries():
                self.flow.show_pets()
            else:
                self.exit()
            return
        try:
            if self.library is not None:
                self.library.close()
                session = self.library.hatch(chosen.name, species=chosen.species, seed=self._seed)
            else:
                assert self._repo is not None  # noqa: S101 - one of the two is always set
                session = GameSession.create(
                    chosen.name,
                    repo=self._repo,
                    clock=self._clock,
                    settings=self._settings,
                    seed=self._seed,
                    species=chosen.species,
                )
        except SaveWriteError as exc:
            self.exit(return_code=EXIT_ERROR, message=f"tama: could not save your new pet: {exc}")
            return
        self._start(session)

    def show_loaded(self, loaded: LoadedSession) -> None:
        """Play a loaded pet, saying what happened while it was away."""
        self._start(loaded.session)
        if loaded.recovered_from_backup:
            self.notify("Your save was damaged; recovered from the backup.", severity="warning")
        if loaded.away.summary or loaded.away.pet_sitter:
            self.push_screen(AwaySummaryScreen(loaded.session.pet.name, loaded.away))

    def start(self, session: GameSession) -> None:
        """Play ``session``'s pet (or show its memorial if it has died)."""
        self._start(session)

    def _start(self, session: GameSession) -> None:
        self.session = session
        if session.pet.species != self.species:
            self.species = session.pet.species
            self.refresh_css()  # the species may theme the UI colours
        if session.pet.stage is LifeStage.DEAD:
            self._show_memorial()
            return
        library = self.library
        self.main = MainScreen(
            session,
            tick_interval=self._tick_interval,
            view=self.view,
            bell=self.bell_enabled,
            others=library.others_needing_care if library is not None else None,
        )
        self.push_screen(self.main)

    def on_main_screen_pet_died(self, _message: MainScreen.PetDied) -> None:
        """Replace the main screen (and any dialog over it) with the memorial."""
        self._close_main()
        self._show_memorial()

    def _close_main(self) -> None:
        if self.main is not None:
            while self.screen is not self.main:
                self.pop_screen()
            self.pop_screen()
            self.main = None

    def show_memorial(self) -> None:
        """Show the open (dead) pet's memorial."""
        self._show_memorial()

    def _show_memorial(self) -> None:
        if self.session is not None:
            memorial = MemorialScreen(
                self.session.pet, self.view, self.session.journal, self.session.tz
            )
            self.push_screen(memorial, self._after_memorial)

    def _after_memorial(self, choice: MemorialChoice | None) -> None:
        if choice in (None, MemorialChoice.QUIT) or self.session is None:
            self.action_quit_game()
            return
        if choice is MemorialChoice.HEIR:
            library = self.library
            ask_for_heir(self, self.session.pet, library.open_file if library else None)
            return
        self.species = self.session.pet.species
        if self.flow is not None:
            self.flow.new_pet_if_room()  # the dead pet stays listed as a memorial
        else:
            self.ask_for_new_pet()

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
