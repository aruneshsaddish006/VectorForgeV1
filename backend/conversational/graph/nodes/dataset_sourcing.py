"""Dataset sourcing node — one interrupt per node run (phase-based).

Each run of this node fires exactly ONE interrupt, then returns a state
update that advances the phase. The graph routes back to this node while
status == "dataset_sourcing".

Phases per sub-problem:
  "choice"   → ask upload | discover | skip
  "upload"   → wait for /upload-dataset API call (s3_path stored in state)
  "discover" → run Exa search, show results, user picks URL
  "schema"   → confirm / override inferred column mapping

The phase is stored in state.dataset_phase so it survives node re-runs
without relying on LangGraph's interrupt replay ordering.

Resume payloads per interrupt:
  choice:   {"choice": "upload"|"discover"|"skip"}
  upload:   {"s3_path": "s3://...", "prob_id": "...", "filename": "..."}
  discover: {"selected_index": 0} | {"custom_url": "https://..."}
  schema:   {"confirmed": true} | {"column_overrides": {"col": "name"}}
"""

from __future__ import annotations

from langgraph.types import interrupt

from conversational.graph.state import ConversationalState, agent_message
from conversational.models.schemas import DatasetSourceType, InterruptType
from conversational.services.exa_search import (
    build_dataset_search_query,
    search_datasets,
)


async def dataset_sourcing_node(state: ConversationalState) -> dict:
    """Source dataset for the current sub-problem using a single interrupt per run."""
    ml_problems: list[dict] = state.get("ml_sub_problems") or []
    idx: int = state.get("pending_dataset_index", 0)

    if idx >= len(ml_problems):
        return {"status": "compiling_output"}

    problem = ml_problems[idx]
    prob_id = problem.get("id", f"prob_{idx}")
    prob_name = problem.get("name", "Unknown problem")
    engine = problem.get("engine", "autogluon")
    taxonomy_id = problem.get("taxonomy_id", "")
    inferred_columns: dict = problem.get("inferred_columns", {})
    dataset_description = problem.get("dataset_description", "")

    phase = state.get("dataset_phase", "choice")

    # ------------------------------------------------------------------ #
    # PHASE: choice — ask how the user wants to provide the dataset        #
    # ------------------------------------------------------------------ #
    if phase == "choice":
        is_autorag = engine == "autorag"
        file_hint = (
            "two CSV files (corpus.csv with doc_id + contents, and "
            "qa_eval.csv with qid + query + retrieval_gt + generation_gt)"
            if is_autorag
            else "one CSV or Parquet file"
        )

        choice_resume = interrupt(
            {
                "type": InterruptType.DATASET_SOURCE_CHOICE.value,
                "problem_id": prob_id,
                "problem_name": prob_name,
                "engine": engine,
                "taxonomy_id": taxonomy_id,
                "message": (
                    f"For **{prob_name}** I need {file_hint}. "
                    "How would you like to provide the dataset?"
                ),
                "options": [
                    {"value": "upload", "label": "Upload file(s) now"},
                    {"value": "discover", "label": "Search Kaggle / public datasets"},
                    {"value": "skip", "label": "I'll provide this later"},
                ],
                "inferred_columns": inferred_columns,
                "dataset_description": dataset_description,
            }
        )

        choice = (choice_resume or {}).get("choice", "skip")

        if choice == "upload":
            return {"status": "dataset_sourcing", "dataset_phase": "upload"}

        if choice == "discover":
            return {"status": "dataset_sourcing", "dataset_phase": "discover"}

        # skip
        return _complete_problem(
            idx,
            len(ml_problems),
            {
                "problem_id": prob_id,
                "problem_name": prob_name,
                "source_type": DatasetSourceType.SKIP,
                "note": "Dataset will be provided out-of-band by the user.",
            },
        )

    # ------------------------------------------------------------------ #
    # PHASE: upload — wait for /upload-dataset endpoint to provide s3_path #
    # ------------------------------------------------------------------ #
    if phase == "upload":
        upload_resume = interrupt(
            {
                "type": InterruptType.AWAITING_UPLOAD.value,
                "problem_id": prob_id,
                "problem_name": prob_name,
                "engine": engine,
                "message": (
                    f"Please upload your dataset file for **{prob_name}** "
                    "using the upload endpoint. "
                    "The conversation will resume once the file is in S3."
                ),
                "endpoint": "POST /api/v1/conversations/{session_id}/upload-dataset",
                "required_body_fields": {
                    "problem_id": prob_id,
                    "file": "<multipart file>",
                },
            }
        )
        s3_path = (upload_resume or {}).get("s3_path", "")
        return {
            "status": "dataset_sourcing",
            "dataset_phase": "schema",
            "dataset_pending_s3_path": s3_path,
        }

    # ------------------------------------------------------------------ #
    # PHASE: discover — run Exa search and let user pick a dataset URL     #
    # ------------------------------------------------------------------ #
    if phase == "discover":
        required_cols = [v.get("inferred_name", k) for k, v in inferred_columns.items() if v]
        query = build_dataset_search_query(prob_name, dataset_description, required_cols)

        try:
            results = await search_datasets(query, num_results=5)
        except Exception:
            results = []

        pick_resume = interrupt(
            {
                "type": InterruptType.EXA_RESULTS_REVIEW.value,
                "problem_id": prob_id,
                "problem_name": prob_name,
                "search_query": query,
                "results": results,
                "message": (
                    f"I found {len(results)} public datasets for **{prob_name}**. "
                    "Select one by index or provide a custom URL."
                ),
                "options": [
                    {
                        "label": r["title"],
                        "url": r["url"],
                        "domain": r.get("domain", ""),
                        "index": i,
                    }
                    for i, r in enumerate(results)
                ],
            }
        )

        selected_index = (pick_resume or {}).get("selected_index")
        custom_url = (pick_resume or {}).get("custom_url")

        if custom_url:
            dataset_url = custom_url
        elif selected_index is not None and results:
            chosen = results[int(selected_index)] if 0 <= int(selected_index) < len(results) else results[0]
            dataset_url = chosen["url"]
        else:
            dataset_url = ""

        return {
            "status": "dataset_sourcing",
            "dataset_phase": "schema",
            "dataset_pending_s3_path": dataset_url,
        }

    # ------------------------------------------------------------------ #
    # PHASE: schema — confirm / override the inferred column mapping       #
    # ------------------------------------------------------------------ #
    if phase == "schema":
        s3_path = state.get("dataset_pending_s3_path", "")
        is_uploaded = s3_path.startswith("s3://")

        # Auto-confirm schema for direct uploads — the user already chose the
        # file so there is no need for interactive column mapping.
        # Only interrupt on the discover path where column names may differ.
        if is_uploaded or not inferred_columns:
            overrides: dict = {}
        else:
            schema_resume = interrupt(
                {
                    "type": InterruptType.SCHEMA_CONFIRMATION.value,
                    "problem_id": prob_id,
                    "problem_name": prob_name,
                    "message": (
                        f"Here are the columns I inferred for **{prob_name}**. "
                        "Please confirm or edit the column names to match your actual dataset."
                    ),
                    "inferred_columns": inferred_columns,
                    "s3_path": s3_path,
                }
            )
            overrides = (schema_resume or {}).get("column_overrides", {})

        column_mapping = _build_column_mapping(inferred_columns, overrides)
        source_type = DatasetSourceType.UPLOAD if is_uploaded else DatasetSourceType.SKIP

        source = {
            "problem_id": prob_id,
            "problem_name": prob_name,
            "source_type": source_type,
            "engine": engine,
            "s3_path": s3_path,
            "column_mapping": column_mapping,
        }
        return _complete_problem(idx, len(ml_problems), source)

    # Fallback — should not reach here
    return {"status": "compiling_output"}


