"""Exception hierarchy. Every exception raised deliberately by tama derives from ``TamaError``."""


class TamaError(Exception):
    """Base class for all tama errors."""


class InvalidArgumentError(TamaError, ValueError):
    """An argument had an invalid value (e.g. a naive datetime or non-positive speed)."""


class GameOverError(TamaError):
    """A move was made in a mini-game that has already finished."""


class SaveError(TamaError):
    """Base class for save-file problems."""


class SaveNotFoundError(SaveError):
    """There is no save file (nor a backup) to load."""


class CorruptSaveError(SaveError):
    """A save file exists but could not be read or understood."""


class UnsupportedSaveVersionError(SaveError):
    """A save file was written by a newer version of tama than this one."""


class SaveWriteError(SaveError):
    """The game could not be saved (e.g. the directory is not writable)."""


class ConfigError(TamaError):
    """The config file is malformed or has invalid values."""
