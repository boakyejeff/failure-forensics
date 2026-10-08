"""Aggregate analyses over taxonomy assignments.

All helpers are pure functions over (cases, assignments) pairs so they are
easy to test and reuse from the CLI, notebooks, or the demo script.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from .ingest import FailureCase
from .taxonomy import Assignment


def bucket_distribution(assignments: Sequence[Assignment]) -> Dict[str, int]:
    """Count assignments per taxonomy bucket (uncertain cases included)."""
    counts: Dict[str, int] = {}
    for assignment in assignments:
        counts[assignment.category] = counts.get(assignment.category, 0) + 1
    return counts


def distribution_rows(
    assignments: Sequence[Assignment],
) -> List[Dict[str, object]]:
    """Bucket, count, and share rows sorted by count descending (then name)."""
    counts = bucket_distribution(assignments)
    total = len(assignments)
    rows = [
        {
            "bucket": bucket,
            "count": count,
            "share": (count / total) if total else 0.0,
        }
        for bucket, count in counts.items()
    ]
    rows.sort(key=lambda r: (-int(r["count"]), str(r["bucket"])))
    return rows


def _group_key(case: FailureCase, key: str) -> str:
    if key == "task_type":
        return case.task_type or "unknown"
    value = case.metadata.get(key, "unknown")
    return str(value) if value is not None else "unknown"


def breakdown_by(
    cases: Sequence[FailureCase],
    assignments: Sequence[Assignment],
    key: str,
) -> Dict[str, Dict[str, int]]:
    """Nested counts: group value -> bucket -> count.

    ``key`` may be "task_type" or any metadata key present on the cases.
    """
    result: Dict[str, Dict[str, int]] = {}
    for case, assignment in zip(cases, assignments):
        group = _group_key(case, key)
        buckets = result.setdefault(group, {})
        buckets[assignment.category] = buckets.get(assignment.category, 0) + 1
    return result


def low_confidence_cases(
    assignments: Sequence[Assignment],
    threshold: float = 0.45,
) -> List[Assignment]:
    """Assignments whose confidence falls below the threshold.

    These are the cases most worth sending to human review.
    """
    return [a for a in assignments if a.confidence < threshold]


def trend_by_group(
    cases: Sequence[FailureCase],
    assignments: Sequence[Assignment],
    group_key: str,
) -> Dict[str, Dict[str, int]]:
    """Bucket distribution per metadata group (e.g. model version, eval run).

    Useful for spotting regressions: a bucket whose share grows across runs.
    """
    return breakdown_by(cases, assignments, group_key)


def top_buckets(
    assignments: Sequence[Assignment], n: int = 3
) -> List[str]:
    """Names of the n most frequent buckets."""
    return [row["bucket"] for row in distribution_rows(assignments)[:n]]  # type: ignore[misc]
