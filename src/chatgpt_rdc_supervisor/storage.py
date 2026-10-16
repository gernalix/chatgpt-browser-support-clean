"""Optional task metadata projection; no ownership, discovery or lifecycle."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from .model import TaskConfig, xdg_state_home

class WriterLeaseConflict(RuntimeError):
    pass

def _retired(*args, **kwargs):
    raise WriterLeaseConflict("retired_supervisor_state: ownership and recovery belong to C3")

class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or xdg_state_home()
        self.tasks_dir = self.root / "tasks"

    def save_task(self, task: TaskConfig) -> None:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        path = self.tasks_dir / f"{task.task_id}.json"
        fd, temporary = tempfile.mkstemp(prefix=path.name+".", dir=self.tasks_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(task.to_dict(), handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load_task(self, task_id: str) -> TaskConfig:
        return TaskConfig.from_dict(json.loads((self.tasks_dir / f"{task_id}.json").read_text()))

    claim_writer = verify_writer = release_writer = writer_leases = _retired
    tasks = save_runtime = load_runtime = _retired
    chats = save_chats = global_state = set_lane_state = _retired
    pending_ccs_replacements = enqueue_ccs_replacement = remove_ccs_replacement = event = _retired
