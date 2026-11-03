"""The header: who the pet is, how it's doing, and whether it needs you."""

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
from tama.services.describe import format_age

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
        return "$success"
    if value >= 25:
        return "$warning"
    return "$error"


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


def attention_text(pet: Pet, balance: Balance) -> str:
    """``⚠ hungry · poop`` when the pet needs something, else empty."""
    reasons = attention_reasons(pet, balance)
    if not reasons:
        return ""
    return "⚠ " + " · ".join(r.value for r in AttentionReason if r in reasons)


class PetHeader(Widget):
    """Name, stage and age; stat icons; attention indicator."""

    @override
    def compose(self) -> ComposeResult:
        """Build the header lines."""
        with Horizontal(id="header-top"):
            yield Static(id="identity", markup=False)
            yield Static(id="stats")
        yield Static(id="attention", markup=False)

    def show(self, pet: Pet, balance: Balance) -> None:
        """Update the header for ``pet``."""
        self.query_one("#identity", Static).update(identity_text(pet))
        self.query_one("#stats", Static).update(stats_content(pet))
        self.query_one("#attention", Static).update(attention_text(pet, balance))
