# Tautulli API: stream counts, bandwidth, Plex server status

Resolves issue #4 (map: #1). Researched 2026-10-29.

**Sources.** All claims come from Tautulli's own source at tag `v2.18.2` (master `9484667`, 2026-09-28), the latest release. Tautulli's published API reference is generated from the docstrings of these same functions (`api2.py` `_api_make_md`), so the source is the owner of the facts. Paths below are in `https://github.com/Tautulli/Tautulli/blob/9484667bc1f2d159368a999320b8f495bbfbd00a/`:

- `plexpy/api2.py` (auth, envelope, errors)
- `plexpy/webserve.py` (`get_activity`, `server_status`, `status`, `get_server_info`, `get_servers_info`)
- `plexpy/pmsconnect.py` (transcode decision, bandwidth)
- `plexpy/activity_pinger.py` (`PLEX_SERVER_UP`)
- `CHANGELOG.md`

## Answer in brief

| Need | Command | Fields |
|---|---|---|
| Direct play / direct stream / transcode counts | `get_activity` | `stream_count_direct_play`, `stream_count_direct_stream`, `stream_count_transcode` (also `stream_count`) |
| Bandwidth | `get_activity` | `total_bandwidth`, `lan_bandwidth`, `wan_bandwidth` (kbps) |
| Plex server up/down (Tautulli's view) | `server_status` | `connected` (bool) |
| Plex server identity/version | `get_server_info` | `pms_name`, `pms_version`, `pms_platform`, `pms_url`, ... |
| Tautulli itself alive | `status` | `result`, `message` |

One `get_activity` call gives counts and bandwidth together. The existing client calls it twice (once per method).

## Request format

- Endpoint: `http://HOST:PORT[/HTTP_ROOT]/api/v2?cmd=<command>` (`api2.py`, `_api_make_md`).
- Key: `apikey=<key>` query parameter, or the `X-Api-Key` header. The header is **new in v2.18.0** and "preferred for security reasons" (`api2.py` help text; `CHANGELOG.md` v2.18.0: "Allow X-Api-Key header to be used instead of the API key parameter"). Older servers only accept the query parameter.
- The key is exactly 32 characters, else the server answers `401 API key not generated correctly` (`_api_validate`).
- Error statuses from `_api_validate`:
  - `404` API not enabled
  - `401` missing or invalid key
  - `400` missing or unknown `cmd`
- Output is JSON by default; `out_type=xml` is optional.
- Envelope: `{"response": {"result": "success"|"error", "message": null|str, "data": ...}}`. The HTTP status is set from the result (`_api_run`), so an error gives a 4xx.

## get_activity

Docstring in `webserve.py`: "Get the current activity on the PMS." No required parameters. Optional `session_key` / `session_id` return one session instead of the aggregate.

Top-level `data` fields (docstring example):

```
{"lan_bandwidth": 25318, "sessions": [ ... ],
 "stream_count": "1",
 "stream_count_direct_play": 1, "stream_count_direct_stream": 0, "stream_count_transcode": 0,
 "total_bandwidth": 25318, "wan_bandwidth": 0}
```

Gotchas, all from the code:

- **Types are mixed.** `stream_count` is a string (it comes from the Plex XML `size` attribute, `pmsconnect.py`). The three `stream_count_*` and the three `*_bandwidth` fields are ints, computed in `webserve.py`. Cast defensively.
- **Counting rule** (`webserve.py`, per session):
  - `transcode_decision == 'transcode'` counts as transcode.
  - `'copy'` counts as direct stream.
  - Anything else counts as direct play.
  - The decision is set in `pmsconnect.py`: "transcode" if the video or audio stream is transcoded, else "copy" if the video or audio stream is copied, else "direct play". So the counts are per session, and one transcoded track makes the whole session a transcode.
  - The three counts always sum to the number of sessions. There is no "unknown" bucket.
- **Bandwidth** is the sum of each session's Plex `Session@bandwidth`. Plex reports this in kbps, and the docs example is `25318` for a ~10.6 Mbps bitrate stream. The Tautulli docstring does not state the unit, so kbps is Plex's convention rather than something Tautulli documents.
- **LAN/WAN split.** A session counts as LAN only if `location == 'lan'`. Everything else, including cellular, counts as WAN.
- **Empty or failed result.** If Tautulli cannot reach Plex, the aggregate branch is skipped and `get_activity` returns `{}` after logging "Unable to retrieve data for get_activity" (`webserve.py`). The counts keys are then absent. With no streams but a reachable server, the counts are 0 and `sessions` is empty. A client must treat "keys absent" and "zero" as different.
- `sessions[]` is large (see the docstring). For a banner, only `transcode_decision`, `bandwidth`, `location` and perhaps `friendly_name` / `full_title` matter, but the response is always the full payload.

## server_status and the other status commands

- `server_status` (`webserve.py`): "Get the current status of Tautulli's connection to the Plex server." Returns `{"result": "success", "connected": <bool>}`. `connected` is `plexpy.PLEX_SERVER_UP`.
- `PLEX_SERVER_UP` starts as `None` and is set `True`/`False` by the activity pinger / websocket logic (`activity_pinger.py`). Right after Tautulli starts it can be `None` (JSON `null`), meaning unknown. Treat `null` as "unknown", not "down".
- Inference, not stated in the docs: because `_api_run` pops a top-level `result` key out of the returned dict into the envelope, `data` for this command should be `{"connected": true}`. Verify against a live instance before locking the parser.
- `status` (`webserve.py`) reports Tautulli's own health (`result: success`, `message: Ok`). The optional `check=database` runs a database integrity check. It does **not** say anything about Plex.
- `get_server_info` returns `pms_identifier`, `pms_ip`, `pms_name`, `pms_platform`, `pms_plexpass`, `pms_port`, `pms_ssl`, `pms_url`, `pms_url_manual`, `pms_version`. It reads Plex.tv resources and describes the configured server, so it does not prove the server is up. `get_servers_info` returns a list of `{name, host, port, version, machine_identifier}`. `get_server_identity` also exists. `get_server_info`, `get_servers_info` and `get_server_identity` are admin-only, which an API-key call satisfies.
- Recommended for a "server status" line: use `server_status.connected` for up/down and `get_server_info.pms_name`/`pms_version` for labels.

## Comparison with utils/plexpy.py

| Aspect | Existing client | Finding |
|---|---|---|
| Command | `get_activity` for both methods | Correct commands. Fields `stream_count_transcode`, `stream_count_direct_play`, `stream_count_direct_stream`, `total_bandwidth` all still exist in v2.18.2. |
| Calls | Two HTTP requests per run | One call suffices. |
| Auth | `?apikey=` in the URL | Still supported. `X-Api-Key` is preferred from v2.18.0 (keeps the key out of URLs and proxy logs). Support both: header for new versions, the query parameter as fallback for older servers. |
| Failure | Bare `except Exception: pass` returns zeros and `0 Kbps` | Failure is indistinguishable from "no streams". It also ignores `response.result == "error"` and an empty `data`. |
| Server status | Not implemented | Add `server_status`. |
| HTTP | `requests` | The v1 plan is stdlib-only (`urllib.request`), which is enough for GET plus JSON. |
| Bandwidth formatting | `misc.kbps_to_string` treats the value as kbps, with Kbps below 1024 and Mbps above | Consistent with the Plex unit. Tautulli's own UI switches to Gbps above 1000 Mbps (`CHANGELOG.md`, "Show bandwidth in Gbps when greater than 1000 Mbps"). |
| Timeout | 10 s | Reasonable. Tautulli itself calls Plex when serving `get_activity`, so it can be slower than a local call. |

## Deprecations

- No deprecation of `get_activity`, `server_status`, `status` or `get_server_info` appears in the changelog through v2.18.2.
- v2.18.0 removed the deprecated `delete_synced_item` command (`CHANGELOG.md`). It is unrelated, and the old client does not use it.
- Unrelated: Tautulli Remote App notifications via OneSignal are deprecated from 2026-10-01 (`CHANGELOG.md` v2.18.1). Not relevant to this project.
- `get_activity` has gained fields over time (e.g. Dolby Atmos in v2.18.0) and never lost the ones used here. Parse by key and ignore unknown ones.

## Suggested module contract (for the build ticket)

1. One call: `GET /api/v2?cmd=get_activity` with `X-Api-Key`. Optionally fall back to `apikey=`.
2. Success means HTTP 200, `response.result == "success"`, and `data` containing `stream_count_transcode`. Anything else is "unavailable".
3. Convert counts with `int()`, and treat missing keys as "Plex unreachable from Tautulli", not zero.
4. A second call, `cmd=server_status`, is optional for up/down (`True`/`False`/`None`).
5. Bandwidth is kbps. Format at render time.
6. Record a fixture from a real instance for `get_activity` (idle, direct play, transcode) and for `server_status`, per the map's "recorded fixtures" plan.

## Not verified

- No live Tautulli instance was queried. Everything is from source and docstrings. Items to confirm: the unit of bandwidth (kbps assumed from Plex), the `server_status` `data` shape, and the `null` value after startup.
- The Tautulli wiki's "Tautulli API Reference" page (`github.com/Tautulli/Tautulli/wiki/Tautulli-API-Reference`) is generated from these docstrings. It was not fetched, and the source was used as the authority instead.
