"""Dynamic environment handling.

Addresses two known limitations of the original startup:

1. The global ``.env`` is loaded once at import time. This module lets the
   program *re-read* it at runtime (e.g. if the user edited it between runs or
   wants to switch models/keys without restarting a long-lived process).
2. "Primary / fallback" keys: if a primary key (or model name) is unset or the
   primary model fails, fall back to a ``*_FALLBACK`` counterpart.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from minisweagent import global_config_file
from minisweagent import i18n

_ = i18n.t

# Exceptions that indicate the *primary* key is rate-limited / unreachable and
# that retrying with a fallback key is worth attempting.
try:
    import litellm

    _FAILOVER_EXCEPTIONS = (
        litellm.exceptions.RateLimitError,
        litellm.exceptions.APIConnectionError,
        litellm.exceptions.ServiceUnavailableError,
        litellm.exceptions.APIError,
    )
except Exception:  # pragma: no cover - litellm always present
    _FAILOVER_EXCEPTIONS = ()


def reload_dotenv(path: str | os.PathLike[str] | None = None) -> None:
    """(Re)load the global ``.env`` file with ``override=True``.

    Unlike the import-time load, this picks up any edits made since startup.
    """
    load_dotenv(dotenv_path=path or global_config_file, override=True)


# Keys that should transparently fall back to a ``*_FALLBACK`` variant when
# the primary is missing. The model name is included so a secondary model can
# be used when the primary is unavailable.
_FALLBACK_KEYS = ("MSWEA_MODEL_NAME",)


def key_status() -> dict[str, dict[str, str]]:
    """Return the primary/fallback status of every relevant credential.

    For each primary key in ``_FALLBACK_KEYS`` (and any ``*_API_KEY`` present in
    the environment), report whether the primary is set, whether a ``<KEY>_FALLBACK``
    exists, and which one is currently active. Useful for displaying key info at
    startup ("main/fallback key").
    """
    candidate_keys = list(_FALLBACK_KEYS)
    for env_key in os.environ:
        if env_key.endswith("_API_KEY"):
            candidate_keys.append(env_key)
    status: dict[str, dict[str, str]] = {}
    for key in dict.fromkeys(candidate_keys):  # de-dupe, preserve order
        primary = bool(os.getenv(key))
        fallback = bool(os.getenv(f"{key}_FALLBACK"))
        if primary:
            active = "primary"
        elif fallback:
            active = "fallback"
        else:
            active = "none"
        status[key] = {"primary": primary, "fallback": fallback, "active": active}
    return status


def apply_key_fallback() -> list[str]:
    """Apply primary/fallback key resolution.

    For each primary key in ``_FALLBACK_KEYS`` (and any ``*_API_KEY`` present in
    the environment), if the primary is unset but a ``<KEY>_FALLBACK`` exists,
    copy the fallback value onto the primary. Returns the list of keys that were
    backfilled (so the caller can report which fallback keys are now active).
    """
    applied: list[str] = []
    candidate_keys = list(_FALLBACK_KEYS)
    for env_key in os.environ:
        if env_key.endswith("_API_KEY"):
            candidate_keys.append(env_key)

    for key in dict.fromkeys(candidate_keys):  # de-dupe, preserve order
        if os.getenv(key):
            continue
        fallback = os.getenv(f"{key}_FALLBACK")
        if fallback:
            os.environ[key] = fallback
            applied.append(key)
    return applied


def has_fallback(key: str) -> bool:
    """Whether a ``<KEY>_FALLBACK`` value is available for ``key``."""
    return bool(os.getenv(f"{key}_FALLBACK"))


def swap_to_fallback() -> bool:
    """Swap every primary key that has a ``*_FALLBACK`` to the fallback value.

    Returns True if at least one primary was swapped. This is the runtime
    failover step: when the primary key is rate-limited or unreachable, we move
    the fallback values onto the primary names so the next model call uses them.
    """
    swapped = False
    candidate_keys = list(_FALLBACK_KEYS)
    for env_key in os.environ:
        if env_key.endswith("_API_KEY"):
            candidate_keys.append(env_key)
    for key in dict.fromkeys(candidate_keys):
        fallback = os.getenv(f"{key}_FALLBACK")
        if fallback:
            os.environ[key] = fallback
            os.environ.pop(f"{key}_FALLBACK", None)
            swapped = True
    return swapped


def failover_model(model_config: dict | None = None) -> object | None:
    """Rebuild the model object using the fallback key.

    Call this after ``swap_to_fallback()`` (or when a primary call raised one of
    the failover exceptions) to obtain a fresh model that uses the secondary key.
    Returns ``None`` if no fallback is available.
    """
    from minisweagent.models import get_model

    if model_config is None:
        model_config = {}
    if not (has_fallback("MSWEA_MODEL_NAME") or any(
        k.endswith("_API_KEY") and has_fallback(k) for k in os.environ
    )):
        return None
    swap_to_fallback()
    return get_model(config=model_config)


def is_failover_exception(exc: BaseException) -> bool:
    """Whether ``exc`` is one we should retry against the fallback key."""
    return isinstance(exc, _FAILOVER_EXCEPTIONS)
