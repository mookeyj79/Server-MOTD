"""Repository hygiene that no linter covers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_index_has_only_lf_line_endings() -> None:
    # .gitattributes forces eol=lf; this catches a file committed before the
    # rule applied to it, or one marked -text by mistake.
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(
        ["git", "ls-files", "--eol"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    bad = [ln for ln in out.splitlines() if ln.split()[0] in ("i/crlf", "i/mixed")]
    hint = "CRLF in the index; run `git add --renormalize .`:\n"
    assert not bad, hint + "\n".join(bad)
