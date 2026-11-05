"""Choose a mini-game (SPEC §3.1)."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from tama.domain.minigames import GameKind
from tama.ui.screens.games import GAMES


class GameSelectScreen(ModalScreen[GameKind | None]):
    """Lists the games; dismisses with the chosen one, or ``None`` if closed."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Cancel"),
        *(
            Binding(str(number), f"choose({number})", show=False)
            for number in range(1, len(GameKind) + 1)
        ),
    ]

    def __init__(
        self,
        last: GameKind | None = None,
        *,
        kinds: tuple[GameKind, ...] = tuple(GameKind),
        title: str = "Play a game",
    ) -> None:
        """Offer ``kinds`` (every game by default), pre-selecting ``last`` if it is one."""
        super().__init__()
        self._kinds = kinds
        self._last = last if last in kinds else kinds[0]
        self._title = title

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static(self._title, classes="dialog-title")
            yield OptionList(
                *(
                    Option(f"{number}  {GAMES[kind][0]:<14}{GAMES[kind][1]}", id=kind.value)
                    for number, kind in enumerate(self._kinds, start=1)
                ),
                id="games",
            )
            hint = f"↑↓ Enter or 1-{len(self._kinds)} to play · Esc to cancel"
            yield Static(hint, classes="dialog-hint")

    def on_mount(self) -> None:
        """Highlight the last game played."""
        games = self.query_one(OptionList)
        games.highlighted = self._kinds.index(self._last)
        games.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Play the selected game."""
        self.dismiss(GameKind(str(event.option.id)))

    def action_choose(self, number: int) -> None:
        """Play the game with this number (if there is one)."""
        if number <= len(self._kinds):
            self.dismiss(self._kinds[number - 1])
