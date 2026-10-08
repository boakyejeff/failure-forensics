"""Failure taxonomy: rule-based heuristics plus deterministic text-feature assignment.

How assignment works
--------------------
1. Every failure case is scanned by a set of small, transparent rule-based
   detectors (one family per taxonomy bucket). Each detector returns *evidence*:
   the rule that fired and the exact text span that triggered it.
2. Independently, the case text is compared (TF-IDF cosine similarity) against
   a short seed description for each taxonomy bucket. This is computed locally
   and deterministically; no network, no pretrained models.
3. The final score per bucket combines capped evidence weight with the
   similarity score. The winning bucket is the assignment; confidence is the
   softmax share of the winner. Cases below ``UNCERTAIN_THRESHOLD`` are flagged
   as uncertain rather than forced into a bucket.

All labels are heuristic. They are a starting point for human review, never
ground truth.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .ingest import FailureCase

UNCERTAIN_THRESHOLD = 0.45
EVIDENCE_WEIGHT = 3.0
SIMILARITY_WEIGHT = 1.0
PRIOR = 0.05


@dataclass
class TaxonomyCategory:
    """One bucket of the starter failure taxonomy."""

    name: str
    description: str
    seed_terms: List[str]
    root_cause_hypothesis: str
    suggested_fix: str

    def seed_text(self) -> str:
        return " ".join([self.name.replace("-", " "), self.description] + self.seed_terms)


@dataclass
class Evidence:
    """One fired heuristic: which rule, the matched span, and its weight."""

    category: str
    span: str
    rule: str
    weight: float = 1.0


@dataclass
class Assignment:
    """The taxonomy assignment for one failure case."""

    case_id: str
    category: str
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
    uncertain: bool = False

    def to_mapping(self) -> Dict:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "uncertain": self.uncertain,
            "evidence": [
                {"category": e.category, "span": e.span, "rule": e.rule,
                 "weight": e.weight}
                for e in self.evidence
            ],
        }


CATEGORIES: List[TaxonomyCategory] = [
    TaxonomyCategory(
        name="hallucination",
        description=(
            "The model invents facts, entities, dates, or citations that are not "
            "supported by the prompt, the provided context, or the expected answer."
        ),
        seed_terms=["fabricated", "invented", "made up", "false fact", "fake citation",
                    "unsubstantiated claim", "confabulation"],
        root_cause_hypothesis=(
            "The model may be filling gaps with parametric memory instead of "
            "grounding in the given context, with decoding favoring fluency over "
            "factuality."
        ),
        suggested_fix=(
            "Add grounding checks: verify named entities and numbers against the "
            "source context; consider retrieval augmentation or constrained "
            "decoding; lower the temperature for factual tasks."
        ),
    ),
    TaxonomyCategory(
        name="instruction-violation",
        description=(
            "The model ignores or disobeys an explicit instruction in the prompt, "
            "such as answering only yes/no, listing exactly N items, or not "
            "explaining."
        ),
        seed_terms=["ignored instruction", "disobeyed", "did not follow",
                    "violated constraint", "wrong output shape"],
        root_cause_hypothesis=(
            "Instruction-following may be weaker than content generation; the "
            "critical instruction may be buried, ambiguous, or stated only once."
        ),
        suggested_fix=(
            "Move critical instructions to the start and the end of the prompt, "
            "use explicit delimiters, and add an output-shape verification step "
            "before accepting the response."
        ),
    ),
    TaxonomyCategory(
        name="reasoning-error",
        description=(
            "The model shows its work but arrives at the wrong conclusion: "
            "arithmetic slips, faulty logic steps, or a wrong final answer on a "
            "reasoning task."
        ),
        seed_terms=["wrong calculation", "arithmetic mistake", "faulty logic",
                    "wrong final answer", "multi-step error", "slip"],
        root_cause_hypothesis=(
            "Multi-step computation may exceed the model's reliable working "
            "memory; small errors compound across steps without verification."
        ),
        suggested_fix=(
            "Prompt for step-by-step work with intermediate verification, use "
            "tools or calculators for arithmetic, and add a self-check pass over "
            "the final answer."
        ),
    ),
    TaxonomyCategory(
        name="format-error",
        description=(
            "The response content may be right but the required format is wrong: "
            "invalid JSON, missing bullet list, missing table, wrong schema."
        ),
        seed_terms=["invalid json", "wrong format", "schema violation",
                    "missing bullets", "malformed output"],
        root_cause_hypothesis=(
            "Format constraints may be treated as soft preferences rather than "
            "hard constraints; structured-output decoding is not enforced."
        ),
        suggested_fix=(
            "Use structured-output APIs or JSON-schema validation with retry; "
            "include a concrete format example in the prompt."
        ),
    ),
    TaxonomyCategory(
        name="context-misuse",
        description=(
            "The prompt supplies a context or passage and the model fails to use "
            "it: answering from prior knowledge instead, or contradicting the "
            "given context."
        ),
        seed_terms=["ignored context", "did not read passage", "contradicted context",
                    "prior knowledge override", "context not used"],
        root_cause_hypothesis=(
            "Long context may dilute attention; the model may fall back on "
            "parametric priors instead of the provided passage."
        ),
        suggested_fix=(
            "Shorten and highlight the relevant context span; ask the model to "
            "quote the supporting passage before answering."
        ),
    ),
    TaxonomyCategory(
        name="refusal",
        description=(
            "The model refuses to answer a benign prompt: apologies, claims of "
            "inability, or safety-style deflection."
        ),
        seed_terms=["refused", "declined to answer", "sorry", "cannot help",
                    "over-refusal", "false refusal"],
        root_cause_hypothesis=(
            "Safety tuning may be over-triggered on benign prompts; the refusal "
            "classifier may be miscalibrated for this task type."
        ),
        suggested_fix=(
            "Review refusal triggers on a calibration set; clarify benign intent "
            "in the prompt; tune safety thresholds per task type."
        ),
    ),
    TaxonomyCategory(
        name="partial-answer",
        description=(
            "The model answers only part of the request: a multi-part question "
            "gets a single-part answer, the response trails off, or the output "
            "is far shorter than the expected answer."
        ),
        seed_terms=["incomplete", "trailed off", "only answered part",
                    "missing sub-answers", "truncated"],
        root_cause_hypothesis=(
            "The model may satisfice on the first sub-question; multi-part "
            "prompts may exceed its effective planning horizon."
        ),
        suggested_fix=(
            "Number the sub-questions explicitly, require a labeled answer per "
            "part, and add a completeness checklist to the prompt."
        ),
    ),
]

_CATEGORY_BY_NAME: Dict[str, TaxonomyCategory] = {c.name: c for c in CATEGORIES}

# ---------------------------------------------------------------------------
# Evidence detectors (rule-based heuristics)
# ---------------------------------------------------------------------------

_REFUSAL_PATTERNS = [
    r"\bi'?m sorry\b",
    r"\bi can'?t\b",
    r"\bi cannot\b",
    r"\bi'?m unable to\b",
    r"\bnot able to\b",
    r"\bcan'?t help\b",
    r"\bas an ai\b",
]

_CONTEXT_MARKERS = ("context:", "passage:", "document:", "article:")


def _span(text: str, start: int, end: int, window: int = 40) -> str:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    snippet = text[lo:hi].replace("\n", " ").strip()
    return snippet


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _detect_refusal(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    for pattern in _REFUSAL_PATTERNS:
        for match in re.finditer(pattern, case.model_output, flags=re.IGNORECASE):
            out.append(Evidence(
                category="refusal",
                span=_span(case.model_output, match.start(), match.end()),
                rule=f"refusal-phrase:{pattern}",
                weight=1.5,
            ))
    return out


def _detect_format_error(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    prompt = case.prompt.lower()
    output = case.model_output.strip()
    if "json" in prompt and ("format" in prompt or "respond in" in prompt):
        try:
            json.loads(output)
        except (json.JSONDecodeError, ValueError):
            out.append(Evidence(
                category="format-error",
                span=_span(output, 0, min(60, len(output))),
                rule="prompt-asks-json-output-not-valid-json",
                weight=1.5,
            ))
    if "bullet" in prompt and "list" in prompt:
        if not re.search(r"(?m)^\s*[-*•]", output):
            out.append(Evidence(
                category="format-error",
                span=_span(output, 0, min(60, len(output))),
                rule="prompt-asks-bullet-list-no-bullets-found",
                weight=1.0,
            ))
    if "table" in prompt and ("markdown" in prompt or "as a table" in prompt):
        if "|" not in output:
            out.append(Evidence(
                category="format-error",
                span=_span(output, 0, min(60, len(output))),
                rule="prompt-asks-table-no-table-found",
                weight=1.0,
            ))
    return out


def _detect_instruction_violation(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    prompt = case.prompt.lower()
    output = case.model_output.strip()
    if re.search(r"answer (with )?only ['\"]?(yes|no)['\"]? or ['\"]?(no|yes)['\"]?", prompt) or \
       re.search(r"\byes or no\b", prompt):
        if _norm(output) not in {"yes", "no", "y", "n"}:
            out.append(Evidence(
                category="instruction-violation",
                span=_span(output, 0, min(80, len(output))),
                rule="prompt-requires-yes-no-only-output-is-longer",
                weight=1.5,
            ))
    match = re.search(r"list exactly (\d+)", prompt)
    if match:
        wanted = int(match.group(1))
        items = re.findall(r"(?m)^\s*[-*•\d.)]", output)
        if len(items) != wanted:
            out.append(Evidence(
                category="instruction-violation",
                span=f"asked for {wanted} items, found {len(items)} list markers",
                rule="prompt-requires-exact-item-count",
                weight=1.0,
            ))
    if re.search(r"do not explain|no explanation|without explanation", prompt):
        words = len(output.split())
        if words > 30 or re.search(r"\bbecause\b|\bsince\b", output, re.IGNORECASE):
            out.append(Evidence(
                category="instruction-violation",
                span=_span(output, 0, min(80, len(output))),
                rule="prompt-forbids-explanation-output-explains",
                weight=1.0,
            ))
    return out


_ENTITY_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")


def _novel_entities(output: str, reference: str) -> List[str]:
    ref_lower = reference.lower()
    novel: List[str] = []
    for token in _ENTITY_RE.findall(output):
        if token.lower() not in ref_lower and token not in novel:
            novel.append(token)
    return novel


def _detect_hallucination(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    reference = f"{case.prompt}\n{case.expected}"
    novel = _novel_entities(case.model_output, reference)
    if len(novel) >= 2 and len(case.model_output) > 40:
        out.append(Evidence(
            category="hallucination",
            span="novel entities not in prompt/expected: " + ", ".join(novel[:6]),
            rule="entities-in-output-absent-from-prompt-and-expected",
            weight=1.0,
        ))
    for pattern in (r"\bet al\.?\b", r"\bdoi:\s*\S+", r"\(\d{4}\)"):
        for match in re.finditer(pattern, case.model_output, flags=re.IGNORECASE):
            snippet = match.group(0)
            if snippet.lower() not in reference.lower():
                out.append(Evidence(
                    category="hallucination",
                    span=_span(case.model_output, match.start(), match.end()),
                    rule="citation-like-pattern-absent-from-prompt",
                    weight=1.0,
                ))
    return out


_REASONING_TYPES = {"math", "arithmetic", "reasoning", "logic"}
_WORKINGS_RE = re.compile(r"[=+\-*/]|\bstep\b|\btherefore\b|\bso,?\s+(the )?answer", re.IGNORECASE)


def _detect_reasoning_error(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    if case.task_type.lower() in _REASONING_TYPES and case.expected.strip():
        if _norm(case.model_output) != _norm(case.expected):
            if _WORKINGS_RE.search(case.model_output):
                out.append(Evidence(
                    category="reasoning-error",
                    span=_span(case.model_output, 0, min(100, len(case.model_output))),
                    rule="reasoning-task-shows-work-but-final-answer-differs",
                    weight=1.2,
                ))
    return out


def _detect_context_misuse(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    prompt_lower = case.prompt.lower()
    marker_at = -1
    for marker in _CONTEXT_MARKERS:
        at = prompt_lower.find(marker)
        if at != -1:
            marker_at = at
            break
    if marker_at == -1 or not case.expected.strip():
        return out
    context = case.prompt[marker_at:]
    expected_terms = {w for w in re.findall(r"[a-z]{4,}", case.expected.lower())}
    if not expected_terms:
        return out
    output_lower = case.model_output.lower()
    context_lower = context.lower()
    expected_in_context = sum(1 for w in expected_terms if w in context_lower)
    expected_in_output = sum(1 for w in expected_terms if w in output_lower)
    if expected_in_context >= max(1, len(expected_terms) // 2) and \
       expected_in_output * 2 < expected_in_context:
        out.append(Evidence(
            category="context-misuse",
            span=_span(case.model_output, 0, min(80, len(case.model_output))),
            rule="expected-terms-present-in-context-but-missing-from-output",
            weight=1.2,
        ))
    return out


def _detect_partial_answer(case: FailureCase) -> List[Evidence]:
    out: List[Evidence] = []
    output = case.model_output.strip()
    questions = len(re.findall(r"\?", case.prompt))
    if questions >= 2:
        sentences = len(re.findall(r"[.!?]", output))
        if sentences < questions:
            out.append(Evidence(
                category="partial-answer",
                span=f"prompt asks {questions} questions, output has ~{sentences} sentences",
                rule="multi-question-prompt-fewer-answer-sentences",
                weight=1.0,
            ))
    expected_words = case.expected.split()
    output_words = output.split()
    if len(expected_words) > 40 and len(output_words) < 0.35 * len(expected_words):
        out.append(Evidence(
            category="partial-answer",
            span=f"output {len(output_words)} words vs expected {len(expected_words)} words",
            rule="output-much-shorter-than-expected",
            weight=1.0,
        ))
    if len(output) > 20 and not re.search(r"[.!?…\"”'`]$", output):
        out.append(Evidence(
            category="partial-answer",
            span=_span(output, max(0, len(output) - 80), len(output)),
            rule="output-ends-abruptly-without-terminal-punctuation",
            weight=0.7,
        ))
    return out


_DETECTORS = (
    _detect_refusal,
    _detect_format_error,
    _detect_instruction_violation,
    _detect_hallucination,
    _detect_reasoning_error,
    _detect_context_misuse,
    _detect_partial_answer,
)


def collect_evidence(case: FailureCase) -> List[Evidence]:
    """Run every heuristic detector over one case; returns all fired evidence."""
    evidence: List[Evidence] = []
    for detector in _DETECTORS:
        evidence.extend(detector(case))
    return evidence


# ---------------------------------------------------------------------------
# Deterministic local text features (TF-IDF over the case corpus)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z]{2,}")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def build_idf(texts: Sequence[str]) -> Dict[str, float]:
    """Inverse document frequency over the given texts. Fully deterministic."""
    doc_count = len(texts)
    df: Dict[str, int] = {}
    for text in texts:
        for term in set(_tokenize(text)):
            df[term] = df.get(term, 0) + 1
    return {
        term: math.log((1 + doc_count) / (1 + count)) + 1.0
        for term, count in df.items()
    }


def tfidf_vector(text: str, idf: Dict[str, float]) -> Dict[str, float]:
    tokens = _tokenize(text)
    if not tokens:
        return {}
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    peak = max(counts.values())
    return {
        term: (count / peak) * idf.get(term, 1.0)
        for term, count in counts.items()
    }


def cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[t] * b[t] for t in a if t in b)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _softmax(scores: List[float]) -> List[float]:
    peak = max(scores)
    exps = [math.exp(s - peak) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def _case_text(case: FailureCase) -> str:
    return f"{case.task_type} {case.prompt} {case.model_output} {case.expected}"


def assign_case(
    case: FailureCase,
    categories: Sequence[TaxonomyCategory],
    idf: Dict[str, float],
    seed_vectors: Dict[str, Dict[str, float]],
) -> Assignment:
    """Assign one case to the best taxonomy bucket with a confidence score."""
    evidence = collect_evidence(case)
    evidence_score: Dict[str, float] = {c.name: 0.0 for c in categories}
    for item in evidence:
        evidence_score[item.category] = min(
            2.0, evidence_score[item.category] + item.weight
        )
    case_vector = tfidf_vector(_case_text(case), idf)
    combined: List[float] = []
    for category in categories:
        similarity = cosine_similarity(case_vector, seed_vectors[category.name])
        combined.append(
            EVIDENCE_WEIGHT * evidence_score[category.name]
            + SIMILARITY_WEIGHT * similarity
            + PRIOR
        )
    probabilities = _softmax(combined)
    best_idx = max(range(len(categories)), key=lambda i: (probabilities[i], -i))
    confidence = probabilities[best_idx]
    relevant = [e for e in evidence if e.category == categories[best_idx].name]
    return Assignment(
        case_id=case.id,
        category=categories[best_idx].name,
        confidence=confidence,
        evidence=relevant,
        uncertain=confidence < UNCERTAIN_THRESHOLD,
    )


def assign_failures(
    cases: Sequence[FailureCase],
    categories: Sequence[TaxonomyCategory] = CATEGORIES,
) -> List[Assignment]:
    """Assign every case in a corpus. Deterministic for identical input."""
    categories = list(categories)
    corpus = [_case_text(case) for case in cases]
    seeds = [category.seed_text() for category in categories]
    idf = build_idf(corpus + seeds)
    seed_vectors = {
        category.name: tfidf_vector(category.seed_text(), idf)
        for category in categories
    }
    return [
        assign_case(case, categories, idf, seed_vectors) for case in cases
    ]


def category(name: str) -> TaxonomyCategory:
    """Look up a taxonomy category by name (KeyError if unknown)."""
    return _CATEGORY_BY_NAME[name]
