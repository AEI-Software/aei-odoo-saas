"""Maps a Discuss channel to its Claude Agent SDK session id.

Backed by a single JSON file on the agent's workspace PVC so a pod restart
doesn't lose conversation continuity. One tenant, one small file — no need
for a database for the MVP.
"""
import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_STORE_PATH = Path(os.getenv("SESSION_STORE_PATH", "/data/sessions.json"))
_lock = asyncio.Lock()


def _read() -> dict[str, str]:
    if not _STORE_PATH.exists():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("session_store: failed to read %s: %s", _STORE_PATH, exc)
        return {}


def _write(data: dict[str, str]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(_STORE_PATH)


async def get(channel_id: int) -> str | None:
    async with _lock:
        return _read().get(str(channel_id))


async def set(channel_id: int, sdk_session_id: str) -> None:
    async with _lock:
        data = _read()
        data[str(channel_id)] = sdk_session_id
        _write(data)
