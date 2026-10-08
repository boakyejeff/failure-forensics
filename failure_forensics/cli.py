"""Command-line interface for the failure forensics tool.

Usage:
    python -m failure_forensics.cli analyze failures.jsonl --out report.md
    ./forensics analyze failures.jsonl --out report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ingest import load_failures
from .taxonomy import assign_failures, UNCERTAIN_THRESHOLD
from .report import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forensics",
        description="Cluster LLM evaluation failures into a failure taxonomy "
                    "and render a forensics report.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser(
        "analyze",
        help="Assign failure cases to taxonomy buckets and write a report.",
    )
    analyze.add_argument("input", help="Failures file (.json, .jsonl, or .csv)")
    analyze.add_argument(
        "--out",
        default="forensics-report.md",
        help="Where to write the Markdown report (default: forensics-report.md)",
    )
    analyze.add_argument(
        "--title",
        default="LLM Failure Forensics Report",
        help="Report title",
    )
    analyze.add_argument(
        "--min-confidence",
        type=float,
        default=UNCERTAIN_THRESHOLD,
        help="Confidence below which assignments are flagged uncertain "
             f"(default: {UNCERTAIN_THRESHOLD})",
    )
    analyze.add_argument(
        "--examples",
        type=int,
        default=3,
        help="Example cases shown per bucket (default: 3)",
    )
    return parser


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        cases = load_failures(args.input)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not cases:
        print(f"error: no failure cases found in {args.input}", file=sys.stderr)
        return 2

    assignments = assign_failures(cases)
    for assignment in assignments:
        assignment.uncertain = assignment.confidence < args.min_confidence

    markdown = render_markdown(
        cases, assignments, title=args.title, examples_per_bucket=args.examples
    )
    out_path = Path(args.out)
    out_path.write_text(markdown, encoding="utf-8")

    uncertain = sum(1 for a in assignments if a.uncertain)
    print(f"analyzed {len(cases)} cases -> {out_path}")
    print(f"low-confidence assignments: {uncertain}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "analyze":
        return cmd_analyze(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
