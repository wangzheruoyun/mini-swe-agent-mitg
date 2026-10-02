"""Startup progress bar for the ``mini`` CLI.

The heaviest part of startup is importing ``litellm`` (tens of seconds, with no
output), which made the program look frozen. This module shows a *real*
percentage progress bar that appears the instant the CLI launches and advances
through the actual startup stages. The long engine-import stage is tracked with a
timer that maps elapsed time to percentage, so the bar keeps moving instead of
stalling.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

# Estimated duration (seconds) of the heavy model-engine import. Used only to map
# elapsed time to a percentage while that single blocking call runs; the value is
# intentionally a soft upper bound so the bar never appears stuck.
_ENGINE_IMPORT_ESTIMATE_S = 30.0

# Cumulative weights for each startup stage. The engine stage carries most of the
# weight because it dominates startup time.
_STAGES = (
    ("Detecting language", 5),
    ("Loading environment", 5),
    ("Resolving keys", 5),
    ("Initializing model engine", 70),
    ("Building agent", 15),
)
_TOTAL_WEIGHT = sum(w for _, w in _STAGES)
_STAGE_INDEX = {name: i for i, (name, _) in enumerate(_STAGES)}


class StartupProgress:
    """A thin wrapper around a Rich ``Progress`` bar for startup."""

    def __init__(self) -> None:
        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            transient=False,
        )
        self._task_id = self._progress.add_task("Starting up...", total=100.0)
        self._completed_weight = 0.0
        self._timer: threading.Thread | None = None
        self._stop_timer = threading.Event()
        self._engine_running = False

    def start(self) -> "StartupProgress":
        # Print the bar immediately so startup never looks frozen.
        self._progress.start()
        return self

    def _set_weight(self, weight: float) -> None:
        self._progress.update(self._task_id, completed=self._completed_weight + weight)

    def stage(self, name: str) -> None:
        """Mark a (fast) named stage as completed and advance the bar."""
        idx = _STAGE_INDEX.get(name)
        if idx is None:
            return
        weight = _STAGES[idx][1]
        self._completed_weight += weight
        self._set_weight(0.0)
        self._progress.update(self._task_id, description=f"{name}... done")

    def run_engine_init(self, fn: Callable[[], None], estimate_s: float = _ENGINE_IMPORT_ESTIMATE_S) -> None:
        """Run the blocking ``fn`` (the heavy engine import) while advancing the
        bar in proportion to elapsed time -- a genuine, moving percentage.
        """
        idx = _STAGE_INDEX["Initializing model engine"]
        weight = _STAGES[idx][1]
        self._progress.update(self._task_id, description="Initializing model engine...")

        start = time.time()
        self._engine_running = True

        def _tick() -> None:
            while self._engine_running and not self._stop_timer.is_set():
                elapsed = time.time() - start
                frac = min(elapsed / max(estimate_s, 0.1), 1.0)
                self._set_weight(weight * frac)
                time.sleep(0.1)

        self._timer = threading.Thread(target=_tick, daemon=True)
        self._timer.start()
        try:
            fn()
        finally:
            self._engine_running = False
            self._stop_timer.set()
            if self._timer is not None:
                self._timer.join(timeout=1.0)
            self._completed_weight += weight
            self._set_weight(0.0)
            self._progress.update(self._task_id, description="Initializing model engine... done")

    def pause(self) -> None:
        """Temporarily stop the live bar (e.g. before an interactive prompt).

        The progress *state* (completed weight) is preserved, so ``resume``
        continues from exactly where we left off. This is needed because an
        interactive ``rich`` prompt cannot share the terminal with a live
        progress bar without corrupting the display.
        """
        self._stop_timer.set()
        self._progress.stop()

    def resume(self) -> None:
        """Resume the live bar after ``pause``; progress state is preserved."""
        self._stop_timer.clear()
        self._progress.start()

    def finish(self) -> None:
        self._stop_timer.set()
        self._completed_weight = float(_TOTAL_WEIGHT)
        self._set_weight(0.0)
        self._progress.update(self._task_id, description="Ready", completed=100.0)
        self._progress.stop()


def startup_progress() -> StartupProgress:
    """Construct and immediately start a startup progress bar."""
    return StartupProgress().start()
