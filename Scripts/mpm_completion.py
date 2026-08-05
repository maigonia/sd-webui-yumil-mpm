import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

import requests


API_SERVER_PORT = 19720
QUEUE_COMPLETION_ROUTE = "/yumil_mpm/queue-completion"
PROCESSING_COMPLETION_ID_ATTR = "_yumil_mpm_completion_id"
VALID_QUEUE_STATES = {"active", "completed", "exhausted"}
VALID_STOP_REASONS = {"queue_completed", "no_queue"}
COMPLETION_ID_PATTERN = re.compile(r"^cmp-[0-9a-fA-F]{32}$")


@dataclass(frozen=True)
class ParsedGenerationResponse:
    prompt_lookup: Dict[str, str]
    terminal_signal: Optional[dict]
    completion_id: Optional[str]


def is_valid_completion_id(value):
    return isinstance(value, str) and COMPLETION_ID_PATTERN.fullmatch(value) is not None


def parse_generation_response(data):
    """Parse prompts and optional queue-completion metadata from MPM."""
    if not isinstance(data, dict):
        return ParsedGenerationResponse({}, None, None)

    api_results = data.get("results", [])
    if not isinstance(api_results, list):
        api_results = []

    prompt_lookup = {}
    for result in api_results:
        if not (
            isinstance(result, dict)
            and result.get("success")
            and isinstance(result.get("category_name"), str)
            and isinstance(result.get("prompt"), str)
        ):
            continue
        prompt_lookup.setdefault(result["category_name"], result["prompt"])

    if data.get("should_continue") is not False:
        return ParsedGenerationResponse(prompt_lookup, None, None)

    queue_state = data.get("queue_state")
    stop_reason = data.get("stop_reason")
    terminal_signal = {
        "should_continue": False,
        "queue_state": queue_state if queue_state in VALID_QUEUE_STATES else None,
        "stop_reason": stop_reason if stop_reason in VALID_STOP_REASONS else None,
    }

    completion_id = data.get("completion_id")
    if not (
        data.get("completion_ack_required") is True
        and queue_state == "completed"
        and stop_reason == "queue_completed"
        and is_valid_completion_id(completion_id)
    ):
        completion_id = None

    return ParsedGenerationResponse(prompt_lookup, terminal_signal, completion_id)


def is_valid_task_id(value):
    return (
        isinstance(value, str)
        and 6 <= len(value) <= 256
        and value.startswith("task(")
        and value.endswith(")")
    )


class TerminalSignalRegistry:
    """Small runtime-only registry that isolates terminal signals by Forge task."""

    def __init__(self, ttl_seconds=600, max_entries=64, clock=time.monotonic):
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    def _prune_expired_locked(self, now):
        expired = [
            task_id
            for task_id, (created_at, _signal) in self._entries.items()
            if now - created_at >= self._ttl_seconds
        ]
        for task_id in expired:
            self._entries.pop(task_id, None)

    def record(self, task_id, tab, terminal_signal):
        if not is_valid_task_id(task_id) or tab not in {"txt2img", "img2img"}:
            return False
        if not isinstance(terminal_signal, dict) or terminal_signal.get("should_continue") is not False:
            return False

        sanitized = {
            "should_continue": False,
            "queue_state": terminal_signal.get("queue_state"),
            "stop_reason": terminal_signal.get("stop_reason"),
            "tab": tab,
        }
        now = self._clock()
        with self._lock:
            self._prune_expired_locked(now)
            self._entries.pop(task_id, None)
            self._entries[task_id] = (now, sanitized)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
        return True

    def take(self, task_id):
        if not is_valid_task_id(task_id):
            return None

        now = self._clock()
        with self._lock:
            self._prune_expired_locked(now)
            entry = self._entries.pop(task_id, None)
        return dict(entry[1]) if entry else None


terminal_signal_registry = TerminalSignalRegistry()


async def queue_completion_status(payload: dict):
    """Same-origin browser endpoint; never returns credentials or completion IDs."""
    from fastapi.responses import JSONResponse

    if not isinstance(payload, dict) or not is_valid_task_id(payload.get("task_id")):
        return JSONResponse({"error": "Invalid task_id"}, status_code=400)

    signal = terminal_signal_registry.take(payload["task_id"])
    if signal is None:
        return {"terminal": False}
    return {"terminal": True, **signal}


def register_completion_route(_demo, app):
    if any(getattr(route, "path", None) == QUEUE_COMPLETION_ROUTE for route in app.routes):
        return
    app.add_api_route(
        QUEUE_COMPLETION_ROUTE,
        queue_completion_status,
        methods=["POST"],
        name="yumil_mpm_queue_completion",
    )


def load_api_key():
    key_file = Path.home() / ".mpm" / "api_key"
    if key_file.exists():
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return os.environ.get("MPM_API_KEY", "")


def notify_mpm_finalization(completion_id, timeout_seconds=15):
    if not is_valid_completion_id(completion_id):
        raise ValueError("Invalid completion_id")

    api_key = load_api_key()
    if not api_key:
        raise RuntimeError("MPM API key is not configured")

    response = requests.post(
        f"http://127.0.0.1:{API_SERVER_PORT}/api/v1/generation/finalized",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"completion_id": completion_id, "status": "succeeded"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("result") not in {
        "accepted",
        "already_processed",
    }:
        raise RuntimeError("MPM returned an invalid finalization response")
    return payload


def attach_completion_id(processing, completion_id):
    if not is_valid_completion_id(completion_id):
        return False
    setattr(processing, PROCESSING_COMPLETION_ID_ATTR, completion_id)
    return True


def finalize_processing(processing, notifier: Optional[Callable[[str], object]] = None):
    completion_id = getattr(processing, PROCESSING_COMPLETION_ID_ATTR, None)
    if not is_valid_completion_id(completion_id):
        return False

    setattr(processing, PROCESSING_COMPLETION_ID_ATTR, None)
    (notifier or notify_mpm_finalization)(completion_id)
    return True
