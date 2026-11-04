"""The mini-games: a game select dialog and one modal screen per game (SPEC §3.1)."""

from textual.screen import ModalScreen

from tama.domain.minigames import GameKind, GameResult
from tama.services.describe import GAME_NAMES
from tama.services.session import GameSession
from tama.ui.screens.games.four_in_a_row import FourInARowScreen
from tama.ui.screens.games.left_right import LeftRightScreen
from tama.ui.screens.games.tic_tac_toe import TicTacToeScreen
from tama.ui.widgets.pet_view import ViewOptions

_HINTS = {
    GameKind.LEFT_RIGHT: "guess where it looks",
    GameKind.FOUR_IN_A_ROW: "line up four",
    GameKind.TIC_TAC_TOE: "three in a row",
}
GAMES: dict[GameKind, tuple[str, str]] = {
    kind: (GAME_NAMES[kind], _HINTS[kind]) for kind in GameKind
}
"""Each game's name and a one-line description, in select-dialog order."""


def game_screen(
    kind: GameKind, session: GameSession, view: ViewOptions
) -> ModalScreen[GameResult | None]:
    """A new game of ``kind`` against ``session``'s pet."""
    match kind:
        case GameKind.LEFT_RIGHT:
            return LeftRightScreen(session, view)
        case GameKind.FOUR_IN_A_ROW:
            return FourInARowScreen(session, view)
        case GameKind.TIC_TAC_TOE:
            return TicTacToeScreen(session, view)
