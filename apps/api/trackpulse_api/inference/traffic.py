from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

# V1 scoring weights — heuristic values chosen to produce a meaningful 0-100
# scale for F1 race conditions (up to 20 cars).
#
# Assumption: each car in the same segment contributes 20 points; each car in
# an immediately adjacent segment (neighbour in track order) contributes 10
# points; a car whose interval to the car ahead is at or below the pressure
# threshold adds an additional 15 points to the segment it occupies.
# The circuit is treated as a closed loop so the first and last segments are
# adjacent.  All scores are clamped to [0, 100].

_SAME_SEGMENT_POINTS: float = 20.0
_ADJACENT_SEGMENT_POINTS: float = 10.0
_CLOSE_INTERVAL_POINTS: float = 15.0
_CLOSE_INTERVAL_THRESHOLD_S: float = 1.0


@dataclass(frozen=True)
class CarSegmentState:
    """Minimal derived state needed to compute traffic for one car.

    ``segment_id`` must match an entry in the ``segment_order`` passed to
    :func:`compute_traffic_scores`; cars with an unknown ``segment_id`` are
    silently excluded from scoring.

    ``interval_ahead_s`` is the gap to the car immediately ahead in race order.
    ``None`` means the data is unavailable (e.g. race leader or missing
    telemetry); a value of ``0.0`` or below is treated as no pressure.
    """

    segment_id: str
    interval_ahead_s: float | None = field(default=None)


def _build_adjacency(segment_order: Sequence[str]) -> dict[str, set[str]]:
    """Return a mapping from segment_id to its immediate neighbours.

    The circuit is modelled as a closed loop: the last segment is adjacent to
    the first.
    """
    n = len(segment_order)
    adjacency: dict[str, set[str]] = {}
    for i, seg_id in enumerate(segment_order):
        prev_id = segment_order[(i - 1) % n]
        next_id = segment_order[(i + 1) % n]
        adjacency[seg_id] = {prev_id, next_id}
    return adjacency


def compute_traffic_scores(
    car_states: Iterable[CarSegmentState],
    segment_order: Sequence[str],
) -> dict[str, float]:
    """Compute a per-segment traffic score from current car segment assignments.

    Parameters
    ----------
    car_states:
        Iterable of :class:`CarSegmentState` representing every car whose
        position is currently known.  Cars whose ``segment_id`` is not in
        ``segment_order`` are ignored.
    segment_order:
        Ordered list of all segment IDs around the circuit.  Order defines
        adjacency; the list is treated as a closed loop.

    Returns
    -------
    dict[str, float]
        Mapping of ``segment_id`` → traffic score in ``[0.0, 100.0]``.  Only
        segments that have a non-zero score are included; call sites that need
        all segments can default missing keys to ``0.0``.

    Notes
    -----
    This is a pure, deterministic function returning *derived* values only.
    It does not read from any external source and has no side effects.
    """
    if not segment_order:
        return {}

    segment_set = set(segment_order)
    adjacency = _build_adjacency(segment_order)

    # Materialise the iterable once so we can traverse it efficiently.
    states = [s for s in car_states if s.segment_id in segment_set]

    raw_scores: dict[str, float] = {}

    for state in states:
        seg = state.segment_id

        # Contribution to the car's own segment.
        raw_scores[seg] = raw_scores.get(seg, 0.0) + _SAME_SEGMENT_POINTS

        # Optional pressure bonus for a close interval.
        if (
            state.interval_ahead_s is not None
            and 0.0 < state.interval_ahead_s <= _CLOSE_INTERVAL_THRESHOLD_S
        ):
            raw_scores[seg] = raw_scores.get(seg, 0.0) + _CLOSE_INTERVAL_POINTS

        # Contribution to neighbouring segments.
        for neighbour in adjacency[seg]:
            raw_scores[neighbour] = raw_scores.get(neighbour, 0.0) + _ADJACENT_SEGMENT_POINTS

    return {seg: min(100.0, score) for seg, score in raw_scores.items()}
