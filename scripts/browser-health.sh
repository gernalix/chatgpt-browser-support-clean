#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/c2-supervisor"
mkdir -p "$STATE_DIR"
umask 077
write_state() {
    local state="$1"
    local temporary
    temporary="$(mktemp "$STATE_DIR/browser-health.XXXXXX")"
    printf '{"state":"%s","observed_at":"%s"}\n' "$state" "$(date -u +%FT%TZ)" > "$temporary"
    mv -f "$temporary" "$STATE_DIR/browser-health.json"
}

SESSION_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/chatgpt-rdc-supervisor/browser-session.json"
MAIN_PID="$(systemctl --user show chatgpt-rdc-supervisor.service --property=MainPID --value 2>/dev/null || true)"
if /usr/bin/python3 - "$SESSION_FILE" "$MAIN_PID" <<'PY'
import json
from pathlib import Path
import sys
import time

try:
    state = json.loads(Path(sys.argv[1]).read_text())
    main_pid = int(sys.argv[2])
    valid = (
        main_pid > 0
        and state.get("state") == "healthy"
        and state.get("pid") == main_pid
        and 0 <= time.time() - float(state["observed_at_epoch"]) <= 150
    )
except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
    valid = False
raise SystemExit(0 if valid else 1)
PY
then
    write_state healthy
    exit 0
fi

write_state unhealthy
echo "chatgpt-rdc-supervisor has no fresh normal-Chrome session; recovery controller must decide" >&2
exit 1
