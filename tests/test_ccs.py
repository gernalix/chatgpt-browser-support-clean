from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chatgpt_rdc_supervisor.ccs import CCSClient, chat_identity
from chatgpt_rdc_supervisor.storage import Store


class FakeCCS(CCSClient):
    def __init__(self) -> None:
        super().__init__("http://unused.invalid")
        self.posts: list[dict] = []
        self.contexts = [
            {
                "id": "plain",
                "url": "https://chatgpt.com/c/old",
                "note": "",
                "codex_note": "",
                "notes_independent": False,
                "prompt_ids": [],
                "twin": None,
                "updated_at": 1,
            },
            {
                "id": "rich",
                "url": "https://chatgpt.com/c/old",
                "note": "keep me",
                "codex_note": "keep me",
                "notes_independent": False,
                "prompt_ids": ["123456"],
                "twin": {"codex_thread": "thread-1"},
                "updated_at": 2,
            },
        ]

    def _request(self, path: str, *, payload: dict | None = None) -> dict:
        if path == "/api/list":
            return {"ok": True, "contexts": self.contexts}
        if path == "/api/context/replace-url":
            assert payload is not None
            self.posts.append(payload)
            current = next(item for item in self.contexts if item["id"] == payload["context_id"])
            current = {**current, "url": payload["new_url"]}
            self.contexts = [current if item["id"] == current["id"] else item for item in self.contexts]
            return {"ok": True, "context": current}
        raise AssertionError(path)


class CCSClientTests(unittest.TestCase):
    def test_replace_prefers_context_with_continuity_state(self) -> None:
        client = FakeCCS()
        result = client.replace_url("https://chatgpt.com/c/old#fragment", "https://chatgpt.com/c/new")
        self.assertEqual("replaced", result["status"])
        self.assertEqual("rich", result["context_id"])
        self.assertEqual("rich", client.posts[0]["context_id"])
        self.assertEqual("https://chatgpt.com/c/old", client.posts[0]["old_url"])

    def test_chat_identity_handles_project_urls(self) -> None:
        self.assertEqual(
            "abc-123",
            chat_identity("https://chatgpt.com/g/project-name/c/abc-123"),
        )

    def test_ccs_pending_queue_is_durable_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td))
            with self.assertRaisesRegex(RuntimeError, "retired_supervisor"):
                store.enqueue_ccs_replacement("T", "old", "new")
            self.assertEqual([], list(Path(td).iterdir()))


if __name__ == "__main__":
    unittest.main()
