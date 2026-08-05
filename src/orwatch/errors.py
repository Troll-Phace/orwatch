"""Exception hierarchy for orwatch.

Every error raised by orwatch derives from :class:`OrwatchError` so that
callers can catch a single base type at the top level. Each concrete
subclass belongs to exactly one module and that owning module is named in
its docstring.
"""


class OrwatchError(Exception):
    """Base class for all orwatch errors."""


class FetchError(OrwatchError):
    """Raised by client.py on a network failure, a non-200 response, or
    unparseable JSON."""


class StoreError(OrwatchError):
    """Raised by store.py on any snapshot read or write failure.

    The message is expected to carry the offending path.
    """


class ConfigError(OrwatchError):
    """Raised by config.py on a missing or malformed orwatch.toml."""
