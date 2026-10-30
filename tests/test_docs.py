"""README sample output and the example config, through the CLI seam (ticket #31)."""

from __future__ import annotations

import os
import re
import socket
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

from server_motd.modules import REGISTRY
from tests.conftest import Run
from tests.fakeserver import FakeServer

ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"
EXAMPLE = ROOT / "docs" / "example-config.toml"

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
MakeServer = Callable[..., FakeServer]

KEY = "s3cret"


SAMPLE = re.compile(r"(<!-- sample-output -->\n```text\n)(.*?)```", re.S)


def readme_sample() -> str:
    text = README.read_text(encoding="utf-8")
    m = SAMPLE.search(text)
    assert m, "README needs a ```text block after <!-- sample-output -->"
    return m.group(2)


@pytest.mark.usefixtures("pin_uptime")
def test_readme_sample_is_real_output(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    sonarr = fake_server(auth=("X-Api-Key", KEY))
    sonarr.add("/api/v3/queue/status", fixture="sonarr/queue_status.json")
    sonarr.add("/api/v3/wanted/missing", fixture="sonarr/wanted_missing.json")
    sonarr.add("/api/v3/health", fixture="sonarr/health_warn.json")
    sonarr.add("/api/v3/calendar", fixture="sonarr/calendar.json")
    tautulli = fake_server(auth=("X-Api-Key", KEY))
    tautulli.add(
        "/api/v2",
        fixture="tautulli/activity_streams.json",
        query={"cmd": "get_activity"},
    )
    tautulli.add(
        "/api/v2",
        fixture="tautulli/server_status_up.json",
        query={"cmd": "server_status"},
    )
    cfg = write_config(
        'title = "media-box"\n'
        '[[modules]]\nkind = "uptime"\n'
        f'[[modules]]\nkind = "sonarr"\nurl = "{sonarr.url}"\napi_key = "{KEY}"\n'
        f'[[modules]]\nkind = "tautulli"\nurl = "{tautulli.url}"\napi_key = "{KEY}"\n'
    )
    r = run_cli("--config", str(cfg), "--width", "64", "--color", "never")
    assert r.code == 0
    if os.environ.get("UPDATE_GOLDEN"):  # refresh the README block in place
        text = README.read_text(encoding="utf-8")
        new = SAMPLE.sub(lambda m: m[1] + r.out + "```", text)
        README.write_text(new, encoding="utf-8", newline="\n")
    assert readme_sample() == r.out


def example_modules() -> list[dict[str, object]]:
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    return list(data["modules"])


def test_example_config_covers_every_kind() -> None:
    assert {m["kind"] for m in example_modules()} == set(REGISTRY)


@pytest.mark.skipif(sys.platform == "win32", reason="load module is Linux only")
def test_example_config_validates_without_network(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    for var in (
        "SONARR_API_KEY",
        "RADARR_API_KEY",
        "LIDARR_API_KEY",
        "TAUTULLI_API_KEY",
        "SABNZBD_API_KEY",
        "QBIT_PASSWORD",
    ):
        monkeypatch.setenv(var, KEY)

    def no_network(*_a: object, **_k: object) -> None:
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    r = run_cli("--config", str(EXAMPLE), "check")
    assert "invalid config" not in r.out
    # Every module is listed; any failure is the blocked network or host.
    assert len([ln for ln in r.out.splitlines() if ln.strip()]) == len(
        example_modules()
    )
