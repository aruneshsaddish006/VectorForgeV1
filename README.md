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

## Notes For Future Orchestrator

The future orchestrator should import each designer through its package boundary:

```python
from vectorforge_v1.exp_designer.trad_ml import autogluon
from vectorforge_v1.exp_designer.gen_ai import autorag
```

This keeps traditional ML and GenAI experiment design isolated while allowing orchestration code to coordinate both.
