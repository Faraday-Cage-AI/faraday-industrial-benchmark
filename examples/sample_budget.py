"""Persistent pre-request dollar reservations for a bounded sample experiment.

Callers must supply a conservative upper bound from counted input tokens,
maximum generated tokens, and verified provider rates BEFORE submitting a paid
request. Unknown/failed requests retain their full reservation. Never refund an
ambiguous request based on a local timeout. This ledger alone is not an adapter.
"""

import fcntl
import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


def dollars(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amount must be finite and nonnegative")
    return amount


class SampleBudget:
    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def create(cls, path, model_limits, episode_limits, total="90"):
        total = dollars(total)
        if total > 100:
            raise ValueError("Experiment authorization is at most $100")
        data = {
            "total_limit": str(total),
            "model_limits": {key: str(dollars(value)) for key, value in model_limits.items()},
            "episode_limits": {key: str(dollars(value)) for key, value in episode_limits.items()},
            "requests": {},
        }
        with Path(path).open("x") as stream:
            json.dump(data, stream)
        return cls(path)

    @contextmanager
    def transaction(self):
        # Hold an exclusive lock across read/check/write, including separate workers.
        # A corrupt/partial file fails closed on reload, never resets the budget.
        with self.path.open("r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            data = json.load(stream)
            yield data
            stream.seek(0)
            json.dump(data, stream, indent=2)
            stream.truncate()
            stream.flush()
            import os

            os.fsync(stream.fileno())

    def reserve(self, request_id, model, episode, upper_bound):
        amount = dollars(upper_bound)
        if amount == 0:
            raise ValueError("Paid request needs a positive reservation")
        with self.transaction() as data:
            if request_id in data["requests"]:
                raise ValueError("Request ID already reserved; do not submit again")
            model_limit = dollars(data["model_limits"][model])
            episode_limit = dollars(data["episode_limits"][episode])
            rows = list(data["requests"].values())
            checks = (
                (rows, dollars(data["total_limit"])),
                ([r for r in rows if r["model"] == model], model_limit),
                ([r for r in rows if r["episode"] == episode], episode_limit),
            )
            if any(
                sum((dollars(r["charged_or_reserved"]) for r in subset), Decimal(0)) + amount
                > limit
                for subset, limit in checks
            ):
                raise BudgetExceeded("Stop before submission: dollar budget exhausted")
            data["requests"][request_id] = {
                "model": model,
                "episode": episode,
                "reserved": str(amount),
                "charged_or_reserved": str(amount),
                "status": "reserved",
            }

    def settle(self, request_id, actual):
        actual = dollars(actual)
        with self.transaction() as data:
            row = data["requests"][request_id]
            if row["status"] != "reserved":
                raise ValueError("Request has already been settled")
            if actual > dollars(row["reserved"]):
                raise BudgetExceeded(
                    "Quote was not a valid upper bound; retain reservation and stop"
                )
            row.update(status="settled", charged_or_reserved=str(actual))
