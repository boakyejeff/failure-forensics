"""Failure forensics: turn LLM evaluation failures into a structured failure taxonomy."""

from .ingest import FailureCase, load_failures
from .taxonomy import Assignment, TaxonomyCategory, assign_failures
from .analyze import (
    bucket_distribution,
    distribution_rows,
    breakdown_by,
    low_confidence_cases,
    trend_by_group,
)
from .report import render_markdown

__all__ = [
    "FailureCase",
    "load_failures",
    "Assignment",
    "TaxonomyCategory",
    "assign_failures",
    "bucket_distribution",
    "distribution_rows",
    "breakdown_by",
    "low_confidence_cases",
    "trend_by_group",
    "render_markdown",
]

__version__ = "0.1.0"
