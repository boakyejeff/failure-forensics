"""End-to-end CLI tests: analyze a failures file, get a report file."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write_jsonl(path: Path) -> None:
    records = [
        {
            "id": "cli-1",
            "prompt": "Explain how photosynthesis works for a 10-year-old.",
            "model_output": "I'm sorry, but I can't help with that.",
            "expected": "Photosynthesis is how plants make food from sunlight.",
            "task_type": "explanation",
        },
        {
            "id": "cli-2",
            "prompt": "What is 17 * 24? Show your work.",
            "model_output": "17 * 24 = 340 + 68 = 418. So the answer is 418.",
            "expected": "408",
            "task_type": "math",
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def test_cli_analyze_end_to_end(tmp_path):
    input_path = tmp_path / "failures.jsonl"
    out_path = tmp_path / "report.md"
    _write_jsonl(input_path)
    result = subprocess.run(
        [sys.executable, "-m", "failure_forensics.cli", "analyze",
         str(input_path), "--out", str(out_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    text = out_path.read_text()
    assert "refusal" in text
    assert "reasoning-error" in text
    assert "cli-1" in text


def test_cli_missing_input_errors(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "failure_forensics.cli", "analyze",
         str(tmp_path / "missing.jsonl")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "error" in result.stderr.lower()
