"""Tests for taxonomy assignment.

These are precision-sanity checks on hand-labeled synthetic cases with
strong, unambiguous signals — not a claim about real-world accuracy.
"""

from failure_forensics import FailureCase, assign_failures
from failure_forensics.taxonomy import (
    UNCERTAIN_THRESHOLD,
    collect_evidence,
)


def test_hand_labeled_precision(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    expected = [label for _, label in labeled_cases]
    assignments = assign_failures(cases)
    predicted = [a.category for a in assignments]
    correct = sum(p == e for p, e in zip(predicted, expected))
    accuracy = correct / len(expected)
    assert accuracy >= 0.8, (
        f"precision sanity failed: {correct}/{len(expected)}; "
        + str(list(zip([c.id for c in cases], predicted, expected)))
    )


def test_clear_cases_get_high_confidence(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    for assignment in assign_failures(cases):
        assert 0.0 <= assignment.confidence <= 1.0
        assert assignment.confidence >= 0.5, (
            f"{assignment.case_id} -> {assignment.category} "
            f"confidence {assignment.confidence:.3f} too low for a clear case"
        )
        assert not assignment.uncertain


def test_clear_cases_carry_evidence_spans(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    for assignment in assign_failures(cases):
        assert assignment.evidence, f"{assignment.case_id} has no evidence"
        for item in assignment.evidence:
            assert item.span.strip(), "evidence span must be non-empty"
            assert item.category == assignment.category


def test_ambiguous_case_flagged_uncertain():
    case = FailureCase(
        id="t-amb",
        prompt="What is the best approach here?",
        model_output=(
            "The answer might be 42 but I'm not fully sure; "
            "the context suggests otherwise."
        ),
        expected="It depends on the constraints.",
        task_type="qa",
    )
    (assignment,) = assign_failures([case])
    assert assignment.uncertain
    assert assignment.confidence < UNCERTAIN_THRESHOLD


def test_assignment_is_deterministic(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    first = [(a.category, round(a.confidence, 6)) for a in assign_failures(cases)]
    second = [(a.category, round(a.confidence, 6)) for a in assign_failures(cases)]
    assert first == second


def test_evidence_detectors_fire(refusal_case, format_case):
    refusal_evidence = collect_evidence(refusal_case)
    assert any(e.category == "refusal" for e in refusal_evidence)
    format_evidence = collect_evidence(format_case)
    assert any(e.category == "format-error" for e in format_evidence)


def test_assignment_mapping_round_trip(labeled_cases):
    (assignment,) = assign_failures([labeled_cases[0][0]])
    mapping = assignment.to_mapping()
    assert mapping["case_id"] == "t-refusal"
    assert mapping["category"] == "refusal"
    assert isinstance(mapping["evidence"], list)
