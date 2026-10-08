# Failure Forensics  -  Synthetic Demo Report

> Method note: bucket labels are assigned by transparent, rule-based heuristics plus local text similarity  -  they are a starting point for human review, not ground truth. Root causes below are heuristic hypotheses to investigate, not verified diagnoses.

## Summary

- Failure cases analyzed: **21**
- Taxonomy buckets hit: **7** of 7
- Low-confidence assignments (worth human review): **2**

## Bucket distribution

| Bucket | Count | Share |
| --- | ---: | ---: |
| hallucination | 4 | 19.0% |
| context-misuse | 3 | 14.3% |
| format-error | 3 | 14.3% |
| instruction-violation | 3 | 14.3% |
| reasoning-error | 3 | 14.3% |
| refusal | 3 | 14.3% |
| partial-answer | 2 | 9.5% |

## Failures by task type

| Task type | hallucination | context-misuse | format-error | instruction-violation | reasoning-error | refusal | partial-answer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| explanation | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| extraction | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| generation | 0 | 0 | 1 | 1 | 0 | 1 | 0 |
| logic | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| math | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| qa | 2 | 1 | 0 | 2 | 0 | 1 | 1 |
| reading-comprehension | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| summarization | 1 | 0 | 0 | 0 | 0 | 0 | 1 |

## Bucket deep dives

### hallucination  -  4 cases (19%)

_The model invents facts, entities, dates, or citations that are not supported by the prompt, the provided context, or the expected answer._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: The model may be filling gaps with parametric memory instead of grounding in the given context, with decoding favoring fluency over factuality.

**Suggested fix**: Add grounding checks: verify named entities and numbers against the source context; consider retrieval augmentation or constrained decoding; lower the temperature for factual tasks.

**Example cases:**

- `syn-004` (confidence 0.78)
  - Prompt: Who wrote the novel 'The Silent Tide'?
  - Model output: The Silent Tide was written by Elena Vasquez in 1987 and won the 1989 Harlow Prize for debut fiction.
  - Expected: No record of such a novel exists.
  - Evidence [entities-in-output-absent-from-prompt-and-expected]: "novel entities not in prompt/expected: Elena, Vasquez, Harlow, Prize"
- `syn-002` (confidence 0.77)
  - Prompt: What did Dr. Alvarez conclude in her 2021 paper on coral bleaching?
  - Model output: Dr. Alvarez concluded that thermal stress declined 30% between 2019 and 2021, reversing the trend (Alvarez et al., 2021).
  - Expected: Unknown; no such paper was provided.
  - Evidence [citation-like-pattern-absent-from-prompt]: "and 2021, reversing the trend (Alvarez et al., 2021)."
- `syn-020` (confidence 0.77)
  - Prompt: Summarize the 2023 Meridian Health annual report.
  - Model output: Meridian Health reported revenue of $4.2 billion in 2023, led by CEO Jonathan Pryce, and opened 14 new clinics in Ohio.
  - Expected: I don't have access to that report.
  - Evidence [entities-in-output-absent-from-prompt-and-expected]: "novel entities not in prompt/expected: Jonathan, Pryce, Ohio"

### context-misuse  -  3 cases (14%)

_The prompt supplies a context or passage and the model fails to use it: answering from prior knowledge instead, or contradicting the given context._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: Long context may dilute attention; the model may fall back on parametric priors instead of the provided passage.

**Suggested fix**: Shorten and highlight the relevant context span; ask the model to quote the supporting passage before answering.

**Example cases:**

- `syn-010` (confidence 0.87)
  - Prompt: Context: The Eiffel Tower is in Paris and was completed in 1889. Question: Where is the Eiffel Tower and when was it completed?
  - Model output: It is in London and was completed in 1901.
  - Expected: Paris, 1889
  - Evidence [expected-terms-present-in-context-but-missing-from-output]: "It is in London and was completed in 1901."
- `syn-007` (confidence 0.87)
  - Prompt: Context: Photosynthesis occurs in chloroplasts, which contain chlorophyll. Question: Where does photosynthesis occur?
  - Model output: Photosynthesis occurs in the mitochondria, the powerhouse of the cell.
  - Expected: In chloroplasts
  - Evidence [expected-terms-present-in-context-but-missing-from-output]: "Photosynthesis occurs in the mitochondria, the powerhouse of the cell."
