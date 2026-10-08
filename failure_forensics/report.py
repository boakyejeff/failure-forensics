"""Markdown forensics report rendering.

The report is explicit about epistemics: taxonomy labels come from heuristics,
and root causes are *hypotheses* to investigate, not verified ground truth.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from .ingest import FailureCase
from .taxonomy import Assignment, CATEGORIES, category
from .analyze import (
    bucket_distribution,
    distribution_rows,
    breakdown_by,
    low_confidence_cases,
)


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _truncate(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_markdown(
    cases: Sequence[FailureCase],
    assignments: Sequence[Assignment],
    title: str = "LLM Failure Forensics Report",
    examples_per_bucket: int = 3,
) -> str:
    """Render a complete forensics report as Markdown text."""
    by_id: Dict[str, FailureCase] = {case.id: case for case in cases}
    total = len(assignments)
    rows = distribution_rows(assignments)
    uncertain = low_confidence_cases(assignments)

    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(
        "> Method note: bucket labels are assigned by transparent, rule-based "
        "heuristics plus local text similarity  -  they are a starting point for "
        "human review, not ground truth. Root causes below are heuristic "
        "hypotheses to investigate, not verified diagnoses."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Failure cases analyzed: **{total}**")
    lines.append(f"- Taxonomy buckets hit: **{len(rows)}** of {len(CATEGORIES)}")
    lines.append(
        f"- Low-confidence assignments (worth human review): **{len(uncertain)}**"
    )
    lines.append("")

    lines.append("## Bucket distribution")
    lines.append("")
    lines.append("| Bucket | Count | Share |")
    lines.append("| --- | ---: | ---: |")
    for row in rows:
        share = float(row["share"])
        lines.append(
            f"| {_escape_cell(str(row['bucket']))} | {row['count']} "
            f"| {share:.1%} |"
        )
    lines.append("")

    meta_breakdown = breakdown_by(cases, assignments, "task_type")
    if len(meta_breakdown) > 1:
        lines.append("## Failures by task type")
        lines.append("")
        lines.append("| Task type | " + " | ".join(
            _escape_cell(r["bucket"]) for r in rows  # type: ignore[misc]
        ) + " |")
        lines.append("| --- | " + " | ".join("---:" for _ in rows) + " |")
        for group in sorted(meta_breakdown):
            buckets = meta_breakdown[group]
            cells = [str(buckets.get(str(r["bucket"]), 0)) for r in rows]
            lines.append(f"| {_escape_cell(group)} | " + " | ".join(cells) + " |")
        lines.append("")

    lines.append("## Bucket deep dives")
    lines.append("")
    for row in rows:
        bucket = str(row["bucket"])
        cat = category(bucket)
        share = float(row["share"])
        lines.append(f"### {bucket}  -  {row['count']} cases ({share:.0%})")
        lines.append("")
        lines.append(f"_{_escape_cell(cat.description)}_")
        lines.append("")
        lines.append(
            "**Hypothesized root cause** *(heuristic hypothesis, not verified)*: "
            f"{cat.root_cause_hypothesis}"
        )
        lines.append("")
        lines.append(f"**Suggested fix**: {cat.suggested_fix}")
        lines.append("")
        bucket_assignments = sorted(
            (a for a in assignments if a.category == bucket),
            key=lambda a: -a.confidence,
        )[:examples_per_bucket]
        lines.append("**Example cases:**")
        lines.append("")
        for assignment in bucket_assignments:
            case = by_id.get(assignment.case_id)
            if case is None:
                continue
            lines.append(
                f"- `{_escape_cell(assignment.case_id)}` "
                f"(confidence {assignment.confidence:.2f}"
                f"{', UNCERTAIN' if assignment.uncertain else ''})"
            )
            lines.append(f"  - Prompt: {_escape_cell(_truncate(case.prompt))}")
            lines.append(
                f"  - Model output: {_escape_cell(_truncate(case.model_output))}"
            )
            if case.expected:
                lines.append(
                    f"  - Expected: {_escape_cell(_truncate(case.expected))}"
                )
            for item in assignment.evidence:
                lines.append(
                    f"  - Evidence [{_escape_cell(item.rule)}]: "
                    f"\"{_escape_cell(_truncate(item.span, 140))}\""
                )
        lines.append("")

    if uncertain:
        lines.append("## Needs human review (low confidence)")
        lines.append("")
        for assignment in sorted(uncertain, key=lambda a: a.confidence)[:10]:
            case = by_id.get(assignment.case_id)
            prompt = _truncate(case.prompt, 100) if case else ""
            lines.append(
                f"- `{_escape_cell(assignment.case_id)}` -> "
                f"{_escape_cell(assignment.category)} "
                f"({assignment.confidence:.2f}): {_escape_cell(prompt)}"
            )
        lines.append("")

    lines.append("---")
    lines.append(
        "Generated by the failure-forensics tool. Treat every label as a "
        "heuristic suggestion: sample the buckets, read the raw cases, and let "
        "human judgment decide."
    )
    lines.append("")
    return "\n".join(lines)
