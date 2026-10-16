from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def conversation_id_from_url(url: str) -> str | None:
    try:
        path = urlsplit(url).path
    except ValueError:
        return None
    marker = "/c/"
    if marker not in path:
        return None
    conversation_id = path.split(marker, 1)[1].split("/", 1)[0].strip()
    if not conversation_id or conversation_id.startswith("WEB:"):
        return None
    return conversation_id


def normalize_chat_url(url: str) -> str | None:
    conversation_id = conversation_id_from_url(url)
    if not conversation_id:
        return None
    parts = urlsplit(url)
    if parts.netloc and parts.netloc.lower() != "chatgpt.com":
        return None
    prefix = parts.path.split("/c/", 1)[0]
    path = f"{prefix}/c/{conversation_id}"
    return urlunsplit(("https", "chatgpt.com", path, "", ""))


def _url_score(url: str) -> int:
    path = urlsplit(url).path

def merge_chat_inventory(*args, **kwargs):
    raise RuntimeError("retired_global_discovery: C3 owns explicit run bindings")