- `syn-015` (confidence 0.16, UNCERTAIN)
  - Prompt: What is the best approach here?
  - Model output: The answer might be 42 but I'm not fully sure; the context suggests otherwise.
  - Expected: It depends on the constraints.

### format-error  -  3 cases (14%)

_The response content may be right but the required format is wrong: invalid JSON, missing bullet list, missing table, wrong schema._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: Format constraints may be treated as soft preferences rather than hard constraints; structured-output decoding is not enforced.

**Suggested fix**: Use structured-output APIs or JSON-schema validation with retry; include a concrete format example in the prompt.

**Example cases:**

- `syn-021` (confidence 0.94)
  - Prompt: Respond in JSON format with keys 'name' and 'age'.
  - Model output: name: Ada, age: 36
  - Expected: {"name": "Ada", "age": 36}
  - Evidence [prompt-asks-json-output-not-valid-json]: "name: Ada, age: 36"
- `syn-011` (confidence 0.94)
  - Prompt: Return the answer in JSON format: {"city": ..., "country": ...}.
  - Model output: The city is Lima and the country is Peru.
  - Expected: {"city": "Lima", "country": "Peru"}
  - Evidence [prompt-asks-json-output-not-valid-json]: "The city is Lima and the country is Peru."
- `syn-014` (confidence 0.77)
  - Prompt: Give the result as a bullet list.
  - Model output: First we add the flour, then we add the sugar and mix everything together.
  - Expected: - flour - sugar - mix
  - Evidence [prompt-asks-bullet-list-no-bullets-found]: "First we add the flour, then we add the sugar and mix everything together."

### instruction-violation  -  3 cases (14%)

_The model ignores or disobeys an explicit instruction in the prompt, such as answering only yes/no, listing exactly N items, or not explaining._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: Instruction-following may be weaker than content generation; the critical instruction may be buried, ambiguous, or stated only once.

**Suggested fix**: Move critical instructions to the start and the end of the prompt, use explicit delimiters, and add an output-shape verification step before accepting the response.

**Example cases:**

- `syn-006` (confidence 0.99)
  - Prompt: List exactly 3 colors. Do not explain.
  - Model output: Red, blue, green, and also yellow which is a warm color often used in design because it stands out.
  - Expected: red, blue, green
  - Evidence [prompt-requires-exact-item-count]: "asked for 3 items, found 0 list markers"
  - Evidence [prompt-forbids-explanation-output-explains]: "Red, blue, green, and also yellow which is a warm color often used in design because it stands out."
- `syn-013` (confidence 0.94)
  - Prompt: Answer with only 'yes' or 'no'. Is Paris the capital of France?
  - Model output: Yes, Paris is the capital of France and has been since the medieval period.
  - Expected: yes
  - Evidence [prompt-requires-yes-no-only-output-is-longer]: "Yes, Paris is the capital of France and has been since the medieval period."
- `syn-017` (confidence 0.94)
  - Prompt: Answer with only 'yes' or 'no': does water boil at 100C at sea level?
  - Model output: Yes. At standard atmospheric pressure, pure water boils at 100 degrees Celsius.
  - Expected: yes
  - Evidence [prompt-requires-yes-no-only-output-is-longer]: "Yes. At standard atmospheric pressure, pure water boils at 100 degrees Celsius."

### reasoning-error  -  3 cases (14%)

_The model shows its work but arrives at the wrong conclusion: arithmetic slips, faulty logic steps, or a wrong final answer on a reasoning task._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: Multi-step computation may exceed the model's reliable working memory; small errors compound across steps without verification.

**Suggested fix**: Prompt for step-by-step work with intermediate verification, use tools or calculators for arithmetic, and add a self-check pass over the final answer.

**Example cases:**

- `syn-016` (confidence 0.86)
  - Prompt: If all bloops are razzies and some razzies are lazzies, are all bloops lazzies? Explain step by step.
  - Model output: Step 1: all bloops are razzies. Step 2: some razzies are lazzies. Step 3: therefore all bloops are lazzies. Answer: yes.
  - Expected: No - the premises only support 'some bloops may be lazzies'.
  - Evidence [reasoning-task-shows-work-but-final-answer-differs]: "Step 1: all bloops are razzies. Step 2: some razzies are lazzies. Step 3: therefore all bloops are lazzies. Answer: yes."
