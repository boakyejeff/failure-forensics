"""Demo: generate a deterministic synthetic failures file and a forensics report.

Everything is scripted and fully offline  -  no network, no model downloads.
The generator uses a fixed seed, so the same file and report are produced
on every run.

Usage:
    python examples/demo.py
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from failure_forensics import FailureCase, assign_failures  # noqa: E402
from failure_forensics.report import render_markdown  # noqa: E402

SEED = 20261008

# (bucket, prompt, model_output, expected, task_type)
TEMPLATES = [
    # -- hallucination: invented entities absent from prompt/expected --
    ("hallucination",
     "Who wrote the novel 'The Silent Tide'?",
     "The Silent Tide was written by Elena Vasquez in 1987 and won the 1989 Harlow Prize for debut fiction.",
     "No record of such a novel exists.",
     "qa"),
    ("hallucination",
     "Summarize the 2023 Meridian Health annual report.",
     "Meridian Health reported revenue of $4.2 billion in 2023, led by CEO Jonathan Pryce, and opened 14 new clinics in Ohio.",
     "I don't have access to that report.",
     "summarization"),
    ("hallucination",
     "What did Dr. Alvarez conclude in her 2021 paper on coral bleaching?",
     "Dr. Alvarez concluded that thermal stress declined 30% between 2019 and 2021, reversing the trend (Alvarez et al., 2021).",
     "Unknown; no such paper was provided.",
     "qa"),
    # -- instruction-violation: explicit yes/no or exact-count instruction ignored --
    ("instruction-violation",
     "Answer with only 'yes' or 'no'. Is Paris the capital of France?",
     "Yes, Paris is the capital of France and has been since the medieval period.",
     "yes",
     "qa"),
    ("instruction-violation",
     "Answer with only 'yes' or 'no': does water boil at 100C at sea level?",
     "Yes. At standard atmospheric pressure, pure water boils at 100 degrees Celsius.",
     "yes",
     "qa"),
    ("instruction-violation",
     "List exactly 3 colors. Do not explain.",
     "Red, blue, green, and also yellow which is a warm color often used in design because it stands out.",
     "red, blue, green",
     "generation"),
    # -- reasoning-error: shows work, wrong final answer --
    ("reasoning-error",
     "What is 17 * 24? Show your work.",
     "17 * 24 = 17*20 + 17*4 = 340 + 68 = 418. So the answer is 418.",
     "408",
     "math"),
    ("reasoning-error",
     "A train travels 60 km/h for 2.5 hours. How far does it go? Show your work.",
     "Distance = speed x time = 60 x 2.5 = 120 + 30 = 140. So, 140 km.",
     "150 km",
     "math"),
    ("reasoning-error",
     "If all bloops are razzies and some razzies are lazzies, are all bloops lazzies? Explain step by step.",
     "Step 1: all bloops are razzies. Step 2: some razzies are lazzies. Step 3: therefore all bloops are lazzies. Answer: yes.",
     "No  -  the premises only support 'some bloops may be lazzies'.",
     "logic"),
    # -- format-error: asked for JSON, got prose --
    ("format-error",
     "Respond in JSON format with keys 'name' and 'age'.",
     "name: Ada, age: 36",
     '{"name": "Ada", "age": 36}',
     "extraction"),
    ("format-error",
     "Return the answer in JSON format: {\"city\": ..., \"country\": ...}.",
     "The city is Lima and the country is Peru.",
     '{"city": "Lima", "country": "Peru"}',
     "extraction"),
    ("format-error",
     "Give the result as a bullet list.",
     "First we add the flour, then we add the sugar and mix everything together.",
     "- flour\n- sugar\n- mix",
     "generation"),
    # -- context-misuse: context given, model answers from priors instead --
    ("context-misuse",
     "Context: The Eiffel Tower is in Paris and was completed in 1889.\nQuestion: Where is the Eiffel Tower and when was it completed?",
     "It is in London and was completed in 1901.",
     "Paris, 1889",
     "reading-comprehension"),
    ("context-misuse",
     "Context: Photosynthesis occurs in chloroplasts, which contain chlorophyll.\nQuestion: Where does photosynthesis occur?",
     "Photosynthesis occurs in the mitochondria, the powerhouse of the cell.",
     "In chloroplasts",
     "reading-comprehension"),
    # -- refusal: benign prompt refused --
    ("refusal",
     "Explain how photosynthesis works for a 10-year-old.",
     "I'm sorry, but I can't help with that.",
     "Photosynthesis is how plants make food from sunlight...",
     "explanation"),
    ("refusal",
     "Write a haiku about the ocean.",
     "I cannot help with that request.",
     "Waves fold to shore / salt on the evening wind / the moon pulls them home",
     "generation"),
    ("refusal",
     "What is the capital of Japan?",
     "As an AI, I'm unable to answer that.",
     "Tokyo",
     "qa"),
    # -- partial-answer: multi-part prompt, single-part answer --
    ("partial-answer",
     "Name the capital of France. What is 2+2? Who wrote Hamlet?",
     "Paris.",
     "Paris. 4. Shakespeare.",
     "qa"),
    ("partial-answer",
     "Summarize the plot of Dune in two sentences. Also list the main characters. Also state the author's name.",
     "Dune is about a desert planet called Arrakis where",
     "Dune follows Paul Atreides on Arrakis. Main characters: Paul, Jessica, Duncan. Author: Frank Herbert.",
     "summarization"),
    # -- ambiguous: weak signals, should come back low-confidence --
    ("ambiguous",
     "What is the best approach here?",
     "The answer might be 42 but I'm not fully sure; the context suggests otherwise.",
     "It depends on the constraints.",
     "qa"),
    ("ambiguous",
     "Describe the process.",
     "Well, there are several aspects worth considering in some detail.",
     "A clear step-by-step description.",
     "explanation"),
]

LABELS = [t[0] for t in TEMPLATES]


def build_cases(seed: int = SEED) -> list[FailureCase]:
    rng = random.Random(seed)
    order = list(range(len(TEMPLATES)))
    rng.shuffle(order)
    cases = []
    for n, idx in enumerate(order, start=1):
        bucket, prompt, output, expected, task_type = TEMPLATES[idx]
        cases.append(FailureCase(
            id=f"syn-{n:03d}",
            prompt=prompt,
            model_output=output,
            expected=expected,
            task_type=task_type,
            metadata={"synthetic": True, "intended_bucket": bucket, "batch": "demo"},
        ))
    return cases


def main() -> int:
    examples_dir = Path(__file__).resolve().parent
    cases = build_cases()

    jsonl_path = examples_dir / "sample_failures.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case.to_mapping(), ensure_ascii=False) + "\n")
    print(f"wrote {len(cases)} synthetic cases -> {jsonl_path}")

    assignments = assign_failures(cases)
    report = render_markdown(cases, assignments,
                             title="Failure Forensics  -  Synthetic Demo Report")
    report_path = examples_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"wrote forensics report -> {report_path}")

    correct = sum(
        1 for case, a in zip(cases, assignments)
        if a.category == case.metadata["intended_bucket"]
    )
    print(f"heuristic agreement with intended labels: {correct}/{len(cases)}")
    print("NOTE: intended labels are generator intent, not ground truth  -  "
          "the tool's labels remain heuristic suggestions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
