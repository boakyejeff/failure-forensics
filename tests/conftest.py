"""Shared fixtures for the failure-forensics test suite."""

import pytest

from failure_forensics import FailureCase


@pytest.fixture
def refusal_case() -> FailureCase:
    return FailureCase(
        id="t-refusal",
        prompt="Explain how photosynthesis works for a 10-year-old.",
        model_output="I'm sorry, but I can't help with that.",
        expected="Photosynthesis is how plants make food from sunlight.",
        task_type="explanation",
    )


@pytest.fixture
def format_case() -> FailureCase:
    return FailureCase(
        id="t-format",
        prompt="Respond in JSON format with keys 'name' and 'age'.",
        model_output="name: Ada, age: 36",
        expected='{"name": "Ada", "age": 36}',
        task_type="extraction",
    )


@pytest.fixture
def instruction_case() -> FailureCase:
    return FailureCase(
        id="t-instr",
        prompt="Answer with only 'yes' or 'no'. Is Paris the capital of France?",
        model_output="Yes, Paris is the capital of France.",
        expected="yes",
        task_type="qa",
    )


@pytest.fixture
def reasoning_case() -> FailureCase:
    return FailureCase(
        id="t-reason",
        prompt="What is 17 * 24? Show your work.",
        model_output="17 * 24 = 17*20 + 17*4 = 340 + 68 = 418. So the answer is 418.",
        expected="408",
        task_type="math",
    )


@pytest.fixture
def hallucination_case() -> FailureCase:
    return FailureCase(
        id="t-hallu",
        prompt="Who wrote the novel 'The Silent Tide'?",
        model_output=(
            "The Silent Tide was written by Elena Vasquez in 1987 and won "
            "the 1989 Harlow Prize for debut fiction."
        ),
        expected="No record of such a novel exists.",
        task_type="qa",
    )


@pytest.fixture
def context_case() -> FailureCase:
    return FailureCase(
        id="t-context",
        prompt=("Context: The Eiffel Tower is in Paris and was completed in 1889.\n"
                "Question: Where is the Eiffel Tower and when was it completed?"),
        model_output="It is in London and was completed in 1901.",
        expected="Paris, 1889",
        task_type="reading-comprehension",
    )


@pytest.fixture
def partial_case() -> FailureCase:
    return FailureCase(
        id="t-partial",
        prompt="Name the capital of France. What is 2+2? Who wrote Hamlet?",
        model_output="Paris.",
        expected="Paris. 4. Shakespeare.",
        task_type="qa",
    )


@pytest.fixture
def labeled_cases(
    refusal_case, format_case, instruction_case, reasoning_case,
    hallucination_case, context_case, partial_case,
) -> list[tuple[FailureCase, str]]:
    return [
        (refusal_case, "refusal"),
        (format_case, "format-error"),
        (instruction_case, "instruction-violation"),
        (reasoning_case, "reasoning-error"),
        (hallucination_case, "hallucination"),
        (context_case, "context-misuse"),
        (partial_case, "partial-answer"),
    ]
