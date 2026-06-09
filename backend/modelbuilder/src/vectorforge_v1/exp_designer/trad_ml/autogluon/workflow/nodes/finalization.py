from __future__ import annotations

from vectorforge_v1.exp_designer.trad_ml.autogluon.services.artifacts import ArtifactStore
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.evaluator import ResultEvaluator
from vectorforge_v1.exp_designer.trad_ml.autogluon.services.summarizer import ResearchSummarizer
from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.state import RunState


def select_final_winner(state: RunState) -> dict:
    primary_metric = (state.get("planner_decision") or {})["selected_primary_metric"]
    winner = ResultEvaluator().select_winner(state.get("experiment_results", []), primary_metric)
    manifest_path = ArtifactStore().run_dir(state["run_id"]) / "reports" / "final_model_manifest.json"
    ArtifactStore().write_json(
        manifest_path,
        {
            "run_id": state["run_id"],
            "experiment_id": winner["experiment_id"],
            "round": winner["round"],
            "model_path": winner["model_path"],
            "primary_metric": winner["primary_metric"],
            "primary_metric_value": winner["primary_metric_value"],
            "secondary_metrics": winner.get("secondary_metrics") or {},
            "holdout_metrics_path": winner.get("holdout_metrics_path"),
        },
    )
    winner["model_manifest_path"] = str(manifest_path)
    return {
        "final_winner": winner,
        "current_best_experiment_id": winner["experiment_id"],
        "events": [{"node": "select_final_winner", "status": "completed", "message": f"Selected {winner['experiment_id']}."}],
    }


def write_final_recommendation(state: RunState) -> dict:
    winner = state["final_winner"]
    path = ResearchSummarizer().write_final_recommendation(state["run_id"], state["planner_decision"] or {}, winner)
    run_id = state["run_id"]
    store = ArtifactStore()
    store.write_status(run_id, "completed", {"final_recommendation_path": str(path)})

    return {
        "status": "completed",
        "final_recommendation_path": str(path),
        "events": [
            {"node": "write_final_recommendation", "status": "completed", "message": "Final recommendation written."},
            {
                "node": "artifact_forge",
                "status": "deferred",
                "message": "Artifact generation deferred until the artifact download endpoint is called.",
            },
        ],
    }
