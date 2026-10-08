# Failure Forensics

Turn raw LLM evaluation failures into a structured failure taxonomy: cluster the
failures, label the clusters, and produce a forensics report with example cases,
hypothesized root causes, and suggested fixes.

## Why

When an LLM eval shows a 78% pass rate, the interesting question is what lives in
the other 22%. Failure Forensics ingests failed eval cases, assigns each one to a
failure bucket (hallucination, instruction violation, reasoning error, and more),
and renders a Markdown report your team can actually act on: how failures
distribute across buckets, concrete examples with the evidence that triggered
each label, and a first hypothesis plus suggested fix per bucket.

## Install

Requires Python 3.9+. No network access needed at any point; the only
dependency is `pytest` for running the test suite.

```bash
cd failure-forensics
pip install -r requirements.txt
```

## Quickstart

```bash
# 1. Generate the deterministic synthetic demo data and report
python examples/demo.py

# 2. Analyze your own failures file (JSON, JSONL, or CSV)
./forensics analyze examples/sample_failures.jsonl --out report.md
# or equivalently:
python -m failure_forensics.cli analyze examples/sample_failures.jsonl --out report.md
```

Expected input record shape (extra keys are kept as metadata):

```json
{"id": "case-001", "prompt": "...", "model_output": "...",
 "expected": "...", "task_type": "math",
 "metadata": {"model": "my-model-v2", "batch": "run-3"}}
```

## How assignment works

1. **Rule-based evidence detectors** scan each case: refusal phrases, JSON/format
   checks against the prompt's stated format, yes/no-only and exact-count
   instruction checks, novel named entities absent from the prompt and expected
   answer (hallucination signal), shown-work-but-wrong-answer on math/reasoning
   tasks, expected terms present in a provided context but missing from the
   output, and multi-part prompts with single-part answers. Every fired rule
   records the exact text span that triggered it.
2. **Local text similarity**: each case is compared (TF-IDF cosine, computed
   locally and deterministically over the input corpus) against a short seed
   description per taxonomy bucket. No network, no pretrained embeddings.
3. Evidence weight and similarity combine into a per-bucket score; the winner
   takes the assignment and confidence is its softmax share. Cases below the
   confidence threshold are flagged **uncertain** instead of being forced into
   a bucket.

## Taxonomy design rationale

The seven starter buckets were chosen because they are (a) the failure modes
that show up most often in LLM eval postmortems, (b) distinguishable by
transparent, auditable rules, and (c) each maps to a different remediation
(fix the prompt, fix the decoding, add tools, tune safety, ...). The taxonomy
is intentionally small and rule-first: a forensics tool should explain *why*
it labeled something, and a 200-label learned taxonomy cannot do that without
a human in the loop. Extend it by adding a `TaxonomyCategory` plus a detector
in `failure_forensics/taxonomy.py`.

## Project layout

```
failure-forensics/
  failure_forensics/
    ingest.py     # FailureCase dataclass; JSON/JSONL/CSV loaders
    taxonomy.py   # starter taxonomy, heuristic detectors, TF-IDF assignment
    analyze.py    # distributions, metadata breakdowns, trends, low-confidence
    report.py     # Markdown forensics report renderer
    cli.py        # `forensics analyze` command-line interface
  examples/
    demo.py                 # deterministic synthetic data + report generator
    sample_failures.jsonl   # generated demo data (22 scripted cases)
    report.md               # generated demo report
  tests/          # pytest suite (ingest, taxonomy, analyze, report, CLI)
```

## Limitations (read this before trusting the output)

- **Heuristics are a starting point, not a substitute for human review.**
  Every label is produced by transparent rules plus local text similarity.
  Sample each bucket, read the raw cases, and let human judgment decide.
- **Root causes are hypotheses, not diagnoses.** The report labels them as
  such; treat them as investigation leads.
- **No semantic understanding.** The tool has no model of meaning beyond
  keyword/regex rules and TF-IDF overlap; subtle or novel failure modes will
  be mislabeled or land in the uncertain pile. That is by design: uncertain
  cases are the ones most worth a human's time.
- **Tune the detectors to your domain.** The built-in rules encode generic
  eval-failure patterns; production use means adding your own categories and
  detectors in `taxonomy.py`.
- Fully offline: the tool makes zero network calls and has no heavy
  dependencies.

## License

MIT — see [LICENSE](LICENSE). Author: Jeffrey B. Appiagyei.
