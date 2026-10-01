"""Lightweight internationalization (i18n) support for mini-swe-agent.

Design goals (per the minimal-change / maximal-impact constraints):
- Zero new third-party dependencies (pure stdlib + JSON catalogs).
- Source strings stay in English (the canonical catalog key), so the
  default language requires no translation table.
- The active language is detected from the system locale at import time,
  satisfying the requirement that the program switches to the system
  language on startup.
- A single helper ``t`` (aliased ``_``) is used everywhere; missing
  translations fall back to the English source string.

Catalog layout: ``minisweagent/i18n/locales/<lang>.json`` mapping
English source string -> localized string. ``en`` is implicit (identity).
"""

from __future__ import annotations

import json
import locale
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

locales_dir = Path(__file__).resolve().parent / "locales"

# Languages we ship catalogs for (besides the implicit English fallback).
SUPPORTED_LANGUAGES = ("en", "zh")

# Module-level state for the currently active language.
_current_language = "en"


def detect_system_language(default: str = "en") -> str:
    """Detect the system language and map it to a supported language code.

    Reads ``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES`` and ``LANG`` in that
    order (matching the POSIX/gettext convention) and returns the closest
    supported language. Falls back to ``default`` when nothing matches.
    """
    candidates: list[str] = []
    for env_var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.getenv(env_var) or ""
        if value:
            # LANGUAGE may be a colon-separated list; take the first entry.
            candidates.append(value.split(":")[0].split(".")[0].strip())
    # Also honor the Python locale as a last resort.
    try:
        candidates.append(locale.getlocale()[0] or "")
    except (ValueError, TypeError):
        pass

    for raw in candidates:
        if not raw:
            continue
        lower = raw.lower()
        # Match on the primary subtag (e.g. "zh_CN.UTF-8" -> "zh").
        primary = lower.split("_")[0]
        if primary in SUPPORTED_LANGUAGES:
            return primary
        # Friendly aliases.
        if primary in ("zh", "cmn", "zho"):
            return "zh"
        if primary in ("en", "eng"):
            return "en"
    return default


@lru_cache(maxsize=len(SUPPORTED_LANGUAGES))
def _load_catalog(lang: str) -> Mapping[str, str]:
    """Load the JSON catalog for ``lang`` (empty for the implicit English)."""
    if lang == "en":
        return {}
    path = locales_dir / f"{lang}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def set_language(lang: str | None = None) -> str:
    """Set the active language. If ``lang`` is falsy, detect from system."""
    global _current_language
    lang = (lang or "").strip().lower() or detect_system_language()
    primary = lang.split("_")[0]
    _current_language = primary if primary in SUPPORTED_LANGUAGES else "en"
    return _current_language


def choose_language() -> str:
    """Decide the runtime language following the user's preferred UX:

    - Detect the system language value first.
    - If the system is already Chinese, use Chinese directly (no prompt).
    - If the system is English (or otherwise not Chinese), *ask* the user
      whether to switch to Chinese, defaulting to yes. This avoids forcing an
      English-speaking system into Chinese while still offering Chinese to users
      whose OS locale reports English (common for many Chinese users).

    Returns the chosen language code and applies it via ``set_language``.
    """
    detected = detect_system_language()
    if detected == "zh":
        return set_language("zh")
    # Non-Chinese system: ask (only when a real terminal is available).
    import sys

    interactive = bool(sys.stdin is not None and sys.stdin.isatty())
    if interactive:
        from rich.console import Console
        from rich.prompt import Confirm

        console = Console(highlight=False)
        console.print(
            t("System language detected as {lang}. Switch to Chinese?").format(lang=detected)
        )
        if Confirm.ask(t("Switch to Chinese?"), default=True):
            return set_language("zh")
    return set_language(detected)


def get_language() -> str:
    """Return the currently active language code."""
    return _current_language


def t(message: str, /, **kwargs) -> str:
    """Translate ``message`` into the active language.

    Missing translations (including all of English) fall back to the source
    ``message``. Named ``kwargs`` are formatted into the (translated) string,
    so callers keep the same placeholders used in the English source.
    """
    catalog = _load_catalog(_current_language)
    translated = catalog.get(message, message)
    if kwargs:
        try:
            return translated.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return translated
    return translated


# Alias commonly used in gettext-style code.
_ = t

# Auto-detect and apply the system language at import time so that the
# program starts in the user's locale without any explicit opt-in.
set_language()


__all__ = [
    "SUPPORTED_LANGUAGES",
    "detect_system_language",
    "set_language",
    "get_language",
    "t",
    "_",
    "locales_dir",
]
