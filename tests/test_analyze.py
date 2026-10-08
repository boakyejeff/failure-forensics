"""Tests for aggregation helpers in analyze.py."""

from failure_forensics import assign_failures
from failure_forensics.analyze import (
    bucket_distribution,
    distribution_rows,
    breakdown_by,
    low_confidence_cases,
    trend_by_group,
)


def test_bucket_distribution_counts(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    counts = bucket_distribution(assignments)
    assert sum(counts.values()) == len(cases)
    assert counts.get("refusal", 0) >= 1


def test_distribution_rows_share_sums_to_one(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    rows = distribution_rows(assignments)
    assert abs(sum(r["share"] for r in rows) - 1.0) < 1e-9
    counts = [r["count"] for r in rows]
    assert counts == sorted(counts, reverse=True)


def test_breakdown_by_task_type(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    table = breakdown_by(cases, assignments, "task_type")
    assert "math" in table
    assert sum(sum(buckets.values()) for buckets in table.values()) == len(cases)


def test_breakdown_by_metadata_key():
    from failure_forensics import FailureCase

    cases = [
        FailureCase(id="a", prompt="p", model_output="o",
                    metadata={"model": "m1"}),
        FailureCase(id="b", prompt="p", model_output="o",
                    metadata={"model": "m2"}),
    ]
    assignments = assign_failures(cases)
    table = breakdown_by(cases, assignments, "model")
    assert set(table) == {"m1", "m2"}


def test_low_confidence_cases_empty_for_clear(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    assert low_confidence_cases(assignments) == []


def test_trend_by_group(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    for i, case in enumerate(cases):
        case.metadata["batch"] = f"run-{i % 2}"
    assignments = assign_failures(cases)
    trend = trend_by_group(cases, assignments, "batch")
    assert set(trend) == {"run-0", "run-1"}
    assert sum(sum(b.values()) for b in trend.values()) == len(cases)
