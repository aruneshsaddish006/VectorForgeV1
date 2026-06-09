from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import sys
import types
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "AKIA5BXDK6TMC5BEBHGX")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "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")
AWS_SESSION_TOKEN = os.environ.get("AWS_SESSION_TOKEN")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")


def run_from_file(request_path: str | Path, work_dir: str | Path = "runs", execute: bool = True) -> dict[str, Any]:
    request = _read_json(Path(request_path))
    return run_orchestrator(request, work_dir=work_dir, execute=execute)


def run_orchestrator(request: dict[str, Any], work_dir: str | Path = "runs", execute: bool = True) -> dict[str, Any]:
    _load_env_files()
    run_id = _new_run_id()
    session_id = _session_id(request, run_id)
    run_dir = Path(work_dir).resolve() / run_id
    _mkdir(run_dir)

    _write_json(run_dir / "input" / "business_request.json", request)
    _write_json(
        run_dir / "status.json",
        {
            "run_id": run_id,
            "session_id": session_id,
            "status": "running" if execute else "planned",
            "started_at": _utc_now(),
            "ready_for_experiments": request.get("ready_for_experiments"),
        },
    )

    max_rounds = _positive_int(request.get("num_round"), 3)
    experiments_per_round = _positive_int(request.get("max_experiment_per_round"), 3)
    results: list[dict[str, Any]] = []

    for problem in request.get("ml_problems", []):
        category = str(problem.get("category", "")).lower()
        engine = str(problem.get("engine", "")).lower()

        if category == "traditional" and engine == "autogluon":
            results.append(
                _route_autogluon_problem(
                    run_id=run_id,
                    session_id=session_id,
                    run_dir=run_dir,
                    request=request,
                    problem=problem,
                    max_rounds=max_rounds,
                    experiments_per_round=experiments_per_round,
                    execute=execute,
                )
            )
        elif category == "genai" and engine == "autorag":
            results.append(
                _route_autorag_problem(
                    run_id=run_id,
                    session_id=session_id,
                    run_dir=run_dir,
                    request=request,
                    problem=problem,
                    max_rounds=max_rounds,
                    experiments_per_round=experiments_per_round,
                    execute=execute,
                )
            )
        else:
            results.append(
                {
                    "problem_id": problem.get("id"),
                    "status": "skipped",
                    "reason": f"Unsupported category/engine: {category}/{engine}",
                }
            )

    status = "completed" if execute else "planned"
    if execute:
        from vectorforge_v1.utils.elasticache_pubsub import publish_end_of_message

        publish_end_of_message(session_id=session_id, run_id=run_id)

    summary = {
        "run_id": run_id,
        "session_id": session_id,
        "status": status,
        "run_dir": str(run_dir),
        "problem_results": results,
        "completed_at": _utc_now(),
    }
    _write_json(run_dir / "reports" / "orchestrator_summary.json", summary)
    _write_json(run_dir / "status.json", summary)
    return summary


