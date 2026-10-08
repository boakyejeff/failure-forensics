"""Tests for Markdown report rendering."""

from failure_forensics import assign_failures
from failure_forensics.report import render_markdown


def test_report_contains_core_sections(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    text = render_markdown(cases, assignments)
    assert text.startswith("# LLM Failure Forensics Report")
    assert "## Summary" in text
    assert "## Bucket distribution" in text
    assert "## Bucket deep dives" in text
    assert "| Bucket | Count | Share |" in text


def test_report_marks_hypotheses_as_heuristic(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    text = render_markdown(cases, assignments)
    assert "heuristic" in text.lower()
    assert "Hypothesized root cause" in text
    assert "Suggested fix" in text


def test_report_shows_examples_with_evidence(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    text = render_markdown(cases, assignments, examples_per_bucket=2)
    assert "t-refusal" in text
    assert "Evidence [" in text
    assert "confidence" in text


def test_report_task_type_table(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    text = render_markdown(cases, assignments)
    assert "## Failures by task type" in text
    assert "math" in text


def test_report_custom_title(labeled_cases):
    cases = [case for case, _ in labeled_cases]
    assignments = assign_failures(cases)
    text = render_markdown(cases, assignments, title="Custom Title")
    assert text.startswith("# Custom Title")
