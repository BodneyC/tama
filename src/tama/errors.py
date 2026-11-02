"""Exception hierarchy. Every exception raised deliberately by tama derives from ``TamaError``."""


class TamaError(Exception):
    """Base class for all tama errors."""


class InvalidArgumentError(TamaError, ValueError):
    """An argument had an invalid value (e.g. a naive datetime or non-positive speed)."""
