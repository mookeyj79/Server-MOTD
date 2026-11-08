"""HTTP client for the service modules.

An `Http` is configured once per Instance (base URL, auth header or query
parameter, how to unwrap the service's reply envelope). Each `fetch` opens a
`session(deadline)`: requests share a cookie jar and take their socket
timeout from the time left, so a module never picks its own timeout.
Transport failures raise the `failure` kinds (unreachable, auth failed, API
error, bad response, timed out).
"""

from __future__ import annotations

import http.client
import http.cookiejar
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from server_motd.config import ConfigError, ModuleSpec
from server_motd.failure import (
    ApiError,
    AuthFailed,
    BadResponse,
    TimedOut,
    Unreachable,
    time_left,
)
from server_motd.model import Deadline


def take_url_and_key(spec: ModuleSpec) -> tuple[str, str]:
    """Take the required `url` (trailing slash stripped) and `api_key` options."""
    url = spec.take_url()
    key = spec.take_secret("api_key")
    if not key:
        raise ConfigError("'api_key' is required")
    return url, key


class Http:
    """How to talk to one service Instance."""

    def __init__(
        self,
        base: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        auth_hint: str = "bad API key",
        unwrap: Callable[[Any], Any] | None = None,
    ) -> None:
        self.base = base
        self.headers = dict(headers or {})
        self.params = dict(params or {})
        self.auth_hint = auth_hint
        self.unwrap = unwrap or (lambda body: body)

    def session(self, deadline: Deadline) -> Session:
        return Session(self, deadline)


class Session:
    """Requests for one fetch, all bounded by the same deadline."""

    def __init__(self, http_: Http, deadline: Deadline) -> None:
        self._http = http_
        self.deadline = deadline
        jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def get_json(self, path: str = "", **params: str) -> Any:
        """GET `base + path` and return the parsed, unwrapped JSON body."""
        body = self._open(path, params, None)
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise BadResponse(f"not JSON ({exc})") from exc
        return self._http.unwrap(data)

    def post_form(self, path: str, form: Mapping[str, str]) -> str:
        """POST a form-encoded body; return the reply text."""
        data = urllib.parse.urlencode(form).encode()
        return self._open(path, {}, data).decode("utf-8", "replace")

    def gather(self, *calls: Callable[[], Any]) -> list[Any]:
        """Run calls concurrently; results in order, or the first call's error.

        Worker threads are daemons, so an overrun never delays process exit.
        """
        results: list[Any] = [None] * len(calls)
        errors: list[BaseException | None] = [None] * len(calls)

        def work(i: int) -> None:
            try:
                results[i] = calls[i]()
            except BaseException as exc:
                errors[i] = exc

        threads = [
            threading.Thread(target=work, args=(i,), daemon=True)
            for i in range(len(calls))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(self.deadline.remaining())
            if t.is_alive():
                raise TimedOut()
        for err in errors:
            if err is not None:
                raise err
        return results

    def _open(self, path: str, params: Mapping[str, str], data: bytes | None) -> bytes:
        query = {**self._http.params, **params}
        url = self._http.base + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, data=data, headers=self._http.headers)
        try:
            with self._opener.open(req, timeout=time_left(self.deadline)) as resp:
                body: bytes = resp.read()
                return body
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise AuthFailed(f"{self._http.auth_hint} (HTTP {exc.code})") from exc
            raise ApiError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimedOut() from exc
            raise Unreachable(str(exc.reason)) from exc
        except TimeoutError as exc:
            raise TimedOut() from exc
        except http.client.HTTPException as exc:
            raise BadResponse(str(exc) or type(exc).__name__) from exc
        except OSError as exc:
            raise Unreachable(str(exc)) from exc
        except ValueError as exc:  # e.g. unknown URL scheme
            raise ConfigError(f"'url': {exc}") from exc
