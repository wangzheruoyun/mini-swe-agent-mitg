"""Resume support: re-open the last unfinished run on startup.

Persists a lightweight session pointer (the path of the current trajectory file)
so that, on the next invocation, the agent can offer to continue the previous
task instead of starting from scratch.
"""

from __future__ import annotations

import json
from pathlib import Path

from minisweagent import global_config_dir

# Tracks the most recently started run so a future invocation can resume it.
_SESSION_FILE = global_config_dir / "last_session.json"


def save_session(output_path: Path | None, task: str | None = None) -> None:
    """Record the in-progress session's trajectory path and task."""
    if not output_path:
        return
    payload = {"output_path": str(output_path), "task": task or ""}
    try:
        _SESSION_FILE.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass


def load_session() -> dict | None:
    """Return the saved session dict, or ``None`` if there is none / it finished."""
    if not _SESSION_FILE.is_file():
        return None
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    path = data.get("output_path")
    if not path or not Path(path).is_file():
        return None
    # Only resume runs that have not already produced a final "exit" message.
    try:
        traj = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    messages = traj.get("messages", [])
    if not messages or messages[-1].get("role") == "exit":
        return None
    data["_path"] = Path(path)
    return data