- `syn-009` (confidence 0.86)
  - Prompt: What is 17 * 24? Show your work.
  - Model output: 17 * 24 = 17*20 + 17*4 = 340 + 68 = 418. So the answer is 418.
  - Expected: 408
  - Evidence [reasoning-task-shows-work-but-final-answer-differs]: "17 * 24 = 17*20 + 17*4 = 340 + 68 = 418. So the answer is 418."
- `syn-018` (confidence 0.86)
  - Prompt: A train travels 60 km/h for 2.5 hours. How far does it go? Show your work.
  - Model output: Distance = speed x time = 60 x 2.5 = 120 + 30 = 140. So, 140 km.
  - Expected: 150 km
  - Evidence [reasoning-task-shows-work-but-final-answer-differs]: "Distance = speed x time = 60 x 2.5 = 120 + 30 = 140. So, 140 km."

### refusal  -  3 cases (14%)

_The model refuses to answer a benign prompt: apologies, claims of inability, or safety-style deflection._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: Safety tuning may be over-triggered on benign prompts; the refusal classifier may be miscalibrated for this task type.

**Suggested fix**: Review refusal triggers on a calibration set; clarify benign intent in the prompt; tune safety thresholds per task type.

**Example cases:**

- `syn-012` (confidence 0.99)
  - Prompt: What is the capital of Japan?
  - Model output: As an AI, I'm unable to answer that.
  - Expected: Tokyo
  - Evidence [refusal-phrase:\bi'?m unable to\b]: "As an AI, I'm unable to answer that."
  - Evidence [refusal-phrase:\bas an ai\b]: "As an AI, I'm unable to answer that."
- `syn-019` (confidence 0.99)
  - Prompt: Explain how photosynthesis works for a 10-year-old.
  - Model output: I'm sorry, but I can't help with that.
  - Expected: Photosynthesis is how plants make food from sunlight...
  - Evidence [refusal-phrase:\bi'?m sorry\b]: "I'm sorry, but I can't help with that."
  - Evidence [refusal-phrase:\bi can'?t\b]: "I'm sorry, but I can't help with that."
  - Evidence [refusal-phrase:\bcan'?t help\b]: "I'm sorry, but I can't help with that."
- `syn-001` (confidence 0.94)
  - Prompt: Write a haiku about the ocean.
  - Model output: I cannot help with that request.
  - Expected: Waves fold to shore / salt on the evening wind / the moon pulls them home
  - Evidence [refusal-phrase:\bi cannot\b]: "I cannot help with that request."

### partial-answer  -  2 cases (10%)

_The model answers only part of the request: a multi-part question gets a single-part answer, the response trails off, or the output is far shorter than the expected answer._

**Hypothesized root cause** *(heuristic hypothesis, not verified)*: The model may satisfice on the first sub-question; multi-part prompts may exceed its effective planning horizon.

**Suggested fix**: Number the sub-questions explicitly, require a labeled answer per part, and add a completeness checklist to the prompt.

**Example cases:**

- `syn-003` (confidence 0.78)
  - Prompt: Name the capital of France. What is 2+2? Who wrote Hamlet?
  - Model output: Paris.
  - Expected: Paris. 4. Shakespeare.
  - Evidence [multi-question-prompt-fewer-answer-sentences]: "prompt asks 2 questions, output has ~1 sentences"
- `syn-008` (confidence 0.58)
  - Prompt: Summarize the plot of Dune in two sentences. Also list the main characters. Also state the author's name.
  - Model output: Dune is about a desert planet called Arrakis where
  - Expected: Dune follows Paul Atreides on Arrakis. Main characters: Paul, Jessica, Duncan. Author: Frank Herbert.
  - Evidence [output-ends-abruptly-without-terminal-punctuation]: "Dune is about a desert planet called Arrakis where"

## Needs human review (low confidence)

- `syn-005` -> hallucination (0.15): Describe the process.
- `syn-015` -> context-misuse (0.16): What is the best approach here?

---
Generated by the failure-forensics tool. Treat every label as a heuristic suggestion: sample the buckets, read the raw cases, and let human judgment decide.
