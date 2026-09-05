"""Core retry policy model: parsing, delay math, and schedule generation.

Delays are reported as (min, max) bounds rather than a single sampled
value, because jittered policies are random by design. A single sample
wouldn't be reproducible or useful for reasoning about a policy; the
bounds are.
"""

from dataclasses import dataclass
from typing import Optional

VALID_JITTER = {"none", "full", "equal"}
VALID_STRATEGY = {"exponential", "linear", "constant"}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay: float
    multiplier: float = 2.0
    max_delay: Optional[float] = None
    jitter: str = "none"
    strategy: str = "exponential"

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise PolicyError("policy must be a JSON object")

        if "max_attempts" not in data:
            raise PolicyError("missing required field: max_attempts")
        try:
            max_attempts = int(data["max_attempts"])
        except (TypeError, ValueError):
            raise PolicyError("max_attempts must be an integer")
        if max_attempts < 1:
            raise PolicyError("max_attempts must be at least 1")

        if "base_delay" not in data:
            raise PolicyError("missing required field: base_delay")
        try:
            base_delay = float(data["base_delay"])
        except (TypeError, ValueError):
            raise PolicyError("base_delay must be a number")
        if base_delay < 0:
            raise PolicyError("base_delay cannot be negative")

        strategy = data.get("strategy", "exponential")
        if strategy not in VALID_STRATEGY:
            raise PolicyError(
                "strategy must be one of {}, got {!r}".format(sorted(VALID_STRATEGY), strategy)
            )

        if strategy != "exponential" and "multiplier" in data:
            raise PolicyError("multiplier only applies to the exponential strategy")

        try:
            multiplier = float(data.get("multiplier", 2.0))
        except (TypeError, ValueError):
            raise PolicyError("multiplier must be a number")
        if multiplier < 1:
            raise PolicyError("multiplier must be at least 1")

        max_delay = data.get("max_delay")
        if max_delay is not None:
            try:
                max_delay = float(max_delay)
            except (TypeError, ValueError):
                raise PolicyError("max_delay must be a number")
            if max_delay < base_delay:
                raise PolicyError("max_delay cannot be smaller than base_delay")

        jitter = data.get("jitter", "none")
        if jitter not in VALID_JITTER:
            raise PolicyError(
                "jitter must be one of {}, got {!r}".format(sorted(VALID_JITTER), jitter)
            )

        return cls(
            max_attempts=max_attempts,
            base_delay=base_delay,
            multiplier=multiplier,
            max_delay=max_delay,
            jitter=jitter,
            strategy=strategy,
        )

    def _uncapped_delay(self, attempt):
        if self.strategy == "constant":
            return self.base_delay
        if self.strategy == "linear":
            return self.base_delay * attempt
        return self.base_delay * (self.multiplier ** (attempt - 1))

    def will_retry(self, attempt):
        return 1 <= attempt <= self.max_attempts

    def _capped_delay(self, attempt):
        if attempt < 1:
            raise PolicyError("attempt must be at least 1")
        raw = self._uncapped_delay(attempt)
        return raw if self.max_delay is None else min(raw, self.max_delay)

    def delay_bounds(self, attempt):
        """Return (min, max) possible delay in seconds before this attempt."""
        capped = self._capped_delay(attempt)
        if self.jitter == "none":
            return capped, capped
        if self.jitter == "full":
            return 0.0, capped
        # "equal": half the delay is fixed, half is randomized on top of it
        return capped / 2, capped

    def sample_delay(self, attempt, rng):
        """Draw one concrete delay for this attempt using rng (a random.Random)."""
        capped = self._capped_delay(attempt)
        if self.jitter == "none":
            return capped
        if self.jitter == "full":
            return rng.uniform(0.0, capped)
        # "equal": half the delay is fixed, half is randomized on top of it
        return capped / 2 + rng.uniform(0.0, capped / 2)

    def schedule(self):
        """Full per-attempt delay and cumulative elapsed time bounds."""
        rows = []
        cumulative_min = 0.0
        cumulative_max = 0.0
        for attempt in range(1, self.max_attempts + 1):
            lo, hi = self.delay_bounds(attempt)
            cumulative_min += lo
            cumulative_max += hi
            rows.append((attempt, lo, hi, cumulative_min, cumulative_max))
        return rows

    def simulate(self, rng):
        """One concrete run through the schedule, sampling each attempt's delay."""
        rows = []
        cumulative = 0.0
        for attempt in range(1, self.max_attempts + 1):
            delay = self.sample_delay(attempt, rng)
            cumulative += delay
            rows.append((attempt, delay, cumulative))
        return rows
