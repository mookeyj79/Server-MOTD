# Download client APIs: qBittorrent, SABnzbd, rTorrent

Research for ticket #3 (map #1). Question: for qBittorrent (WebUI v2), SABnzbd and rTorrent (XML-RPC/SCGI, as used by ruTorrent), how do auth, sessions and endpoints work, and what gives transfer rates, totals and per-state counts in one or two calls using only the Python stdlib?

Researched 2026-10-29. Latest releases at that date: qBittorrent 5.3.0 (WebAPI 2.16.2), SABnzbd 5.1.3 stable (5.2.0 beta in flight), rTorrent 0.16.27.

## Method and confidence

All claims trace to first-party sources: vendor API docs and, where docs are stale or silent, the vendor's source at a pinned release tag. Source links use tags so they stay valid.

Nothing here was run against a live qBittorrent, SABnzbd or rTorrent. The only thing executed was the SCGI transport in section 3.5, against a fake in-process SCGI server (it round-trips a `system.multicall`). Recorded fixtures from real instances should be captured when the modules are built (the map already plans this).

## Summary for the architecture decision

| | qBittorrent | SABnzbd | rTorrent |
|---|---|---|---|
| Transport | HTTP, form-encoded POST/GET, JSON | HTTP GET, JSON | XML-RPC over HTTP (via ruTorrent/web server) or raw SCGI |
| Auth | Username/password login, then session cookie | API key query parameter only | None in rTorrent itself; whatever the fronting web server does |
| Session state | Yes (cookie jar needed) | None | None |
| Calls for a full MOTD line | 2 (login + `sync/maindata`), or 3 with `transfer/info` | 2 (`queue` + `server_stats`), no login | 1 (`system.multicall` containing `d.multicall2`) |
| Rates | bytes/s ints | `kbpersec` string, KiB/s | bytes/s ints |
| Lifetime totals | `alltime_dl` / `alltime_ul` (maindata only) | `server_stats` `total`, bytes | None. `throttle.global_*.total` is since rTorrent started |
| Version drift to handle | Cookie name, login failure shape, state names | `qstatus` mode is gone | `d.multicall2` renamed `d.multicall` in 0.16 (alias kept) |

## 1. qBittorrent WebUI API v2

