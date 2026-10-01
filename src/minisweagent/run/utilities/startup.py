"""Startup orchestration for the ``mini`` CLI.

Pulls together the cross-cutting requirements that previously lived only
implicitly (or were missing entirely):

- Detect & apply the system language (i18n auto-switch on startup).
- Dynamically (re-)load the ``.env`` so model/key edits take effect at runtime.
- Resolve primary/fallback keys.
- Resume the last unfinished session when the user launches without a task.
- Print a concise, localized startup banner.

Keeping this in one place (and calling it as the very first action in ``mini``)
ensures every concern is applied consistently without touching unrelated modules.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from rich.console import Console

from minisweagent import __version__, global_config_file, i18n
from minisweagent.run.utilities.env import apply_key_fallback, key_status, reload_dotenv
from minisweagent.run.utilities.session import load_session

console = Console(highlight=False)
_ = i18n.t


def _mask_secret(key: str, value: str) -> str:
    """Show model names in full but mask secret values (API keys/tokens)."""
    if not value:
        return ""
    if key.endswith("_API_KEY") or "TOKEN" in key or "SECRET" in key:
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}…{value[-4:]}"
    return value


def _eager_load_model_engine() -> None:
    """Proactively import the heavy model engine (litellm) once.

    The first import of litellm is the single slowest part of startup (several
    seconds, with no output) and is otherwise triggered lazily inside
    ``get_model`` -- which made startup look frozen. Importing it here, behind a
    progress indicator, both surfaces that the program is working and ensures the
    cost is paid only once (subsequent imports hit the module cache).
    """
    import litellm  # noqa: F401  (side-effect: warm up the import)


def bootstrap() -> dict[str, Any]:
    """Run all startup concerns. Returns a small context dict for callers."""
    # 0. Performance: Litellm's import-time telemetry/network checks make startup
    #    slow. Disable them (idempotent -- only set when unset) before litellm is
    #    first imported by the model layer.
    os.environ.setdefault("LITELLM_TELEMETRY", "False")

    # 1. System language: detect the OS locale, then apply the user's preferred
    #    rule -- Chinese systems use Chinese directly; English/other systems are
    #    asked whether to switch to Chinese (defaulting to yes).
    lang = i18n.choose_language()
    if not os.getenv("MSWEA_SILENT_STARTUP"):
        console.print(_("Reading system language: [bold green]{lang}[/bold green]").format(lang=lang))

    # 2. Dynamic .env reload (so edits are picked up without a restart).
    reload_dotenv()
    if not os.getenv("MSWEA_SILENT_STARTUP"):
        console.print(
            _("Dynamic environment loaded from [bold green]'{path}'[/bold green]").format(path=global_config_file)
        )

    # 3. Primary/fallback key resolution + status reporting.
    applied = apply_key_fallback()
    if not os.getenv("MSWEA_SILENT_STARTUP"):
        for key, info in key_status().items():
            value = os.getenv(key) or os.getenv(f"{key}_FALLBACK") or ""
            # Mask secret-like values; show model names in full.
            display = _mask_secret(key, value)
            if info["active"] == "fallback":
                console.print(
                    _("Fallback key ({key}) = {value} (from *_FALLBACK).").format(key=key, value=display)
                )
            elif info["active"] == "primary":
                console.print(_("Primary key ({key}) = {value}.").format(key=key, value=display))
            else:
                console.print(_("No key set for ({key}); fallback unavailable.").format(key=key))

    # 4. Eagerly warm up the (heavy, silent) model engine behind a progress
    #    indicator, so startup doesn't look frozen during the long import.
    if os.getenv("MSWEA_SILENT_STARTUP"):
        _eager_load_model_engine()
    elif console.is_terminal:
        # Interactive terminal: show an animated spinner.
        with console.status(_("Initializing model engine (this may take a moment)...")):
            _eager_load_model_engine()
    else:
        # Non-terminal (piped/redirected): spinner wouldn't render, so print a
        # static progress line instead so the run still looks alive.
        console.print(_("Initializing model engine (this may take a moment)..."))
        _eager_load_model_engine()

    # 5. Banner.
    if not os.getenv("MSWEA_SILENT_STARTUP"):
        console.print(
            _("This is [bold green]mini-swe-agent[/bold green] version [bold green]{version}[/bold green].\n"
              "Check the [bold red]v2 migration guide[/] at [bold red]https://klieret.short.gy/mini-v2-migration[/]\n"
              "Loading global config from [bold green]'{config_file}'[/bold green]").format(
                version=__version__, config_file=global_config_file
            )
        )

    return {"language": lang, "fallback_keys": applied}


def resume_prompt() -> Path | None:
    """If there is an unfinished session, return its trajectory path.

    The ``mini`` CLI then resumes *directly* from that trajectory (restoring the
    full conversation and continuing from where it left off) -- there is no extra
    confirmation step, matching the requirement to "return to the last unfinished
    task on startup". When an interactive terminal is available we still show a
    short notice; the resume itself is automatic. The actual task is reconstructed
    from the trajectory's stored messages (already fully rendered), so we never
    re-template the task and accidentally duplicate its framing text.
    """
    session = load_session()
    if session is None:
        return None
    path: Path = session["_path"]
    try:
        import json as _json

        traj = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        console.print(_("Last session had no resumable task; starting fresh.").format())
        return None

    import sys

    interactive = bool(sys.stdin is not None and sys.stdin.isatty())
    if not interactive:
        # Unattended runs (CI, piped stdin): there is no one to ask, so we load
        # the trajectory automatically to avoid stalling on a prompt.
        return path

    # Interactive: show a preview and *ask* whether to load the trajectory file.
    messages = traj.get("messages", [])
    task_preview = ""
    if len(messages) > 1:
        content = messages[1].get("content", "")
        task_preview = content if isinstance(content, str) else str(content)
    console.print(_("Detected a previous session trajectory file:").format())
    console.print(f"[bold green]{path}[/bold green]")
    console.print(f"[bold]{task_preview[:200]}[/bold]")
    from rich.prompt import Confirm

    if Confirm.ask(_("Load this trajectory file and continue?"), default=True):
        return path
    return None


