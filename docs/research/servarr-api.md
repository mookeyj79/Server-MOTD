# Servarr API surface for Sonarr, Radarr and Lidarr

Research for issue #2 (child of map #1). Question: which endpoints and auth do Sonarr, Radarr and Lidarr offer for a login-time summary (queue, wanted/missing, health, upcoming calendar, disk space), what is cheap enough for a ~2s budget, and what differs between the three.

## Sources (all primary)

Each project publishes its machine-readable OpenAPI spec in its own repository, and the docs sites are rendered from it. Everything below was read from these files (fetched 2026-10-29, `develop` branch):

- Sonarr: <https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/Sonarr.Api.V3/openapi.json> (info text: "The v3 API docs apply to both v3 and v4 versions of Sonarr")
- Radarr: <https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json>
- Lidarr: <https://raw.githubusercontent.com/Lidarr/Lidarr/develop/src/Lidarr.Api.V1/openapi.json>
- Rendered docs: <https://sonarr.tv/docs/api/>, <https://radarr.video/docs/api/>, <https://lidarr.audio/docs/api/>

Not covered by the specs (flagged "unverified" where relevant): server-side latency, maximum `pageSize`, rate limits. The specs do not state them and I did not run a live instance.

## Versions and base paths

| App | API base | Spec version |
|---|---|---|
| Sonarr | `/api/v3` (covers Sonarr v3 and v4; some fields v4 only) | 3.0.0 |
| Radarr | `/api/v3` | 3.0.0 |
| Lidarr | `/api/v1` | 1.0.0 |

If the user runs behind a URL base, the system status `urlBase` field reports it (`SystemResource.urlBase`); the module config should simply take a full base URL.

## Authentication

Identical in all three specs. Two `apiKey` security schemes are declared:

- Header `X-Api-Key: <key>` (preferred; keeps the key out of URLs and proxy logs).
- Query parameter `apikey=<key>`.

Either satisfies the global `security` requirement. The key is per application instance (found in the app's Settings, General). One key per instance, so named instances in config map one-to-one to a (url, key) pair. Whether auth can be disabled for local addresses is an app setting, not an API property, so the module should always send the key.

## Endpoints for the five needs

All GET, all under the base path above. Shapes are from the specs' component schemas.

| Need | Endpoint | Cost | Notes |
|---|---|---|---|
| Identity/reachability, version | `/system/status` | tiny | `appName`, `instanceName`, `version`, `urlBase`, `startTime`. Good as the "is it up" probe, but any other call also proves it. |
| Queue count and problems | `/queue/status` | tiny, unpaged | `totalCount`, `count`, `unknownCount`, `errors`, `warnings`, `unknownErrors`, `unknownWarnings`. Identical schema in all three. Best default: one cheap call, no records. |
| Queue items (optional detail) | `/queue` | paged | `page`(1), `pageSize`(10), `sortKey`, `sortDirection`; returns `{page,pageSize,sortKey,sortDirection,totalRecords,records[]}`. Per-app extras below. |
| Wanted/missing count | `/wanted/missing?pageSize=1` | one paged query | Use `totalRecords` for the count; `monitored` defaults to `true`. Records are not needed. |
| Cutoff unmet count | `/wanted/cutoff?pageSize=1` | one paged query | Same shape; `monitored` defaults `true`. |
| Health warnings | `/health` | small | Array of `{id, source, type, message, wikiUrl}`; `type` is one of `ok`, `notice`, `warning`, `error`. |
| Upcoming calendar | `/calendar?start=<ISO>&end=<ISO>` | one range query | `start`/`end` are `date-time`. `unmonitored` defaults `false`. Returns a plain array (not paged). |
| Disk space | `/diskspace` | small | Array of `{id, path, label, freeSpace, totalSpace}` (bytes, integers). Same in all three. |

Count trick: the paged endpoints return `totalRecords` regardless of `pageSize`, so requesting `pageSize=1` gives a count without transferring the whole list. This is derived from the paging schema (every `*PagingResource` has `totalRecords`), not from an explicit doc statement; confirm against a recorded fixture.

## Differences between the three

- Base path and version: Sonarr/Radarr `/api/v3`, Lidarr `/api/v1`.
- Calendar include flags: Sonarr `includeSeries`, `includeEpisodeFile`, `includeEpisodeImages`; Lidarr `includeArtist`; Radarr has none (movie data is inline). For a summary, set `includeSeries=true` on Sonarr and `includeArtist=true` on Lidarr to get names in one call; otherwise episodes/albums only carry foreign ids.
- Wanted include flags: Sonarr `includeSeries`, `includeImages`; Lidarr `includeArtist`; Radarr none.
- Queue include flags: Sonarr `includeSeries`, `includeEpisode`, `includeUnknownSeriesItems`; Radarr `includeMovie`, `includeUnknownMovieItems`; Lidarr `includeArtist`, `includeAlbum`, `includeUnknownArtistItems`. Queue filters `languages` exists on Sonarr and Radarr but not Lidarr.
- Entity nouns: episode/series, movie, album/artist. Wanted/calendar records are `EpisodeResource`, `MovieResource`, `AlbumResource` respectively.
- `/system/status` has `isContainerized` on Sonarr and Radarr but not Lidarr (irrelevant to the MOTD).
- Sonarr v3 vs v4 are served by one spec, with some v4-only fields; a module should treat unknown/missing optional fields defensively.
- Calendar feeds (`/feed/v3/calendar/*.ics`, `/feed/v1/calendar/lidarr.ics`) exist but are iCal, not JSON; not useful here.

## Recommendation for the 2s budget

Per instance, fire these concurrently (stdlib `urllib` in a thread pool, or one thread per call), all cheap:

1. `/queue/status` (queue count, warnings/errors flags)
2. `/wanted/missing?pageSize=1` (missing count via `totalRecords`)
3. `/health` (count of non-`ok`/`notice` entries, surface messages)
4. `/calendar?start=now&end=now+N days` with the include flag for names
5. `/diskspace` only if the disk-space system module does not already cover it (Servarr's list is the app's view of its root folders, which can differ from the host filesystems)

Skip `/queue` detail and `/wanted/cutoff` in v1 unless a per-item list is wanted; they add cost without changing the headline. Use a per-request timeout well under the module budget, and degrade per call (a failed calendar call should not hide queue counts).

## Open points for the build ticket

- Record fixtures from a real instance to confirm the `totalRecords` count trick and field names on each app.
- Server latency and maximum `pageSize` are not documented in the specs (unverified).
- Calendar window length and whether to include unmonitored items (default `false`) are product choices.
