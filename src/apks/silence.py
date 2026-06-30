"""Silence noisy pyaxmlparser decode warnings during APK parsing."""

import contextlib
import logging
from collections.abc import Iterator


@contextlib.contextmanager
def silence_pyaxmlparser() -> Iterator[None]:
    """Suppress harmless decode warnings from all pyaxmlparser loggers.

    Explicitly silences every registered ``pyaxmlparser.*`` logger
    (not just the parent) to catch child loggers that emit warnings
    during lazy resource parsing (e.g. ``.application`` access).
    """
    prefix = "pyaxmlparser"
    loggers = {
        name: _log
        for name, _log in logging.root.manager.loggerDict.items()
        if (name == prefix or name.startswith(prefix + ".")) and isinstance(_log, logging.Logger)
    }
    prior_levels = {name: _log.level for name, _log in loggers.items()}
    for _log in loggers.values():
        _log.setLevel(logging.ERROR)
    try:
        yield
    finally:
        for name, _log in loggers.items():
            _log.setLevel(prior_levels[name])
