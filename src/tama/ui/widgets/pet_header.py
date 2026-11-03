"""The header: who the pet is, how it's doing, and whether it needs you."""

from datetime import UTC, tzinfo
from typing import override

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.widget import Widget
from textual.widgets import Static

from tama.domain.attention import AttentionReason, attention_reasons
from tama.domain.balance import Balance
from tama.domain.pet import Pet
from tama.domain.stage import LifeStage
from tama.domain.stats import Stat
from tama.services.describe import format_age, holiday_since
from tama.ui.widgets.pet_view import ViewOptions

BLINK_SECONDS = 0.5

STAT_ICONS: dict[Stat, str] = {
    Stat.HUNGER: "🍖",
    Stat.HAPPINESS: "😊",
    Stat.ENERGY: "⚡",
    Stat.HYGIENE: "🧼",
    Stat.HEALTH: "♥",
}


def level_style(value: int) -> str:
    """Theme colour for a stat value: fine, worrying, or urgent."""
    if value >= 50:
        return "$tama-stat-good"
    if value >= 25:
        return "$tama-stat-warning"
    return "$tama-stat-bad"


def identity_text(pet: Pet) -> str:
    """``Mochi · child · 2d 4h``."""
    return f"{pet.name} · {pet.stage.value} · {format_age(pet.age)}"


def stats_content(pet: Pet) -> Content:
    """Compact, colour-coded stat readout (empty for eggs and dead pets)."""
    if pet.stage in (LifeStage.EGG, LifeStage.DEAD):
        return Content("")
    parts = [
        Content.assemble(f"{icon} ", (str(pet.stats[stat]), level_style(pet.stats[stat])))
        for stat, icon in STAT_ICONS.items()
    ]
    return Content("  ").join(parts)


def attention_text(pet: Pet, balance: Balance, tz: tzinfo = UTC) -> str:
    """``⚠ hungry · poop`` when the pet needs something, ``⏸ on holiday since 3 Nov``, or empty."""
    if pet.paused_since is not None:
        return f"⏸ on holiday since {holiday_since(pet.paused_since, tz)}"
    reasons = attention_reasons(pet, balance)
    if not reasons:
        return ""
    return "⚠ " + " · ".join(r.value for r in AttentionReason if r in reasons)


class PetHeader(Widget):
    """Name, stage and age; stat icons; a blinking attention indicator (SPEC §4)."""

    def __init__(self, options: ViewOptions | None = None) -> None:
        """Create the header; the indicator blinks only when ``options`` allow motion."""
        super().__init__()
        options = options or ViewOptions()
        self.blinking = options.animate and not options.reduced_motion

    @override
    def compose(self) -> ComposeResult:
        """Build the header lines."""
        with Horizontal(id="header-top"):
            yield Static(id="identity", markup=False)
            yield Static(id="stats")
        with Horizontal(id="header-bottom"):
            yield Static(id="attention", markup=False)
            yield Static(id="others", markup=False)

    def on_mount(self) -> None:
        """Start blinking the attention indicator (it only shows while there is a call)."""
        if self.blinking:
            self.set_interval(BLINK_SECONDS, self.blink)

    def show(self, pet: Pet, balance: Balance, tz: tzinfo = UTC) -> None:
        """Update the header for ``pet``, with dates in ``tz``."""
        self.query_one("#identity", Static).update(identity_text(pet))
        self.query_one("#stats", Static).update(stats_content(pet))
        attention = attention_text(pet, balance, tz)
        indicator = self.query_one("#attention", Static)
        indicator.update(attention)
        indicator.set_class(pet.on_holiday, "-holiday")
        if not attention or pet.on_holiday:
            indicator.remove_class("-blink-off")

    def show_others(self, count: int) -> None:
        """``⚠ +N`` when ``count`` other pets need attention (SPEC §6.1); never blinks."""
        self.query_one("#others", Static).update(f"⚠ +{count}" if count else "")

    def blink(self) -> None:
        """Flip the attention indicator between shown and hidden while the pet is calling."""
        indicator = self.query_one("#attention", Static)
        calling = bool(indicator.content) and not indicator.has_class("-holiday")
        indicator.set_class(calling and not indicator.has_class("-blink-off"), "-blink-off")