def _complete_problem(idx: int, total: int, source: dict) -> dict:
    """Return state update that finalises one sub-problem's dataset and advances the index."""
    next_idx = idx + 1
    next_status = "dataset_sourcing" if next_idx < total else "compiling_output"
    return {
        "status": next_status,
        "pending_dataset_index": next_idx,
        "dataset_phase": "choice",        # reset phase for the next problem
        "dataset_pending_s3_path": "",
        "dataset_sources": [source],
        "messages": [
            agent_message(
                content=_source_summary(source),
                agent_name="Dataset Agent",
                card_type="dataset_source",
                card_data=source,
            )
        ],
    }


def _build_column_mapping(inferred_columns: dict, overrides: dict) -> dict:
    confirmed: dict = {}
    for key, meta in inferred_columns.items():
        confirmed[key] = {
            **meta,
            "confirmed_name": overrides.get(key, meta.get("inferred_name", "")),
            "user_confirmed": True,
        }
    return confirmed


def _source_summary(source: dict) -> str:
    stype = source.get("source_type")
    name = source.get("problem_name", "")
    if stype == DatasetSourceType.UPLOAD:
        return f"Dataset for **{name}** uploaded to S3: `{source.get('s3_path', '')}`."
    if stype == DatasetSourceType.DISCOVER:
        return f"Dataset for **{name}** sourced: {source.get('dataset_url', '')}."
    return f"Dataset for **{name}** marked as pending — will be provided out-of-band."
