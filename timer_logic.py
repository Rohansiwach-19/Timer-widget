"""
Timer Logic Model
Handles accurate countdown logic using a monotonic end timestamp.
No Qt or UI dependencies.
"""
from enum import Enum
import math
import time


class TimerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


class TimerLogic:
    def __init__(self, default_duration_sec: float = 25 * 60):
        self.total_duration: float = float(default_duration_sec)
        self.remaining_seconds: float = float(default_duration_sec)
        self.end_timestamp: float = 0.0
        self.state: TimerState = TimerState.IDLE

    def set_duration(self, seconds: float) -> bool:
        """
        Set a new total duration in seconds.
        Must be strictly greater than 0.
        """
        if seconds <= 0:
            return False
        self.total_duration = float(seconds)
        self.remaining_seconds = float(seconds)
        self.end_timestamp = 0.0
        self.state = TimerState.IDLE
        return True

    def start(self) -> None:
        """Start or resume countdown."""
        if self.state == TimerState.FINISHED or self.remaining_seconds <= 0:
            # Starting again after finishing restarts from the full duration
            self.remaining_seconds = self.total_duration

        self.end_timestamp = time.monotonic() + self.remaining_seconds
        self.state = TimerState.RUNNING

    def pause(self) -> None:
        """Pause the countdown."""
        if self.state == TimerState.RUNNING:
            now = time.monotonic()
            self.remaining_seconds = max(0.0, self.end_timestamp - now)
            self.state = TimerState.PAUSED

    def toggle(self) -> TimerState:
        """Toggle between start and pause."""
        if self.state == TimerState.RUNNING:
            self.pause()
        else:
            self.start()
        return self.state

    def reset(self) -> None:
        """Reset back to the last chosen total duration."""
        self.remaining_seconds = self.total_duration
        self.end_timestamp = 0.0
        self.state = TimerState.IDLE

    def tick(self) -> bool:
        """
        Periodic tick called by countdown loop.
        Returns True if the timer transitioned to FINISHED on this tick.
        """
        if self.state != TimerState.RUNNING:
            return False

        now = time.monotonic()
        remaining = self.end_timestamp - now
        if remaining <= 0.0:
            self.remaining_seconds = 0.0
            self.state = TimerState.FINISHED
            return True
        else:
            self.remaining_seconds = remaining
            return False

    @property
    def progress(self) -> float:
        """
        Remaining progress ratio from 0.0 to 1.0.
        1.0 = full duration remaining, 0.0 = complete.
        """
        if self.total_duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining_seconds / self.total_duration))

    def format_time(self) -> str:
        """
        Formats remaining time as MM:SS, or H:MM:SS when an hour or more remains.
        Rounds up to next whole second for a clean countdown display.
        """
        if self.remaining_seconds <= 0:
            return "00:00"

        rem = int(math.ceil(self.remaining_seconds))
        hours = rem // 3600
        mins = (rem % 3600) // 60
        secs = rem % 60

        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        else:
            return f"{mins:02d}:{secs:02d}"

