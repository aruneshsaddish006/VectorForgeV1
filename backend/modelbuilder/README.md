# VectorForge Modelbuilder

Dedicated Python module for the VectorForge model-building backend. It contains:

- AutoGluon experiment design
- AutoRAG experiment design
- Artifact forge packaging and deployment helpers
- Cross-designer orchestration
- The modelbuilder FastAPI entrypoint in `app.py`

Run locally from this directory:

```bash
pip install -e .
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```
