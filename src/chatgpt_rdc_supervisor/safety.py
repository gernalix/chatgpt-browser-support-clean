"""Process singleton and persistent, shared chat launch circuit breaker."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import time


KILL_SWITCH = Path.home() / ".config/c2/disable-chat-supervisor"
STATE_DIR = Path.home() / ".local/state/c2-supervisor"
MAX_TABS = 20
MAX_LAUNCHES = 3
WINDOW_SECONDS = 300


class LaunchDisabled(RuntimeError):
    pass


def ensure_enabled(kill_switch: Path = KILL_SWITCH) -> None:
    if kill_switch.exists():
        raise LaunchDisabled("chat_supervisor_kill_switch_active")


@contextmanager
def daemon_lock(state_dir: Path = STATE_DIR, kill_switch: Path = KILL_SWITCH):
    raise LaunchDisabled("retired_global_supervisor")
    yield  # context-manager protocol; unreachable


def reserve_launch(*, open_tabs: int, state_dir: Path = STATE_DIR,
                   kill_switch: Path = KILL_SWITCH, now: float | None = None) -> None:
    """Reserve one new chat before opening a tab or sending any message."""
    now = time.time() if now is None else now
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "chat-launch.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ensure_enabled(kill_switch)
        state_file = state_dir / "chat-launches.json"
        try:
            state = json.loads(state_file.read_text())
            launches = [float(t) for t in state.get("launches", []) if now - WINDOW_SECONDS < float(t) <= now]
        except (OSError, ValueError, TypeError):
            launches = []
        if open_tabs >= MAX_TABS or len(launches) >= MAX_LAUNCHES:
            kill_switch.parent.mkdir(parents=True, exist_ok=True)
            kill_switch.write_text("chat launch circuit breaker tripped\n")
            raise LaunchDisabled("chat_launch_circuit_breaker_tripped")
        launches.append(now)
        temporary = state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"launches": launches}, sort_keys=True) + "\n")
        temporary.replace(state_file)
