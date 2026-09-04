"""American odds, implied probability, and no-vig consensus."""

from __future__ import annotations


def american_to_implied(odds: int | float) -> float:
    american = int(odds)
    if american == 0:
        raise ValueError("American odds cannot be 0")
    if american > 0:
        return 100.0 / (american + 100.0)
    return abs(american) / (abs(american) + 100.0)


def implied_to_american(probability: float) -> int:
    if probability <= 0 or probability >= 1:
        raise ValueError("probability must be in (0, 1)")
    if probability >= 0.5:
        return int(round(-100 * probability / (1 - probability)))
    return int(round(100 * (1 - probability) / probability))


def remove_vig(implied: list[float]) -> list[float]:
    if not implied:
        raise ValueError("need at least one implied probability")
    if any(p <= 0 for p in implied):
        raise ValueError("implied probabilities must be positive")
    total = sum(implied)
    return [p / total for p in implied]


def no_vig(odds: list[int | float]) -> list[float]:
    return remove_vig([american_to_implied(value) for value in odds])


def no_vig_two_way(odds_a: int | float, odds_b: int | float) -> tuple[float, float]:
    fair = no_vig([odds_a, odds_b])
    return fair[0], fair[1]