def _route_autogluon_problem(
    *,
    run_id: str,
    session_id: str,
    run_dir: Path,
    request: dict[str, Any],
    problem: dict[str, Any],
    max_rounds: int,
    experiments_per_round: int,
    execute: bool,
) -> dict[str, Any]:
    problem_id = _required(problem, "id")
    problem_dir = run_dir / "problems" / problem_id
    input_dir = problem_dir / "input"
    _mkdir(input_dir)

    dataset_path = _materialize_source(problem, input_dir)
    requested_target_column = (
        problem.get("dataset", {})
        .get("target_column", {})
        .get("inferred_name")
    )
    target_column, available_columns = _resolve_csv_column(dataset_path, requested_target_column)
    business_kpi = "; ".join(problem.get("business_kpis") or [])
    problem_statement = _traditional_problem_statement(request, problem)

    planner_input = {
        "dataset_path": str(dataset_path),
        "target_column": target_column,
        "requested_target_column": requested_target_column,
        "available_columns": available_columns,
        "problem_statement": problem_statement,
        "business_kpi": business_kpi,
        "task_type_hint": problem.get("autogluon_task_type"),
        "business_context": _business_context(request, problem),
    }
    mapping = {
        "designer": "trad_ml/autogluon",
        "category": problem.get("category"),
        "engine": problem.get("engine"),
        "source_fields": {
            "dataset.source.s3_path": problem.get("dataset", {}).get("source", {}).get("s3_path"),
            "dataset.target_column.inferred_name": requested_target_column,
            "resolved_target_column": target_column,
            "available_columns": available_columns,
            "description": problem.get("description"),
            "business_kpis": problem.get("business_kpis"),
            "max_experiment_per_round": experiments_per_round,
            "num_round": max_rounds,
        },
        "designer_inputs": {
            "RunState.user_request.dataset_path": str(dataset_path),
            "RunState.user_request.target_column": target_column,
            "RunState.user_request.problem_statement": problem_statement,
            "RunState.user_request.business_kpi": business_kpi,
            "RunState.max_rounds": max_rounds,
            "RunState.experiments_per_round": experiments_per_round,
        },
    }
    _write_json(problem_dir / "planning" / "round_1_planner_input.json", planner_input)
    _write_json(problem_dir / "planning" / "field_mapping.json", mapping)
    _write_json(
        problem_dir / "planning" / "target_column_resolution.json",
        {
            "requested_target_column": requested_target_column,
            "resolved_target_column": target_column,
            "available_columns": available_columns,
        },
    )

    if not execute:
        return {
            "problem_id": problem_id,
            "designer": "autogluon",
            "status": "planned",
            "planner_input_path": str(problem_dir / "planning" / "round_1_planner_input.json"),
            "mapping_path": str(problem_dir / "planning" / "field_mapping.json"),
        }

    designer_runs_dir = run_dir / "designers" / "trad_ml" / "autogluon"
    os.environ["VECTORFORGE_RUNS_DIR"] = str(designer_runs_dir)
    from langgraph.types import Command

    from vectorforge_v1.exp_designer.trad_ml.autogluon.config import get_settings
    from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.graph import autoresearch_graph

    get_settings.cache_clear()
    designer_run_id = f"{run_id}_{problem_id}_autogluon"
    initial_state = _autogluon_initial_state(
        run_id=designer_run_id,
        session_id=session_id,
        dataset_path=str(dataset_path),
        target_column=target_column,
        problem_statement=problem_statement,
        business_kpi=business_kpi,
        max_rounds=max_rounds,
        experiments_per_round=experiments_per_round,
    )
    graph_config = {"configurable": {"thread_id": designer_run_id}}
    result = autoresearch_graph.invoke(initial_state, graph_config, version="v2")
    status = _read_status(designer_runs_dir / designer_run_id / "status.json")
    if status.get("status") == "awaiting_confirmation":
        result = autoresearch_graph.invoke(Command(resume={"confirmed": True}), graph_config, version="v2")
        status = _read_status(designer_runs_dir / designer_run_id / "status.json")

    return {
        "problem_id": problem_id,
        "designer": "autogluon",
        "status": status.get("status", "unknown"),
        "designer_run_id": designer_run_id,
        "designer_run_dir": str(designer_runs_dir / designer_run_id),
        "planner_input_path": str(problem_dir / "planning" / "round_1_planner_input.json"),
        "mapping_path": str(problem_dir / "planning" / "field_mapping.json"),
        "state_summary": _state_summary(result),
    }


