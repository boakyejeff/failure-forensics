"""Ingestion of LLM evaluation failure cases from JSON, JSONL, and CSV files.

A failure case is a single model response that did not meet expectations:
the prompt that was given, what the model produced, and what was expected.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Union

_KNOWN_FIELDS = {"id", "prompt", "model_output", "expected", "task_type", "metadata"}


@dataclass
class FailureCase:
    """One failed model response from an evaluation run."""

    id: str
    prompt: str
    model_output: str
    expected: str = ""
    task_type: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "FailureCase":
        """Build a case from a dict-like record; unknown keys go to metadata."""
        data = dict(mapping)
        metadata: Dict[str, Any] = {}
        raw_meta = data.get("metadata")
        if isinstance(raw_meta, Mapping):
            metadata.update(raw_meta)
        elif isinstance(raw_meta, str) and raw_meta.strip():
            try:
                parsed = json.loads(raw_meta)
                if isinstance(parsed, Mapping):
                    metadata.update(parsed)
            except json.JSONDecodeError:
                metadata["metadata_raw"] = raw_meta
        for key, value in data.items():
            if key not in _KNOWN_FIELDS and key not in metadata:
                metadata[key] = value
        return cls(
            id=str(data.get("id", "")),
            prompt=str(data.get("prompt", "")),
            model_output=str(data.get("model_output", "")),
            expected=str(data.get("expected", "")),
            task_type=str(data.get("task_type", "general") or "general"),
            metadata=metadata,
        )

    def to_mapping(self) -> Dict[str, Any]:
        """Serialize back to a plain dict (round-trips through from_mapping)."""
        return {
            "id": self.id,
            "prompt": self.prompt,
            "model_output": self.model_output,
            "expected": self.expected,
            "task_type": self.task_type,
            "metadata": dict(self.metadata),
        }


def _records_from_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(record, Mapping):
                raise ValueError(f"{path}:{lineno}: expected a JSON object per line")
            yield record


def _records_from_json(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, Mapping):
        # tolerate {"failures": [...]} style wrappers
        for key in ("failures", "cases", "items", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError(f"{path}: expected a JSON array of failure records")
    for record in payload:
        if not isinstance(record, Mapping):
            raise ValueError(f"{path}: every record must be a JSON object")
        yield record


def _records_from_csv(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV has no header row")
        for row in reader:
            yield {k: (v or "") for k, v in row.items() if k}


def load_failures(path: Union[str, Path]) -> List[FailureCase]:
    """Load failure cases from a .json, .jsonl, or .csv file.

    Raises FileNotFoundError if the path does not exist and ValueError for
    unsupported extensions or malformed records.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no such file: {path}")
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        records = _records_from_jsonl(path)
    elif suffix == ".json":
        records = _records_from_json(path)
    elif suffix == ".csv":
        records = _records_from_csv(path)
    else:
        raise ValueError(
            f"unsupported file type '{suffix}'; use .json, .jsonl, or .csv"
        )
    return [FailureCase.from_mapping(record) for record in records]
