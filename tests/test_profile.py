"""Profile install/uninstall through the CLI, on temp profile files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from server_motd.profile import Environment
from tests.conftest import Run

Setup = Callable[..., Path]


@pytest.fixture
def profile_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Setup:
    def setup(policy: str = "RemoteSigned") -> Path:
        path = tmp_path / "ps7" / "profile.ps1"
        monkeypatch.setattr(
            "server_motd.profile.discover",
            lambda: Environment({"PowerShell 7": path}, {"PowerShell 7": policy}),
        )
        return path

    return setup


def test_install_creates_file_with_block(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    path = profile_env()
    assert run_cli("install-profile").code == 0
    text = path.read_bytes().decode("ascii")
    assert text.startswith("# >>> server-motd >>>\r\n")
    assert text.endswith("# <<< server-motd <<<\r\n")


def test_install_twice_yields_one_block(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    path = profile_env()
    path.parent.mkdir()
    path.write_bytes(b"Set-Alias a b\r\n")
    run_cli("install-profile")
    once = path.read_bytes()
    run_cli("install-profile")
    assert path.read_bytes() == once
    assert once.count(b"# >>> server-motd >>>") == 1


@pytest.mark.parametrize(
    "original",
    [
        b"Set-Alias a b",
        b"Set-Alias a b\r\n",
        b"one\ntwo\n",
        b"\xef\xbb\xbf# caf\xc3\xa9\r\n",
        "# caf\xe9\r\n".encode("utf-16"),
        b"# caf\xe9 ansi\r\n",
    ],
)
def test_install_then_uninstall_restores_bytes(
    original: bytes, profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    path = profile_env()
    path.parent.mkdir()
    path.write_bytes(original)
    run_cli("install-profile")
    installed = path.read_bytes()
    assert installed.startswith(original)  # user bytes, BOM and encoding untouched
    assert run_cli("uninstall-profile").code == 0
    assert path.read_bytes() == original


def test_uninstall_deletes_file_it_created(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    path = profile_env()
    run_cli("install-profile")
    run_cli("uninstall-profile")
    assert not path.exists()


def test_lf_newlines_and_text_after_block_preserved(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    path = profile_env()
    path.parent.mkdir()
    path.write_bytes(b"before\n")
    run_cli("install-profile")
    data = path.read_bytes()
    assert b"\r" not in data
    path.write_bytes(data + b"tail\n")
    run_cli("uninstall-profile")
    assert path.read_bytes() == b"before\ntail\n"


def test_unmatched_marker_is_refused(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    path = profile_env()
    path.parent.mkdir()
    original = b"x\r\n# >>> server-motd >>>\r\ny\r\n"
    path.write_bytes(original)
    result = run_cli("install-profile")
    assert result.code == 1
    assert "unmatched" in result.err
    assert path.read_bytes() == original


def test_restricted_policy_warns(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    profile_env(policy="Restricted")
    assert "Restricted" in run_cli("install-profile").err


def test_other_policy_does_not_warn(
    profile_env: Setup, run_cli: Callable[..., Run]
) -> None:
    profile_env(policy="RemoteSigned")
    assert run_cli("install-profile").err == ""
