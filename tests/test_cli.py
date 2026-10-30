import subprocess
import sys

from server_motd.cli import main


def test_main_exits_zero() -> None:
    assert main([]) == 0


def test_console_script_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "server_motd"], capture_output=True, check=False
    )
    assert result.returncode == 0
