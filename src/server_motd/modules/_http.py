"""Helpers shared by the HTTP service modules.

One request timeout (kept within the runner's per-module limit), the common
`url` / `api_key` options, and the mapping of transport failures to short
user-visible messages.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from server_motd.config import ConfigError, ModuleSpec

REQUEST_TIMEOUT = 2.5


def take_url_and_key(spec: ModuleSpec) -> tuple[str, str]:
    """Take the required `url` (trailing slash stripped) and `api_key` options."""
    url = spec.take("url", str)
    key = spec.take_secret("api_key")
    if not url:
        raise ConfigError("'url' is required")
    if not key:
        raise ConfigError("'api_key' is required")
    return url.rstrip("/"), key


def request(
    opener: Callable[..., Any],
    *args: Any,
    auth_error: str = "bad API key",
) -> Any:
    """Call `opener(*args, timeout=REQUEST_TIMEOUT)` and return the response.

    Failures raise RuntimeError with the message shown in the MOTD. Use as a
    context manager result: the caller closes the response.
    """
    try:
        return opener(*args, timeout=REQUEST_TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(f"{auth_error} (HTTP {exc.code})") from exc
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"unreachable: {exc.reason}") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"bad response: {exc}") from exc


def read(
    opener: Callable[..., Any],
    *args: Any,
    auth_error: str = "bad API key",
) -> bytes:
    """Open, read fully and close; transport failures map as in `request`."""
    try:
        with request(opener, *args, auth_error=auth_error) as resp:
            data: bytes = resp.read()
            return data
    except RuntimeError:
        raise
    except (OSError, ValueError) as exc:  # failure while reading the body
        raise RuntimeError(f"bad response: {exc}") from exc


def get_json(
    target: str | urllib.request.Request, *, auth_error: str = "bad API key"
) -> Any:
    """GET a URL (or Request) and parse the JSON body."""
    body = read(urllib.request.urlopen, target, auth_error=auth_error)
    try:
        return json.loads(body)
    except ValueError as exc:
        raise RuntimeError(f"bad response: {exc}") from exc
