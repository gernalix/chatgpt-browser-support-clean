from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class WorkerStatus(StrEnum):
    HEALTHY = "healthy"
    WORKING = "working"
    STALLED = "stalled"
    SUSPECTED_STALL = "suspected_stall"
    VERIFYING = "verifying"
    GLOBAL_DEGRADED = "global_degraded"
    CONTEXT_RISK = "context-risk"
    HUMAN_REQUIRED = "human-required"
    COMPLETE = "complete"
    PAUSED = "paused"
    ERROR = "error"


class Action(StrEnum):
    NONE = "none"
    VERIFY = "verify"
    CONTINUE = "continue"
    NUDGE_CONTINUE = "nudge-continue"
    REQUEST_CHECKPOINT = "request-checkpoint"
    RETRY = "retry"
    RELOAD = "reload"
    ROLLOVER = "rollover"
    HUMAN_REQUIRED = "human-required"
    COMPLETE = "complete"


@dataclass
class Thresholds:
    checkpoint_max_age_s: int = 600
    checkpoint_grace_s: int = 180
    idle_continue_s: int = 180
    generation_suspect_s: int = 40
    generation_verify_s: int = 90
    generation_stall_s: int = 180
    max_worker_age_s: int = 1200
    soft_turns: int = 60
    hard_turns: int = 80
    soft_chars: int = 140_000
    hard_chars: int = 200_000
    max_recovery_attempts: int = 3
    max_rollovers_per_checkpoint: int = 2
    rate_limit_backoff_s: int = 1800


@dataclass
class TaskConfig:
    task_id: str
    state_file: str
    repo_root: str
    chat_url: str
    project_url: str | None = None
    enabled: bool = True
    autopilot: bool = True
    thresholds: Thresholds = field(default_factory=Thresholds)
    work_item_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskConfig":
        raw = dict(data)
        raw["thresholds"] = Thresholds(**raw.get("thresholds", {}))
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def lease_work_item_id(self) -> str:
        return self.work_item_id or self.task_id


@dataclass
class BrowserSnapshot:
    url: str
    title: str
    authenticated: bool
    composer: bool
    generating: bool
    retry_available: bool
    error_kind: str | None
    slow_thinking: bool
    slow_notice_signature: str
    turn_count: int
    text_chars: int
    signature: str


@dataclass
class CheckpointSnapshot:
    exists: bool
    committed: bool
    pushed: bool
    commit: str | None
    commit_epoch: float | None
    dirty: bool
    next_action: str | None
    has_blocker: bool
    complete: bool
    terminal: bool = False


@dataclass
class RuntimeState:
    status: WorkerStatus = WorkerStatus.HEALTHY
    last_action: Action = Action.NONE
    last_action_epoch: float = 0.0
    last_progress_epoch: float = 0.0
    last_signature: str = ""
    recovery_attempts: int = 0
    checkpoint_requested_epoch: float = 0.0
    last_checkpoint_commit: str = ""
    rollover_count: int = 0
    rollovers_since_checkpoint: int = 0
    human_reason: str | None = None
    rate_limit_until_epoch: float = 0.0
    worker_started_epoch: float = 0.0
    last_slow_notice_signature: str = ""
    last_verification_epoch: float = 0.0
    rollover_recovery_pending_epoch: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeState":
        raw = dict(data)
        raw["status"] = WorkerStatus(raw.get("status", WorkerStatus.HEALTHY))
        raw["last_action"] = Action(raw.get("last_action", Action.NONE))
        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["last_action"] = self.last_action.value
        return data


def xdg_state_home() -> Path:
    return Path.home() / ".local" / "state" / "chatgpt-rdc-supervisor"