def _route_autorag_problem(
    *,
    run_id: str,
    session_id: str,
    run_dir: Path,
    request: dict[str, Any],
    problem: dict[str, Any],
    max_rounds: int,
    experiments_per_round: int,
    execute: bool,
) -> dict[str, Any]:
    problem_id = _required(problem, "id")
    problem_dir = run_dir / "problems" / problem_id
    input_dir = problem_dir / "input" / "documents"
    _mkdir(input_dir)

    docs_dir = _materialize_genai_sources(problem, input_dir)
    document_description = _genai_document_description(problem)
    optimize_for = _genai_optimize_for(request, problem)
    qa_sample_count = _qa_sample_count(problem)
    planner_input = {
        "docs_dir": str(docs_dir),
        "document_description": document_description,
        "optimize_for": optimize_for,
        "qa_sample_count": qa_sample_count,
        "business_context": _business_context(request, problem),
    }
    mapping = {
        "designer": "gen_ai/autorag",
        "category": problem.get("category"),
        "engine": problem.get("engine"),
        "source_fields": {
            "dataset.source.s3_path": problem.get("dataset", {}).get("source", {}).get("s3_path"),
            "dataset.source.row_count": problem.get("dataset", {}).get("source", {}).get("row_count"),
            "dataset.source.rows_count": problem.get("dataset", {}).get("source", {}).get("rows_count"),
            "dataset.description": problem.get("dataset", {}).get("description"),
            "description": problem.get("description"),
            "business_kpis": problem.get("business_kpis"),
            "max_experiment_per_round": experiments_per_round,
            "num_round": max_rounds,
        },
        "designer_inputs": {
            "AgentState.docs_dir": str(docs_dir),
            "AgentState.document_description": document_description,
            "AgentState.optimize_for": optimize_for,
            "AgentState.qa_sample_count": qa_sample_count,
            "AgentState.max_rounds": max_rounds,
            "AgentState.architectures_per_round": experiments_per_round,
        },
    }
    _write_json(problem_dir / "planning" / "round_1_planner_input.json", planner_input)
    _write_json(problem_dir / "planning" / "field_mapping.json", mapping)

    if not execute:
        return {
            "problem_id": problem_id,
            "designer": "autorag",
            "status": "planned",
            "planner_input_path": str(problem_dir / "planning" / "round_1_planner_input.json"),
            "mapping_path": str(problem_dir / "planning" / "field_mapping.json"),
        }

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required before running the AutoRAG designer.")

    _install_sentence_transformer_splitter_stub()
    from vectorforge_v1.exp_designer.gen_ai.autorag.agentic_autorag import build_graph, utc_now_iso, write_json

    designer_run_dir = run_dir / "designers" / "gen_ai" / "autorag" / f"{run_id}_{problem_id}_autorag"
    _mkdir(designer_run_dir)
    write_json(
        designer_run_dir / "status.json",
        {
            "run_id": designer_run_dir.name,
            "status": "running",
            "started_at": utc_now_iso(),
        },
    )
    final_state = build_graph().invoke(
        {
            "run_id": designer_run_dir.name,
            "session_id": session_id,
            "docs_dir": str(Path(docs_dir).resolve()),
            "work_dir": str(designer_run_dir),
            "document_description": document_description,
            "optimize_for": optimize_for,
            "qa_sample_count": qa_sample_count,
            "max_rounds": max_rounds,
            "architectures_per_round": experiments_per_round,
            "current_round": 1,
            "experiment_history": [],
            "architecture_rationale_paths": [],
            "eval_results_paths": [],
        }
    )
    return {
        "problem_id": problem_id,
        "designer": "autorag",
        "status": "completed",
        "designer_run_id": designer_run_dir.name,
        "designer_run_dir": str(designer_run_dir),
        "planner_input_path": str(problem_dir / "planning" / "round_1_planner_input.json"),
        "mapping_path": str(problem_dir / "planning" / "field_mapping.json"),
        "report_path": final_state.get("report_path"),
    }


def _materialize_source(problem: dict[str, Any], input_dir: Path) -> Path:
    source = problem.get("dataset", {}).get("source", {})
    source_path = source.get("local_path") or source.get("path") or source.get("s3_path")
    if not source_path:
        raise ValueError(f"Problem {problem.get('id')} is missing dataset.source.s3_path or local_path")

    s3_location = _parse_s3_location(str(source_path))
    if s3_location:
        bucket, key = s3_location
        return _download_s3_object(bucket, key, input_dir / Path(key).name)

    local_path = Path(str(source_path)).expanduser().resolve()
    destination = input_dir / local_path.name
    _mkdir(destination.parent)
    shutil.copy2(local_path, destination)
    return destination