Sources: [WebUI API (qBittorrent 5.0) wiki](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-5.0)) (raw markdown); source at tags [release-5.3.0](https://github.com/qbittorrent/qBittorrent/tree/release-5.3.0/src/webui), [release-5.2.4](https://github.com/qbittorrent/qBittorrent/tree/release-5.2.4/src/webui), [release-5.1.4](https://github.com/qbittorrent/qBittorrent/tree/release-5.1.4/src/webui), [release-4.6.7](https://github.com/qbittorrent/qBittorrent/tree/release-4.6.7/src/webui).

### 1.1 Auth and sessions

- All endpoints are `/api/v2/<scope>/<method>`. Only `GET` or `POST` are allowed; since 4.4.4 the wrong verb returns `405`. All methods require authentication except `auth/login` (wiki, "General Information").
- Login is `POST /api/v2/auth/login` with form fields `username` and `password`. Per the wiki, `403` means the IP is banned for too many failed logins; `200` otherwise. On success the response sets a session cookie, which must be sent on later requests (wiki, "Authentication").
- Cookie name is not stable across versions (source, `webapplication.cpp`):
  - 4.6.7, 5.0.0, 5.1.4: `SID`.
  - 5.2.0 and later (checked 5.2.0, 5.2.4, 5.3.0): `QBT_SID_<webui port>`.
  - The wiki still says `SID`. A client must not hard-code the name; use `http.cookiejar` (`urllib.request.HTTPCookieProcessor`) and let it carry whatever was set.
- Login failure shape also changed (source, `authcontroller.cpp`):
  - 4.6.7, 5.0.0, 5.1.4: HTTP 200 with body `Fails.` on bad credentials, `Ok.` on success.
  - 5.2.4, 5.3.0: bad credentials throw `APIErrorType::Unauthorized` (the code path maps this to an HTTP 401 error in `webapplication.cpp`; not exercised live).
  - So a client should treat success as "HTTP 200, body is not `Fails.`, and a session cookie is present", and treat 401 and 403 as failure.
- Session lifetime is a server preference (`m_sessionTimeout`, WebUI "session timeout"); the cookie is refreshed on use. For a one-shot login banner, log in on every run and discard; there is no need to persist sessions between runs.
- The Referer/Origin wording in the wiki ("set to the exact same domain and port as the Host header") is stricter than the code. In `isCrossSiteRequest` (5.3.0) a request is only rejected if it carries `Sec-Fetch-Site`, `Origin` or `Referer` that mismatches the Host; with none of those headers the code explicitly allows it ("Web API clients don't send any of these headers"). `urllib` sends none, so no extra headers are needed. If Host header validation is on, the `Host` must match the server's address, domain whitelist or port; connecting by a different hostname than the one whitelisted yields 401.
- Auth bypass: the preference `bypass_local_auth` (documented as "authentication challenge for loopback address should be disabled") and the subnet whitelist (`bypass_auth_subnet_whitelist*`). In code, `isAuthNeeded()` returns false for loopback when local auth is off, or when the client IP is in the whitelist. In that case a request without a cookie starts a session automatically, so the same client code works with or without credentials; the module should allow empty username/password.
- API keys: the master branch (post 5.3.0; not in 5.3.0 or earlier tags) adds `Authorization: Bearer <key>` / `X-Api-Key` header auth that skips cookies and CSRF and cannot reach `auth/*`. Not released as of this research; design the config so a future `api_key` field could be added, but do not build on it for v1.
- Version probe: `GET /api/v2/app/version` returns a string such as `v5.3.0`, and `GET /api/v2/app/webapiVersion` returns e.g. `2.16.2` (wiki "Application"). Both need authentication like everything else; the wiki states only "200 in all scenarios".

### 1.2 Endpoints for stats

- `GET /api/v2/transfer/info` (wiki "Get global transfer info"; `transfercontroller.cpp`): `dl_info_speed`, `dl_info_data`, `up_info_speed`, `up_info_data`, `dl_rate_limit`, `up_rate_limit`, `dht_nodes`, `connection_status` (`connected`, `firewalled`, `disconnected`). Speeds are bytes/s; `*_info_data` is bytes transferred this session (since qBittorrent started), not lifetime. This endpoint has no lifetime totals.
- `GET /api/v2/sync/maindata?rid=0` (wiki "Get main data"; `synccontroller.cpp`): returns `rid`, `full_update`, `torrents` (map of hash to torrent, each with `state`), `server_state`, and categories/tags. `server_state` contains the transfer keys above plus, per `synccontroller.cpp`: `alltime_dl`, `alltime_ul` (lifetime bytes), `global_ratio`, `total_peer_connections`, `free_space_on_disk`, `queueing`, `use_alt_speed_limits`. The wiki does not list these `server_state` sub-fields; the source is the authority. Lifetime totals are only available here.
- `GET /api/v2/torrents/info?filter=<f>` (wiki "Get torrent list"): `filter` accepts `all`, `downloading`, `seeding`, `completed`, `stopped`, `active`, `inactive`, `running`, `stalled`, `stalled_uploading`, `stalled_downloading`, `errored`. Also `limit`, `offset`, `sort`. There is no field-projection parameter (checked `torrentscontroller.cpp`: only `filter`, `category`, `tag`, `sort`, `limit`, `offset`, `hashes`...), so every call returns full torrent objects.

### 1.3 Torrent `state` values

The wiki table still lists `pausedUP`/`pausedDL` and calls `stopped` only a filter. The source says otherwise. `serialize_torrent.cpp`:

- 4.6.7: `pausedUP`, `pausedDL`.
- 5.0.0 through 5.3.0: `stoppedUP`, `stoppedDL` (the pause-to-stop rename landed in 5.0).
- 5.3.0 full list: `error`, `missingFiles`, `uploading`, `stoppedUP`, `queuedUP`, `stalledUP`, `checkingUP`, `forcedUP`, `downloading`, `metaDL`, `forcedMetaDL`, `stoppedDL`, `queuedDL`, `stalledDL`, `checkingDL`, `forcedDL`, `checkingResumeData`, `moving`, `unknown`.

Suggested bucketing that works on both 4.x and 5.x: downloading = `downloading`, `metaDL`, `forcedMetaDL`, `forcedDL`, `stalledDL`, `queuedDL`, `checkingDL`; seeding = `uploading`, `forcedUP`, `stalledUP`, `queuedUP`, `checkingUP`; stopped = `stoppedUP`, `stoppedDL`, `pausedUP`, `pausedDL`; error = `error`, `missingFiles`. Which buckets the MOTD shows is a design call for the module ticket.

### 1.4 Recommended call plan (stdlib)

1. `POST auth/login` (urlencoded body via `urllib.parse.urlencode`), with `HTTPCookieProcessor` opener.
2. `GET sync/maindata` (rid defaults to 0, so always a full update). One response gives rates, session and lifetime totals, and every torrent's state for counting. Cost scales with torrent count (full torrent objects); for very large libraries, the fallback is `transfer/info` plus `torrents/info?filter=downloading` and `filter=seeding`, which is 3 round trips after login but with smaller payloads for the counted states. Measure before choosing; there is no way to ask for state only.

Two requests total, one session, nothing persisted. Timeout via `urlopen(timeout=...)` per request.

## 2. SABnzbd

Sources: [SABnzbd API wiki (5.1)](https://sabnzbd.org/wiki/configuration/5.1/api) (the old `/wiki/advanced/api` URL is a redirect stub); source at tag [5.1.3](https://github.com/sabnzbd/sabnzbd/tree/5.1.3/sabnzbd) (`api.py`, `interface.py`, `constants.py`, `nzbqueue.py`).

### 2.1 Auth and sessions

- Endpoint: `GET http://host:port/api?mode=<mode>&output=json&apikey=<key>` (wiki). JSON is already the default in code; only `output=xml` switches (`report()` in `api.py`). Sending `output=json` is harmless and explicit.
- Auth is the API key only, as a query parameter `apikey`. There is no session or cookie. `interface.py` `set_auth()` explicitly disables HTTP Basic auth on the `/api` route, and `secured_expose` skips the login check for key-protected routes, so a configured SABnzbd web username/password does not apply to API calls. The wiki does not document username/password auth for the API.
- Key kinds: the API key does everything; the NZB key only authorises level-1 calls (adding jobs) (`check_apikey`). `mode=version` and `mode=auth` need no key at all (wiki; `check_apikey`).
- Errors are not JSON. A missing key returns the plain text `API Key Required` and a wrong key `API Key Incorrect`, with HTTP status 403 (`secured_expose` sets 403; the body is only sent when the `api_warnings` setting is on, otherwise it is empty). Other 403 causes in the same wrapper: external-access restrictions, the hostname whitelist check, and the config lock. Parse by status code first, then try `json.loads`. The wiki's "error: API Key Incorrect" wording is a legacy formatting; the 5.1.3 source returns the bare string. Error responses from handlers that call `report(error)` are JSON `{"status": false, "error": "..."}`.
- Cheap liveness probe: `mode=version` (no key) returns `{"version": "5.1.3"}`.

### 2.2 Endpoints for stats

- `mode=queue` (key `queue` in the response; `build_queue` in `api.py`): `status` (`Paused`, `Downloading` or `Idle`), `paused` (bool), `kbpersec` (string, KiB/s, two decimals), `speed` (human string such as `1.3 M`), `mb`, `mbleft` (strings, MiB), `size`, `sizeleft` (human strings), `noofslots` (matched jobs), `noofslots_total` (all jobs), `timeleft`, `speedlimit`, `speedlimit_abs`, `diskspace1/2`, `diskspacetotal1/2` (GiB strings), `have_warnings`, `quota`, and `slots` (per-job list with `status`). Params `start` and `limit`: `limit=0` (default) returns all slots, so to get counts without the slot payload use a small `limit=1`; `noofslots_total` still reports the full queue size. A `status=` filter (comma list) restricts slots and therefore `noofslots`.
- Slot status values come from `Status` in `constants.py`: `Downloading`, `Queued`, `Paused`, `Propagating`, `Fetching`, `Checking`, `Grabbing`, plus post-processing states (`Verifying`, `Repairing`, `Extracting`, `Moving`, `Running`, `QuickCheck`) that appear in history and `ppslots`.
- `mode=server_stats` (`_api_server_stats`): `{"total": <bytes>, "month": ..., "week": ..., "day": ..., "servers": {<name>: {total, month, week, day, daily, articles_tried, articles_success}}}`, all in bytes, summed from the bandwidth meter. `total` is lifetime downloaded across all configured news servers. Note that SABnzbd tracks downloaded bytes only; there is no upload.
- `mode=history` also carries `total_size`, `month_size`, `week_size`, `day_size`, but as human strings (`to_units`), so prefer `server_stats` for numbers. History `limit` defaults to the `history_limit` setting when 0, so counts of completed/failed jobs from `noofslots` are page-limited; the "per-state counts" for a usenet client are naturally the queue buckets (downloading, queued, paused), and failed/completed counts would need `mode=history&status=Failed` and a decision on what `noofslots` means for that query (not verified here).
- `mode=qstatus` (older docs and old clients): absent from the 5.1.3 and develop `api.py` dispatch table; do not use it. `mode=queue` supersedes it.

### 2.3 Recommended call plan

Two independent GETs, parallelisable and with no login: `mode=queue&limit=0` (or a status-filtered/limited variant) for rate, remaining size, state counts; `mode=server_stats` for totals. Unit handling: `kbpersec` is KiB/s as a string, so `float(kbpersec) * 1024` gives bytes/s; `mb`/`mbleft` are MiB strings.

## 3. rTorrent (XML-RPC over SCGI)

Sources: rTorrent source at [v0.16.27](https://github.com/rakshasa/rtorrent/tree/v0.16.27/src) and [v0.9.8](https://github.com/rakshasa/rtorrent/tree/v0.9.8/src) (`command_throttle.cc`, `command_events.cc`, `command_download.cc`, `main.cc`, `rpc/scgi_task.cc`); [SCGI protocol spec](https://python.ca/scgi/protocol.txt); ruTorrent [`conf/config.php`](https://github.com/Novik/ruTorrent/blob/master/conf/config.php) and [`php/scgitransport.php`](https://github.com/Novik/ruTorrent/blob/master/php/scgitransport.php).

### 3.1 Transport and auth

- rTorrent itself speaks only SCGI (a binary framing of the request) on a TCP port or unix socket, configured with `network.scgi.open_port` or `network.scgi.open_local` (`command_network.cc`). It has no authentication. Anything that can reach the socket can issue commands.
- ruTorrent reaches it as a web server (`scgi_pass`) and mounts the XML-RPC endpoint at `/RPC2` (`$XMLRPCMountPoint = "/RPC2"` in `conf/config.php`); ruTorrent's own PHP talks SCGI to `$scgi_host:$scgi_port` (default 127.0.0.1:5000) or a unix socket. When the MOTD is pointed at an HTTP URL ending `/RPC2` (as the existing code does), authentication is whatever the front web server enforces (typically HTTP Basic). Embedding credentials in the URL works with `xmlrpc.client.ServerProxy` (`http://user:pass@host/RPC2` becomes a Basic auth header). For direct SCGI there is no auth at all and the config should say so ("unix socket path" or "host:port").
- SCGI request format ([spec](https://python.ca/scgi/protocol.txt)): a netstring `len:headers,` followed by the body. Headers are `NAME\0VALUE\0` pairs, `CONTENT_LENGTH` must come first and `SCGI` must be `1`. The response is HTTP-like (`Status: 200 OK`, headers, blank line, body); the server closes the connection.
- Trust: `v0.16.x` adds an `UNTRUSTED_CONNECTION` SCGI header (`scgi_task.cc`); when it is `1` only commands whitelisted with `mark_safe` are allowed (ruTorrent sends it for untrusted callers). A raw SCGI client that omits the header is treated as trusted (default `m_trusted = true`). Everything this module needs is on the whitelist (`throttle.global_*.rate/.total`, `d.multicall2`, `d.state`, `d.complete`, `d.is_active`, `d.down.rate`, `d.up.rate`), so it works either way.
- Content type: 0.16 also detects JSON-RPC bodies starting with `{` or `[`. XML-RPC works on every version and `xmlrpc.client` is stdlib, so use XML-RPC for v1.

### 3.2 Commands

Byte totals exceed 32 bits quickly. `xmlrpc.client` parses `<i8>` and `<int>` values into Python ints without a range check, but I did not verify which tag each rTorrent build emits (there is a `network.xmlrpc.dialect.set` command in `command_network.cc`). Check totals above 2 GiB on a real instance.

- `throttle.global_down.rate`, `throttle.global_up.rate` (bytes/s), `throttle.global_down.total`, `throttle.global_up.total` (bytes since rTorrent started; `command_throttle.cc` binds `torrent::Rate::rate/total`). There are no lifetime totals in rTorrent; if the MOTD wants lifetime transfer it would need to read ruTorrent plugin data, which is out of scope.
- `d.multicall2` takes `(target, view, cmd1=, cmd2=, ...)`: the first XML-RPC argument is the (empty) target, the second the view name; an empty view string means `default` (`d_multicall` in `command_events.cc`, both 0.9.8 and 0.16.27). The trailing `=` on each command string is the "call with no arguments" syntax. Returns a list of rows. ruTorrent itself uses view `main`.
- In 0.16.x the real command is `d.multicall`, and `d.multicall2` is a registered redirect plus a "TODO: Deprecate d.multicall2. (6/2026)" comment (`main.cc`: `CMD_REDIRECT("d.multicall2", "d.multicall")`, with an additional note to deprecate "a while after 1.1 release"). 0.9.x only has `d.multicall2` (the 0.9.8 registration is `d.multicall2`). So: use `d.multicall2` for compatibility, and expect to add a fallback to `d.multicall` if the redirect is ever removed.
- Per-download fields: `d.state` (1 started, 0 stopped), `d.complete` (1 finished), `d.is_active`, `d.hashing`, `d.down.rate`, `d.up.rate` (bytes/s), `d.message` (error text). A defensible bucketing: downloading = state 1 and complete 0; seeding = state 1 and complete 1; stopped = state 0; active-transfer counts can use the rates.

### 3.3 One call: `system.multicall`

`system.multicall` is handled by the XML-RPC layer itself (`command_dynamic.cc` lists it as handled directly by the XMLRPC code), so global rates, totals and the per-torrent rows can ride one request:

```python
proxy.system.multicall([
    {"methodName": "throttle.global_down.rate",  "params": []},
    {"methodName": "throttle.global_up.rate",    "params": []},
    {"methodName": "throttle.global_down.total", "params": []},
    {"methodName": "throttle.global_up.total",   "params": []},
    {"methodName": "d.multicall2",
     "params": ["", "main", "d.state=", "d.complete=", "d.down.rate=", "d.up.rate="]},
])
```

Each result is wrapped in a one-element list (a fault is a dict); `d.multicall2` returns the list of rows. Use view `main` or `""` (`default`). Note `d.multicall2`'s first param is the empty target.

### 3.4 Comparison with the existing repo code

`utils/rtorrent.py` and `utils/xmlrpc.py` (this repo, fork predecessor):

- It issues one HTTP request per metric (`get_download_total`, `get_upload_total`, `get_download_rate`, `get_upload_rate`, `get_torrent_counts`), and the bash scripts call the Python entry point separately for each, so a refresh costs around six connections and six interpreter starts. `system.multicall` collapses this to one request.
- It targets an HTTP `/RPC2` URL only, so it cannot talk to a bare SCGI socket.
- `d.multicall2("", "", ...)` is correct (empty target, empty view means `default`), matching the source.
- "Seeding" and "downloading" are defined as non-zero `d.up.rate` and `d.down.rate` (the rows' `[-2]` and `[-1]` fields), i.e. currently transferring, not state. That is a semantic choice, not an API limitation; state-based buckets are above.
- The rate conversion multiplies bytes/s by `8.38861` and relabels `B` as `b`. Bytes to bits is a factor of 8; 8.38861 is 8 x 1.048576, so shown rates are about 4.9% high. I found no basis for the extra factor in the rTorrent source (the rates are plain bytes/s via `torrent::Rate::rate`). Worth fixing in the port.
- `utils/xmlrpc.py` sets the process-global `socket.setdefaulttimeout` and its `__exit__` restores it only when the previous value `is None` (inverted), so it effectively never restores a non-None default. With the map's concurrent module fetching, a global default timeout is also a race between threads. The replacement should pass a timeout per connection (see the transport below).
- The default timeout in the old wrapper is 10 s; the new budget is about 2 s.

### 3.5 Tested stdlib SCGI transport

Subclass `xmlrpc.client.Transport` and override `request()` (no third-party code; this was run against a fake SCGI server and round-tripped a `system.multicall`):

```python
import socket, xmlrpc.client

class ScgiTransport(xmlrpc.client.Transport):
    """xmlrpc.client transport for SCGI: address is (host, port) or a unix socket path."""
    def __init__(self, address, timeout=2.0):
        super().__init__()
        self.address, self.timeout = address, timeout

    def request(self, host, handler, request_body, verbose=False):
        hdr = (b"CONTENT_LENGTH\0" + str(len(request_body)).encode() + b"\0SCGI\0001\0"
               b"REQUEST_METHOD\0POST\0CONTENT_TYPE\0text/xml\0")
        msg = str(len(hdr)).encode() + b":" + hdr + b"," + request_body
        if isinstance(self.address, tuple):
            s = socket.create_connection(self.address, timeout=self.timeout)
        else:
            s = socket.socket(socket.AF_UNIX); s.settimeout(self.timeout); s.connect(self.address)
        with s:
            s.sendall(msg)
            buf = b""
            while chunk := s.recv(65536):
                buf += chunk
        _, _, body = buf.partition(b"\r\n\r\n")
        p, u = self.getparser(); p.feed(body); p.close()
        return u.close()

proxy = xmlrpc.client.ServerProxy("http://localhost/RPC2", transport=ScgiTransport(("127.0.0.1", 5000)))
```

For the HTTP variant (`/RPC2` through nginx or ruTorrent) use the stock transport; to bound time per connection subclass `Transport.make_connection` and set `conn.timeout`, or pass a custom `Transport` whose `make_connection` returns `http.client.HTTPConnection(host, timeout=2)`. `socket.AF_UNIX` is not available on Windows Python, so a Windows host must reach rTorrent over TCP SCGI or the HTTP mount.

## 4. Implications for the module model

- Config per instance, keyed on transport rather than assuming one shape: qBittorrent `url`, optional `username`/`password` (optional because of local-auth bypass); SABnzbd `url`, required `api_key`; rTorrent either `url` (HTTP `/RPC2`, optional basic-auth credentials) or `scgi` (`host:port` or `unix:/path`). Secrets via the map's `${ENV}` / `*_file` mechanisms (SABnzbd's key and the qBittorrent password; an rTorrent URL with credentials embedded is a secret too).
- Only qBittorrent needs a cookie jar and login. Make the login part of the module's single fetch so a failure produces one "unavailable" result.
- One module call is 1-2 HTTP requests for each client, which fits a 2 s budget on a LAN. Apply the timeout per socket operation and treat the module budget as an overall deadline.
- Normalise to a common shape in the module (rate bytes/s down and up, totals down and up where available, counts downloading/seeding/stopped/error). Lifetime totals are not uniformly available: qBittorrent has them (maindata only), SABnzbd has download-only, rTorrent has session-only; the renderer should label session totals as such or omit them.
- Version drift (qBittorrent cookie name, login failure, state names; rTorrent `d.multicall2`) argues for fixtures per major version in the map's recorded-fixture test plan: qBittorrent 4.6.x and 5.3.x, SABnzbd 5.1.x, rTorrent 0.9.8 and 0.16.x.

## 5. Open questions

- Large-library cost of `sync/maindata` (and rTorrent's `d.multicall2`) against the 2 s budget is unmeasured; test with a few thousand torrents.
- SABnzbd history counts (failed/completed) were not verified; if wanted, check what `noofslots` returns with a `status=` filter and a small `limit`.
- rTorrent integer width over XML-RPC (`<i8>` for totals above 2 GiB) needs a live check against both 0.9.x and 0.16.x builds, including builds using the tinyxml2 XML-RPC backend (`rpc/xmlrpc_tinyxml2.cc` exists in 0.16).
- qBittorrent API-key auth (Bearer / `X-Api-Key`) is on master only; revisit once released.
