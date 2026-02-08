"""Library to read data from the Smart API."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("pySmartHashtag")
except PackageNotFoundError:
    __version__ = "0.0.0"
