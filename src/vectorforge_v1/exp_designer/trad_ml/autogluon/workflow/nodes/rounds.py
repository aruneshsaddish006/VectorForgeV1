from __future__ import annotations

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.evaluator import ResultEvaluator
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.summarizer import ResearchSummarizer
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def initialize_round(state: RunState) -> dict:
    round_number = state.get("current_round", 0) + 1
    ArtifactStore().write_status(state["run_id"], "running", {"current_round": round_number})
    return {
        "status": "running",
        "current_round": round_number,
        "round_success": False,
        "events": [{"node": "initialize_round", "status": "completed", "message": f"Round {round_number} initialized."}],
    }


def dispatch_experiments(state: RunState) -> dict:
    return {
        "events": [
            {
                "node": "dispatch_experiments",
                "status": "completed",
                "message": f"Dispatching {len((state.get('current_round_plan') or {}).get('experiments', []))} experiments.",
            }
        ]
    }


def collect_round_results(state: RunState) -> dict:
    round_number = state["current_round"]
    round_results = [result for result in state.get("experiment_results", []) if result["round"] == round_number]
    has_success = any(result["status"] == "completed" for result in round_results)
    return {
        "round_success": has_success,
        "events": [{"node": "collect_round_results", "status": "completed", "message": "Round results collected."}],
        **({} if has_success else {"errors": [{"node": "collect_round_results", "message": "No successful experiments."}]}),
    }


def select_round_winner(state: RunState) -> dict:
    round_number = state["current_round"]
    primary_metric = (state.get("planner_decision") or {})["selected_primary_metric"]
    round_results = [result for result in state.get("experiment_results", []) if result["round"] == round_number]
    winner = ResultEvaluator().select_winner(round_results, primary_metric)
    manifest_path = _write_model_manifest(state["run_id"], winner, f"round_{round_number}_winner")
    winner["model_manifest_path"] = str(manifest_path)
    ArtifactStore().write_leaderboard(state["run_id"], state.get("experiment_results", []))
    return {
        "current_best_experiment_id": winner["experiment_id"],
        "events": [{"node": "select_round_winner", "status": "completed", "message": f"Selected {winner['experiment_id']}."}],
    }


def summarize_round(state: RunState) -> dict:
    round_number = state["current_round"]
    primary_metric = (state.get("planner_decision") or {})["selected_primary_metric"]
    round_results = [result for result in state.get("experiment_results", []) if result["round"] == round_number]
    winner = ResultEvaluator().select_winner(round_results, primary_metric)
    path = ResearchSummarizer().append_round_summary(
        state["run_id"], round_number, state.get("current_round_plan") or {}, round_results, winner
    )
    return {
        "leaderboard_path": str(ArtifactStore().run_dir(state["run_id"]) / "reports" / "leaderboard.csv"),
        "events": [{"node": "summarize_round", "status": "completed", "message": f"Updated {path}."}],
    }


def should_continue_rounds(state: RunState) -> dict:
    return {
        "events": [{"node": "should_continue_rounds", "status": "completed", "message": "Round continuation checked."}]
    }


def _write_model_manifest(run_id: str, winner: dict, name: str) -> str:
    store = ArtifactStore()
    path = store.run_dir(run_id) / "reports" / f"{name}_model_manifest.json"
    store.write_json(
        path,
        {
            "run_id": run_id,
            "experiment_id": winner["experiment_id"],
            "round": winner["round"],
            "model_path": winner["model_path"],
            "primary_metric": winner["primary_metric"],
            "primary_metric_value": winner["primary_metric_value"],
            "secondary_metrics": winner.get("secondary_metrics") or {},
            "holdout_metrics_path": winner.get("holdout_metrics_path"),
        },
    )
    return str(path)
