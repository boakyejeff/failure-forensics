"""Tests for ingestion from JSON, JSONL, and CSV."""

import csv
import json

import pytest

from failure_forensics import FailureCase, load_failures


def _sample() -> dict:
    return {
        "id": "c1",
        "prompt": "What is 2+2?",
        "model_output": "5",
        "expected": "4",
        "task_type": "math",
        "metadata": {"model": "demo-1"},
    }


def test_load_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(_sample()) + "\n" + json.dumps(_sample()) + "\n")
    cases = load_failures(path)
    assert len(cases) == 2
    assert cases[0].id == "c1"
    assert cases[0].metadata["model"] == "demo-1"


def test_load_json_array(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_sample(), _sample()]))
    cases = load_failures(path)
    assert len(cases) == 2
    assert cases[1].task_type == "math"


def test_load_json_wrapped(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"failures": [_sample()]}))
    assert len(load_failures(path)) == 1


def test_load_csv(tmp_path):
    path = tmp_path / "cases.csv"
    sample = _sample()
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sample.keys()))
        writer.writeheader()
        writer.writerow({k: (json.dumps(v) if k == "metadata" else v)
                         for k, v in sample.items()})
    cases = load_failures(path)
    assert len(cases) == 1
    assert cases[0].model_output == "5"
    assert cases[0].metadata["model"] == "demo-1"


def test_csv_extra_columns_become_metadata(tmp_path):
    path = tmp_path / "cases.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "prompt", "model_output",
                                                "custom_field"])
        writer.writeheader()
        writer.writerow({"id": "c9", "prompt": "p", "model_output": "o",
                         "custom_field": "kept"})
    cases = load_failures(path)
    assert cases[0].metadata["custom_field"] == "kept"
    assert cases[0].expected == ""  # defaults applied


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_failures(tmp_path / "nope.jsonl")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "cases.txt"
    path.write_text("hello")
    with pytest.raises(ValueError, match="unsupported"):
        load_failures(path)


def test_malformed_jsonl_raises(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text("{not valid json}\n")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_failures(path)


def test_from_mapping_round_trip():
    case = FailureCase.from_mapping(_sample())
    again = FailureCase.from_mapping(case.to_mapping())
    assert again == case