def _materialize_genai_sources(problem: dict[str, Any], input_dir: Path) -> Path:
    source = problem.get("dataset", {}).get("source", {})
    source_path = source.get("local_path") or source.get("path") or source.get("s3_path")
    if not source_path:
        raise ValueError(f"Problem {problem.get('id')} is missing dataset.source.s3_path or local_path")

    s3_location = _parse_s3_location(str(source_path))
    if s3_location:
        bucket, key = s3_location
        if key.endswith("/"):
            _download_s3_prefix(bucket, key, input_dir)
        else:
            _download_s3_object(bucket, key, input_dir / Path(key).name)
        return input_dir

    local_path = Path(str(source_path)).expanduser().resolve()
    if local_path.is_dir():
        for path in local_path.iterdir():
            if path.is_file() and not path.name.startswith("."):
                shutil.copy2(path, input_dir / path.name)
    else:
        shutil.copy2(local_path, input_dir / local_path.name)
    return input_dir


def _parse_s3_location(source_path: str) -> tuple[str, str] | None:
    parsed = urlparse(source_path)
    if parsed.scheme == "s3":
        return parsed.netloc, parsed.path.lstrip("/")
    if parsed.scheme in {"http", "https"} and ".s3." in parsed.netloc:
        bucket = parsed.netloc.split(".s3.", 1)[0]
        return bucket, parsed.path.lstrip("/")
    return None


def _download_s3_object(bucket: str, key: str, destination: Path) -> Path:
    _mkdir(destination.parent)
    _s3_client().download_file(bucket, key, str(destination))
    return destination


def _download_s3_prefix(bucket: str, prefix: str, destination_dir: Path) -> None:
    s3 = _s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    found = False
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            found = True
            relative = Path(key).relative_to(prefix)
            destination = destination_dir / relative
            _mkdir(destination.parent)
            s3.download_file(bucket, key, str(destination))
    if not found:
        raise FileNotFoundError(f"No S3 objects found under s3://{bucket}/{prefix}")


def _s3_client():
    import boto3

    kwargs: dict[str, Any] = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    if AWS_SESSION_TOKEN:
        kwargs["aws_session_token"] = AWS_SESSION_TOKEN
    return boto3.client("s3", **kwargs)


def _install_sentence_transformer_splitter_stub() -> None:
    module_name = "langchain_text_splitters.sentence_transformers"
    if module_name in sys.modules:
        return

    module = types.ModuleType(module_name)

    class SentenceTransformersTokenTextSplitter:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "SentenceTransformersTokenTextSplitter is disabled in VectorForge's non-GPU AutoRAG path."
            )

    module.SentenceTransformersTokenTextSplitter = SentenceTransformersTokenTextSplitter
    sys.modules[module_name] = module


def _resolve_csv_column(dataset_path: Path, requested_column: str | None) -> tuple[str, list[str]]:
    available_columns = _read_csv_headers(dataset_path)
    if not requested_column:
        raise ValueError(f"Target column is required. Available columns: {available_columns}")
    if requested_column in available_columns:
        return requested_column, available_columns

    casefolded = {column.casefold(): column for column in available_columns}
    requested_casefolded = requested_column.casefold()
    if requested_casefolded in casefolded:
        return casefolded[requested_casefolded], available_columns

    normalized = {_normalize_column_name(column): column for column in available_columns}
    requested_normalized = _normalize_column_name(requested_column)
    if requested_normalized in normalized:
        return normalized[requested_normalized], available_columns

    raise ValueError(
        f"Target column {requested_column!r} was not found in the dataset. "
        f"Available columns: {available_columns}"
    )


def _read_csv_headers(dataset_path: Path) -> list[str]:
    with dataset_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            return [column.strip() for column in next(reader)]
        except StopIteration as exc:
            raise ValueError(f"Dataset is empty: {dataset_path}") from exc


def _normalize_column_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _traditional_problem_statement(request: dict[str, Any], problem: dict[str, Any]) -> str:
    evidence = "; ".join(problem.get("hypothesis_evidence") or [])
    return (
        f"{problem.get('name')}: {problem.get('description')}\n"
        f"Business problem: {request.get('business_problem')}\n"
        f"Domain: {request.get('domain')}\n"
        f"Constraints: {request.get('constraint_summary')}\n"
        f"Evidence: {evidence}"
    )


def _genai_document_description(problem: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in [
            problem.get("dataset", {}).get("description"),
            problem.get("description"),
        ]
        if part
    )


