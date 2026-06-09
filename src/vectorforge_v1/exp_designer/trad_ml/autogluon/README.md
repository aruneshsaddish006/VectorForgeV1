# VectorForge Backend V1

LangGraph + FastAPI backend for the V1 agentic AutoML research loop.

## Run

```bash
uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

The default experiment mode is `mock` so the workflow can complete quickly during API development. To run real AutoGluon tabular experiments:

```bash
VECTORFORGE_EXPERIMENT_MODE=autogluon uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

The loop length and round width are configurable globally:

```bash
VECTORFORGE_MAX_ROUNDS=2 VECTORFORGE_EXPERIMENTS_PER_ROUND=4 uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

They can also be passed per run as multipart form fields named `max_rounds` and `experiments_per_round`.

AutoGluon fit parallelism is configurable. The local default is `sequential` because AutoGluon's `parallel`
strategy uses Ray and is best reserved for larger machines.

```bash
VECTORFORGE_AUTOGLUON_FIT_STRATEGY=parallel VECTORFORGE_AUTOGLUON_NUM_CPUS=6 uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

If `VECTORFORGE_AUTOGLUON_NUM_CPUS` is not set, each experiment receives roughly `os.cpu_count() / experiments_per_round` CPUs. Experiment `status.json` files include `phase`, `elapsed_seconds`, `estimated_remaining_seconds`, and `progress_percent`; `logs.txt` is created at experiment start and flushed with a small `tqdm` phase progress trace.

For fast local iteration on small datasets, VectorForge overrides AutoGluon's quality presets to skip bagging, stacking, and post-fit refits by default:

```bash
VECTORFORGE_AUTOGLUON_NUM_BAG_FOLDS=0 VECTORFORGE_AUTOGLUON_NUM_STACK_LEVELS=0 VECTORFORGE_AUTOGLUON_REFIT_FULL=false uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

To opt back into bagging, set `VECTORFORGE_AUTOGLUON_NUM_BAG_FOLDS` to `2` or higher. Global VectorForge settings override planner-provided experiment configs, so local runs stay predictable. If using bagging, `VECTORFORGE_AUTOGLUON_SAVE_BAG_FOLDS=true` keeps fold models available for safer refits at the cost of more disk usage.

LightGBM is skipped by default while local stability is being tuned:

```bash
VECTORFORGE_AUTOGLUON_DISABLED_MODEL_FAMILIES='["GBM"]' uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

Set `VECTORFORGE_AUTOGLUON_DISABLED_MODEL_FAMILIES='[]'` to allow LightGBM again.

Planner provider can be configured with `VECTORFORGE_PLANNER_PROVIDER`. To use OpenAI structured planner output, set the key in environment or `.env`:

```bash
export VECTORFORGE_OPENAI_API_KEY="your_api_key_here"
VECTORFORGE_PLANNER_PROVIDER=openai uv run uvicorn vectorforge_v1.exp_designer.trad_ml.autogluon.main:app --reload
```

`.env` example:

```dotenv
VECTORFORGE_OPENAI_API_KEY=your_api_key_here
VECTORFORGE_PLANNER_PROVIDER=openai
VECTORFORGE_OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_API_KEY` and `OPENAI_KEY` are also accepted for compatibility.

You can override the planner model with `VECTORFORGE_OPENAI_MODEL`.

## Flow Implemented

- `POST /runs` accepts a CSV plus target, problem statement, and KPI.
- LangGraph profiles the dataset and interrupts for planner confirmation.
- `POST /runs/{run_id}/confirm` resumes the graph.
- The graph runs the configured number of rounds and experiments per round, writes leaderboard/research artifacts, and finalizes a recommendation.
- `GET /workflow/mermaid` exports the compiled LangGraph as Mermaid text from LangGraph itself.
- Each optimization round records holdout validation metrics, reviews secondary metric tradeoffs, and writes a round-winning model manifest.

Artifacts are written under `runs/{run_id}/`.
