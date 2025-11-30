"""Library to read data from the Smart API."""

from importlib.metadata import version

from pysmarthashtag.const import EndpointUrls, SmartRegion, get_endpoint_urls_for_region

__version__ = version("pySmartHashtag")

__all__ = [
    "__version__",
    "SmartRegion",
    "EndpointUrls",
    "get_endpoint_urls_for_region",
]
