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

    def __init__(self, last: GameKind | None = None) -> None:
        """Pre-select ``last``, the game chosen last time this session."""
        super().__init__()
        self._last = last or GameKind.LEFT_RIGHT

    @override
    def compose(self) -> ComposeResult:
        """Build the dialog."""
        with Vertical(classes="dialog"):
            yield Static("Play a game", classes="dialog-title")
            yield OptionList(
                *(
                    Option(f"{number}  {name:<14}{blurb}", id=kind.value)
                    for number, (kind, (name, blurb)) in enumerate(GAMES.items(), start=1)
                ),
                id="games",
            )
            yield Static("↑↓ Enter or 1-3 to play · Esc to cancel", classes="dialog-hint")

    def on_mount(self) -> None:
        """Highlight the last game played."""
        games = self.query_one(OptionList)
        games.highlighted = list(GameKind).index(self._last)
        games.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Play the selected game."""
        self.dismiss(GameKind(str(event.option.id)))

    def action_choose(self, number: int) -> None:
        """Play the game with this number."""
        self.dismiss(list(GameKind)[number - 1])
