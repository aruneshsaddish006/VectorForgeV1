# VectorForge V1

VectorForge V1 reconciles the two current experiment designers into one repository layout so an orchestrator can later coordinate them from stable package paths.

## Repository Layout

```text
VectorforgeV1/
  src/
    vectorforge_v1/
      orchestrator/              # future cross-designer orchestration layer
      agent/                     # future agent coordination layer
      routes/                    # future API route aggregation layer
      utils/                     # shared utilities
      exp_designer/
        trad_ml/
          autogluon/             # traditional ML experiment designer
        gen_ai/
          autorag/               # GenAI/RAG experiment designer
```

## Experiment Designers

### Traditional ML: AutoGluon

Location:

```text
src/vectorforge_v1/exp_designer/trad_ml/autogluon/
```

This is the AutoGluon/FastAPI/LangGraph designer copied from `VectorForge/AutoGluon`. Its imports have been rewritten to the new package path:

```python
vectorforge_v1.exp_designer.trad_ml.autogluon
```

Run API server:

```bash
vectorforge-v1-trad-ml
```

Equivalent module command:

```bash
python -m vectorforge_v1.exp_designer.trad_ml.autogluon
```

### GenAI: AutoRAG

Location:

```text
src/vectorforge_v1/exp_designer/gen_ai/autorag/
```

This is the AutoRAG/LangGraph designer copied from `VectorForge/agentic_autorag.py`.

Run the AutoRAG designer:

```bash
vectorforge-v1-gen-ai \
  --docs-dir /path/to/documents \
  --work-dir runs \
  --fresh \
  --rounds 3 \
  --architectures-per-round 3 \
  --document-description "PDFs with images and tables" \
  --optimize-for "I want broad coverage and fewer hallucinations"
```

Equivalent module command:

```bash
python -m vectorforge_v1.exp_designer.gen_ai.autorag \
  --docs-dir /path/to/documents \
  --work-dir runs \
  --fresh
```

## Installation

Create a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Install only the shared package:

```bash
pip install -e .
```

Install traditional ML dependencies:

```bash
pip install -e ".[trad-ml]"
```

Install GenAI/RAG dependencies:

```bash
pip install -e ".[gen-ai]"
```

Install both designer stacks:

```bash
pip install -e ".[all]"
```

## Environment

AutoGluon designer settings use `VECTORFORGE_*` environment variables.

AutoRAG designer requires:

```bash
OPENAI_API_KEY=...
```

Optional AutoRAG variables:

```bash
AUTORAG_AGENT_MODEL=gpt-4o-mini-2024-07-18
AUTORAG_AGENT_GEVAL_MODEL=gpt-4o-mini-2024-07-18
AUTORAG_AGENT_QA_SAMPLES=4
```

## Orchestrator

The orchestrator accepts a business-problem JSON payload with one or more `ml_problems`.
It routes each problem to the matching experiment designer:

- `category=traditional`, `engine=autogluon` -> `exp_designer/trad_ml/autogluon`
- `category=genai`, `engine=autorag` -> `exp_designer/gen_ai/autorag`

Run only the mapping/planning step:

```bash
vectorforge-v1-orchestrate request.json --work-dir runs --plan-only
```

Run the mapped designers:

```bash
vectorforge-v1-orchestrate request.json --work-dir runs
```

The orchestrator writes:

- `input/business_request.json`: original request payload
- `problems/<problem_id>/planning/round_1_planner_input.json`: the first-round context passed to the selected designer
- `problems/<problem_id>/planning/field_mapping.json`: source JSON fields mapped to designer inputs
- `designers/trad_ml/autogluon/...`: AutoGluon designer run outputs
- `designers/gen_ai/autorag/...`: AutoRAG designer run outputs
- `reports/orchestrator_summary.json`: top-level routing and run summary

Programmatic use:

```python
from vectorforge_v1.orchestrator import run_orchestrator

summary = run_orchestrator(payload, work_dir="runs", execute=True)
```

This keeps traditional ML and GenAI experiment design isolated while allowing orchestration code to coordinate both.
