from __future__ import annotations

import json
import os
import urllib.request
from urllib.parse import urlsplit, urlunsplit


def canonical_url(value: str) -> str:
    try:
        parts = urlsplit(str(value or ""))
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return str(value or "")
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    except Exception:
        return str(value or "")


def chat_identity(value: str) -> str:
    path = urlsplit(canonical_url(value)).path
    marker = "/c/"
    if marker not in path:
        return ""
    return path.split(marker, 1)[1].split("/", 1)[0]


class CCSClient:
    def __init__(self, base_url: str | None = None, timeout: float = 3.0) -> None:
        self.base_url = (base_url or os.environ.get("CHATGPT_RDC_CCS_URL") or "http://127.0.0.1:43817").rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, *, payload: dict | None = None) -> dict:
        body = None
        headers = {}
        method = "GET"
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        req = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise RuntimeError("ccs_invalid_response")
        return data

    @staticmethod
    def _score(context: dict, old_url: str) -> tuple:
        exact = int(canonical_url(str(context.get("url") or "")) == old_url)
        has_note = int(bool(context.get("note") or context.get("codex_note")))
        has_twin = int(bool(context.get("twin")))
        prompt_count = len(context.get("prompt_ids") or [])
        updated = float(context.get("updated_at") or 0)
        return (exact, has_note, has_twin, prompt_count, updated)

    def find_context(self, old_url: str) -> dict | None:
        old_url = canonical_url(old_url)
        data = self._request("/api/list")
        contexts = data.get("contexts") or []
        exact = [c for c in contexts if canonical_url(str(c.get("url") or "")) == old_url]
        candidates = exact
        if not candidates:
            identity = chat_identity(old_url)
            if identity:
                candidates = [c for c in contexts if chat_identity(str(c.get("url") or "")) == identity]
        if not candidates:
            return None
        return max(candidates, key=lambda c: self._score(c, old_url))

    def replace_url(self, old_url: str, new_url: str) -> dict:
        old_url = canonical_url(old_url)
        new_url = canonical_url(new_url)
        if not old_url or not new_url:
            raise RuntimeError("ccs_url_missing")
        context = self.find_context(old_url)
        if context is None:
            return {"ok": True, "status": "not-found", "old_url": old_url, "new_url": new_url}

        before = {
            "note": str(context.get("note") or ""),
            "codex_note": str(context.get("codex_note") or ""),
            "notes_independent": bool(context.get("notes_independent")),
            "prompt_ids": sorted(str(x) for x in (context.get("prompt_ids") or [])),
            "twin": context.get("twin"),
        }
        result = self._request(
            "/api/context/replace-url",
            payload={
                "context_id": str(context["id"]),
                "old_url": old_url,
                "new_url": new_url,
            },
        )
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "ccs_replace_failed"))
        context_id = str((result.get("context") or {}).get("id") or context["id"])
        listed = self._request("/api/list").get("contexts") or []
        after = next((item for item in listed if str(item.get("id") or "") == context_id), None)
        if not isinstance(after, dict):
            raise RuntimeError("ccs_replace_readback_missing")
        if canonical_url(str(after.get("url") or "")) != new_url:
            raise RuntimeError("ccs_replace_readback_url_mismatch")

        after_state = {
            "note": str(after.get("note") or ""),
            "codex_note": str(after.get("codex_note") or ""),
            "notes_independent": bool(after.get("notes_independent")),
            "prompt_ids": sorted(str(x) for x in (after.get("prompt_ids") or [])),
            "twin": after.get("twin"),
        }
        if after_state != before:
            raise RuntimeError("ccs_replace_continuity_mismatch")
        return {
            "ok": True,
            "status": "replaced",
            "context_id": str(after["id"]),
            "old_url": old_url,
            "new_url": new_url,
        }
