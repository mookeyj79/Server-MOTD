"""Sonarr, Radarr and Lidarr modules through the CLI seam, against a fake server."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tests.conftest import Run
from tests.fakeserver import FakeServer, closed_port_url

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
Golden = Callable[[str, str], None]
MakeServer = Callable[..., FakeServer]

KEY = "s3cret"


def servarr(
    make: MakeServer,
    service: str,
    *,
    health: str = "health_ok.json",
    version: str = "v3",
) -> FakeServer:
    srv = make(auth=("X-Api-Key", KEY))
    base = f"/api/{version}"
    srv.add(f"{base}/queue/status", fixture=f"{service}/queue_status.json")
    srv.add(f"{base}/wanted/missing", fixture=f"{service}/wanted_missing.json")
    srv.add(f"{base}/health", fixture=f"{service}/{health}")
    srv.add(f"{base}/calendar", fixture=f"{service}/calendar.json")
    return srv


def cfg_for(kind: str, url: str, extra: str = "", name: str | None = None) -> str:
    title = f'name = "{name}"\n' if name else ""
    return (
        f'[[modules]]\nkind = "{kind}"\n{title}url = "{url}"\n'
        f'api_key = "{KEY}"\n{extra}'
    )


def test_sonarr_golden(
    run_cli: RunCli,
    write_config: WriteConfig,
    fake_server: MakeServer,
    assert_golden: Golden,
) -> None:
    srv = servarr(fake_server, "sonarr", health="health_warn.json")
    cfg = write_config(cfg_for("sonarr", srv.url))
    r = run_cli("--config", str(cfg), "--width", "60", "--color", "never")
    assert r.code == 0
    assert_golden("sonarr.txt", r.out)
    # Cheap endpoints only, authenticated by header, missing counted via pageSize=1.
    assert {q.path for q in srv.requests} == {
        "/api/v3/queue/status",
        "/api/v3/wanted/missing",
        "/api/v3/health",
        "/api/v3/calendar",
    }
    assert all(q.headers["x-api-key"] == KEY for q in srv.requests)
    missing = next(q for q in srv.requests if q.path.endswith("/wanted/missing"))
    assert missing.query["pageSize"] == "1"


def test_two_sonarr_instances_have_distinct_titles(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    a = servarr(fake_server, "sonarr")
    b = servarr(fake_server, "sonarr")
    cfg = write_config(
        cfg_for("sonarr", a.url, name="Sonarr TV")
        + cfg_for("sonarr", b.url, name="Sonarr Anime")
    )
    out = run_cli("--config", str(cfg), "--color", "never").out
    assert "Sonarr TV" in out
    assert "Sonarr Anime" in out
    assert out.count("Missing") == 2


def test_radarr_and_lidarr_render(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    rad = servarr(fake_server, "radarr", health="health_error.json")
    lid = servarr(fake_server, "lidarr", version="v1")
    cfg = write_config(cfg_for("radarr", rad.url) + cfg_for("lidarr", lid.url))
    out = run_cli("--config", str(cfg), "--width", "70", "--color", "never").out
    assert "Radarr" in out
    assert "Lidarr" in out
    assert "No download client is available" in out
    assert "/api/v1/wanted/missing" in {q.path for q in lid.requests}


def test_warn_crit_applies_to_missing_only(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    # sonarr fixture: Missing 12, Queue 5 (with errors), health ok.
    srv = servarr(fake_server, "sonarr")
    outs = {}
    for label, extra in {
        "none": "",
        "warn": "warn = 10\ncrit = 20\n",
        "crit": "warn = 5\ncrit = 12\n",
    }.items():
        cfg = write_config(cfg_for("sonarr", srv.url, extra))
        outs[label] = run_cli("--config", str(cfg), "--color", "always").out
    yellow, red = "\x1b[33m", "\x1b[31m"
    assert yellow not in outs["none"] and red not in outs["none"]
    assert yellow in outs["warn"] and red not in outs["warn"]
    assert red in outs["crit"]
    queue_line = next(ln for ln in outs["crit"].splitlines() if "Queue" in ln)
    assert yellow not in queue_line and red not in queue_line


def test_unreachable_instance_is_unavailable(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    cfg = write_config(cfg_for("radarr", closed_port_url(), name="Down"))
    r = run_cli("--config", str(cfg), "--color", "never")
    assert r.code == 0
    assert "Down" in r.out
    assert "UNAVAILABLE" in r.out


def test_bad_api_key_is_unavailable(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = servarr(fake_server, "sonarr")
    cfg = write_config(cfg_for("sonarr", srv.url).replace(KEY, "wrong"))
    out = run_cli("--config", str(cfg), "--color", "never").out
    assert "UNAVAILABLE" in out
    assert "API key" in out


def test_missing_url_is_invalid_config(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    cfg = write_config('[[modules]]\nkind = "sonarr"\napi_key = "k"\n')
    out = run_cli("--config", str(cfg), "--color", "never").out
    assert "invalid config" in out
    assert "url" in out


def test_calendar_failure_does_not_hide_other_rows(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = servarr(fake_server, "sonarr")
    srv.add("/api/v3/calendar", json={"error": "boom"}, status=500)
    cfg = write_config(cfg_for("sonarr", srv.url))
    out = run_cli("--config", str(cfg), "--color", "never").out
    assert "UNAVAILABLE" not in out
    assert "Missing" in out
