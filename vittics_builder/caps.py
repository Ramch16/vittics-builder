"""Hard per-run resource caps shared by every agent working on one project (benchmark slot).

A model call is admitted only if what the project has already used, plus what calls in flight have reserved,
plus this call's worst case, stays within the caps. The worst case is the call's input estimate plus its
maximum output (`max_tokens`). After the call, the reservation is replaced by the usage actually recorded.
Several agents may run in parallel threads, so admission and settlement share one lock.

Unknown usage cannot certify compliance: with a cost cap set, a call whose price is unknown (an unpriced
model, a CLI engine that reports no cost) is refused rather than counted as free. CLI engines run many turns
inside one call and cannot be bounded per call, so they are refused whenever a token or cost cap is set.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


class CapExceeded(RuntimeError):
    """A call would exceed a cap, or the run's time is up. `kind` is "tokens", "cost", "wall" or "unbounded"."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass
class RunCaps:
    max_total_tokens: int | None = None
    max_cost: float | None = None
    max_wall_seconds: float | None = None
    started: float = field(default_factory=time.monotonic)
    used_tokens: int = 0
    used_cost: float = 0.0
    _reserved: dict = field(default_factory=dict)
    _next: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _check_wall(self) -> None:
        if self.max_wall_seconds is not None and time.monotonic() - self.started >= self.max_wall_seconds:
            raise CapExceeded("wall", f"Run time cap of {self.max_wall_seconds:g}s reached.")

    def admit(self, tokens: int, cost: float | None, *, bounded: bool = True) -> int:
        """Reserve a call's worst case (`tokens`, `cost`; cost None = unknown). Returns a ticket for settle()."""
        with self._lock:
            self._check_wall()
            if not bounded and (self.max_total_tokens is not None or self.max_cost is not None):
                raise CapExceeded("unbounded", "This engine's usage cannot be bounded per call; it cannot run "
                                  "under a token or cost cap.")
            if self.max_cost is not None and cost is None:
                raise CapExceeded("cost", "The call's price is unknown, so it cannot be admitted under a cost cap.")
            held_tokens = sum(t for t, _ in self._reserved.values())
            held_cost = sum(c or 0.0 for _, c in self._reserved.values())
            if self.max_total_tokens is not None and self.used_tokens + held_tokens + tokens > self.max_total_tokens:
                raise CapExceeded("tokens", f"Token cap {self.max_total_tokens} would be exceeded "
                                  f"(used {self.used_tokens}, in flight {held_tokens}, this call up to {tokens}).")
            if self.max_cost is not None and self.used_cost + held_cost + (cost or 0.0) > self.max_cost + 1e-12:
                raise CapExceeded("cost", f"Cost cap {self.max_cost:g} would be exceeded "
                                  f"(used {self.used_cost:.6f}, in flight {held_cost:.6f}, this call up to {cost:.6f}).")
            self._next += 1
            self._reserved[self._next] = (tokens, cost)
            return self._next

    def settle(self, ticket: int, tokens: int, cost: float) -> None:
        """Replace a reservation with the usage actually recorded."""
        with self._lock:
            self._reserved.pop(ticket, None)
            self.used_tokens += int(tokens)
            self.used_cost += float(cost or 0.0)

    def release(self, ticket: int) -> None:
        """Drop a reservation whose call failed before reporting usage."""
        with self._lock:
            self._reserved.pop(ticket, None)

    def snapshot(self) -> dict:
        with self._lock:
            return {"used_tokens": self.used_tokens, "used_cost": self.used_cost, "in_flight": len(self._reserved),
                    "elapsed_seconds": round(time.monotonic() - self.started, 3)}


def estimate_input_tokens(system: str, messages: list, tools: list) -> int:
    """A conservative input estimate: about one token per three characters of everything sent."""
    import json
    size = len(system) + len(json.dumps(messages, default=str)) + len(json.dumps(tools, default=str))
    return size // 3 + 1