def _genai_optimize_for(request: dict[str, Any], problem: dict[str, Any]) -> str:
    kpis = "; ".join(problem.get("business_kpis") or [])
    return (
        f"{problem.get('description')} "
        f"Optimize for these business KPIs: {kpis}. "
        f"Overall business problem: {request.get('business_problem')}"
    )


def _qa_sample_count(problem: dict[str, Any]) -> int:
    source = problem.get("dataset", {}).get("source", {})
    value = source.get("row_count", source.get("rows_count"))
    return _positive_int(value, int(os.environ.get("AUTORAG_AGENT_QA_SAMPLES", "24")))


def _business_context(request: dict[str, Any], problem: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_problem": request.get("business_problem"),
        "domain": request.get("domain"),
        "constraint_summary": request.get("constraint_summary"),
        "problem_id": problem.get("id"),
        "problem_name": problem.get("name"),
        "hypothesis_evidence": problem.get("hypothesis_evidence") or [],
        "business_kpis": problem.get("business_kpis") or [],
        "session_cost_usd": request.get("session_cost_usd"),
    }


def _session_id(request: dict[str, Any], fallback: str) -> str:
    value = request.get("session_id") or request.get("sessionId") or request.get("id")
    return str(value) if value else fallback


def _autogluon_initial_state(
    *,
    run_id: str,
    session_id: str,
    dataset_path: str,
    target_column: str | None,
    problem_statement: str,
    business_kpi: str,
    max_rounds: int,
    experiments_per_round: int,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "session_id": session_id,
        "status": "created",
        "current_round": 0,
        "max_rounds": max_rounds,
        "experiments_per_round": experiments_per_round,
        "user_request": {
            "dataset_path": dataset_path,
            "target_column": target_column,
            "problem_statement": problem_statement,
            "business_kpi": business_kpi,
        },
        "clarification": None,
        "dataset_profile_path": None,
        "metric_decision_path": None,
        "planner_decision": None,
        "round_plan_path": None,
        "current_round_plan": None,
        "experiment_results": [],
        "leaderboard_path": None,
        "current_best_experiment_id": None,
        "final_recommendation_path": None,
        "errors": [],
        "events": [],
        "profile_success": False,
        "initial_decision_valid": False,
        "round_plan_valid": False,
        "confirmation_confirmed": False,
        "round_success": False,
        "final_winner": None,
    }


def _state_summary(result: Any) -> dict[str, Any]:
    state = getattr(result, "value", result) or {}
    if not isinstance(state, dict):
        return {}
    return {
        "current_round": state.get("current_round"),
        "leaderboard_path": state.get("leaderboard_path"),
        "final_recommendation_path": state.get("final_recommendation_path"),
        "current_best_experiment_id": state.get("current_best_experiment_id"),
        "errors": state.get("errors", []),
    }


def _required(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not value:
        raise ValueError(f"Missing required field: {field}")
    return str(value)


def _positive_int(value: Any, default: int) -> int:
    resolved = default if value is None else int(value)
    if resolved < 1:
        raise ValueError("Round and experiment counts must be positive integers.")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> Path:
    _mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def _read_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _new_run_id() -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{stamp}_{uuid.uuid4().hex[:8]}"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _load_env_files() -> None:
    for path in _candidate_env_paths():
        if path.exists():
            _load_env_file(path)


def _candidate_env_paths() -> list[Path]:
    package_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[4]
    return [
        Path.cwd() / ".env",
        package_root / ".env",
        repo_root / ".env",
        repo_root.parent / ".env",
    ]


def _load_env_file(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description="Route VectorForge problem JSON to the right experiment designers.")
    parser.add_argument("request_json", help="Path to the business problem JSON payload.")
    parser.add_argument("--work-dir", default="runs", help="Directory where orchestrator runs are written.")
    parser.add_argument("--plan-only", action="store_true", help="Only write mapped planner inputs; do not run designers.")
    args = parser.parse_args()

    summary = run_from_file(args.request_json, work_dir=args.work_dir, execute=not args.plan_only)
    print(f"Orchestrator run complete: {summary['run_dir']}")
    print(f"Status: {summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
