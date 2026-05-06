"""
Turn timer for 跑得快 (Pao De Kuai).

Provides a configurable asyncio-based turn timeout with an auto-pass callback.
When the timer expires, the registered async callback is invoked to auto-pass
the current player's turn.
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional


class TurnTimer:
    """Configurable asyncio turn timer with auto-pass callback.

    Usage:
        timer = TurnTimer()
        timer.start(duration_sec=15, on_timeout=async_auto_pass)

        # Query remaining time
        secs = timer.remaining_seconds()

        # Cancel before timeout (e.g., player acted)
        timer.cancel()
    """

    DEFAULT_DURATION = 30

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._deadline: Optional[float] = None
        self._on_timeout: Optional[Callable[[], Awaitable[None]]] = None
        self._duration: int = self.DEFAULT_DURATION

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Return True if a timer is currently active (not done/cancelled)."""
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------------
    # Timer lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        duration_sec: int = DEFAULT_DURATION,
        on_timeout: Callable[[], Awaitable[None]] = None,  # type: ignore[assignment]
    ) -> None:
        """Start a turn timer.

        Cancels any previously running timer first.  When *duration_sec*
        elapses, the async *on_timeout* callback is awaited.

        Args:
            duration_sec: Seconds before timeout (default 30).
            on_timeout: Async callable invoked when the timer expires.
        """
        # Cancel any existing timer (idempotent via cancel())
        self.cancel()

        self._duration = duration_sec
        self._on_timeout = on_timeout
        self._deadline = time.monotonic() + duration_sec
        self._task = asyncio.create_task(self._run_timer(duration_sec))

    def cancel(self) -> None:
        """Cancel the current timer (idempotent – safe to call repeatedly)."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._deadline = None
        # Keep _duration so reset() can use it if needed

    def reset(self) -> None:
        """Cancel and restart the timer with the same duration and callback.

        No-op if no timer has been started yet.
        """
        if self._on_timeout is not None:
            self.start(self._duration, self._on_timeout)

    def remaining_seconds(self) -> int:
        """Return the number of whole seconds remaining before timeout.

        Returns 0 if the timer is not running.
        """
        if self._deadline is None:
            return 0
        remaining = self._deadline - time.monotonic()
        return max(0, int(remaining))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run_timer(self, delay: float) -> None:
        """Sleep for *delay* seconds, then fire the timeout callback."""
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return  # cancelled – expected

        # Timer completed normally – invoke the callback
        if self._on_timeout is not None:
            await self._on_timeout()
