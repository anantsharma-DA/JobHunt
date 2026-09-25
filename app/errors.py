"""What you see when something fails: messages JobHunt wrote for you, never a library's internals.

Messages JobHunt writes itself (a wrong API key, an empty Resume tab, a site blocking searches) tell you what to do and
are shown as they are. Anything unexpected (an exception from a library, which can hold file paths, web addresses,
class names or stack traces) is logged in full to the black run.bat window only, and you see GENERIC instead.
"""
import logging

import requests

GENERIC = "Something went wrong. Please try again later."
SHORT = "something went wrong; please try again later"  # for use inside a longer message

log = logging.getLogger("uvicorn.error")  # uvicorn prints this logger in the run.bat window


def hidden(exc, where="", short=False):
    """Logs the full error for you to look at in the run.bat window; returns the plain message to show."""
    log.error("%s%s: %s", where, " failed" if where else "Unexpected error", exc.__class__.__name__,
              exc_info=(type(exc), exc, exc.__traceback__))
    return SHORT if short else GENERIC


def network(exc, where=""):
    """A readable reason for a failed web request, without its address or the library's wording."""
    if isinstance(exc, requests.Timeout):
        return "the site took too long to answer; try again later"
    if isinstance(exc, requests.ConnectionError):
        return "the site could not be reached; check your internet connection"
    return hidden(exc, where, short=True)
