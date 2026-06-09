from __future__ import annotations

import json
from typing import Any

from vectorforge_v1.artifact_forge.contract import ArtifactNarrative
from vectorforge_v1.artifact_forge.config import get_settings
from vectorforge_v1.llm_gateway import model_json_schema, structured_llm_call, structured_openai_llm_call


def _deterministic_narrative(manifest_facts: dict[str, Any]) -> ArtifactNarrative:
    engine = manifest_facts.get("engine_type", "unknown")
    task = manifest_facts.get("task", "ml_task")
    metric = manifest_facts.get("primary_metric", "primary_metric")
    metric_val = manifest_facts.get("primary_metric_value")
    io_schema = manifest_facts.get("io_schema", {})
    input_schema = manifest_facts.get("input_schema", [])

    sample = _synthesize_sample(input_schema, io_schema, engine)

    caveats = [
        f"Requires {engine} runtime; not ONNX-portable.",
        "Serve anywhere via load_model().predict() — engine is hidden behind the contract.",
    ]
    if engine == "autorag":
        caveats.append("Inference calls OpenAI — requires OPENAI_API_KEY in the serving environment.")

    return ArtifactNarrative(
        overview=(
            f"This artifact packages the winning {engine} model for {task}. "
            f"Primary metric ({metric}): {metric_val if metric_val is not None else 'N/A'}. "
            "Use load_model().predict() for inference."
        ),
        sample_input=sample,
        usage_walkthrough=(
            "1. Install requirements: pip install -r requirements.txt\n"
            "2. Run inference: python infer.py --input sample_input.json\n"
            "3. Or import: from model_interface import load_model; load_model().predict(sample_input)"
        ),
        serving_notes=(
            "Deploy as a Python service. Wrap predict() in a FastAPI endpoint or batch pipeline. "
            "The model binary must stay co-located with model_interface.py."
        ),
        retraining_notes=(
            "Run train.py with a new dataset CSV to retrain using the same engine configuration. "
            "Pin the same requirements.txt versions for reproducibility."
        ),
        caveats=caveats,
    )


def _synthesize_sample(
    input_schema: list[dict[str, Any]],
    io_schema: dict[str, str],
    engine_type: str,
) -> dict[str, Any] | list[Any]:
    if engine_type == "autorag":
        return ["What is the main topic of the document?"]

    if not input_schema:
        return [{"feature_1": 0.0, "feature_2": "value"}]

    row: dict[str, Any] = {}
    for col_info in input_schema[:10]:
        name = col_info.get("name", col_info.get("column", "col"))
        dtype = str(col_info.get("dtype", "object")).lower()
        if "int" in dtype or "float" in dtype:
            row[name] = 0
        elif "bool" in dtype:
            row[name] = False
        else:
            row[name] = "sample_value"
    return [row]


def _validate_sample_against_io_schema(
    sample: Any,
    io_schema: dict[str, str],
    engine_type: str,
) -> bool:
    if engine_type == "autorag":
        return isinstance(sample, list) and len(sample) > 0 and isinstance(sample[0], str)
    if isinstance(sample, list) and len(sample) > 0:
        return isinstance(sample[0], dict)
    return False


def author_narrative(manifest_facts: dict[str, Any]) -> tuple[ArtifactNarrative, bool]:
    """Returns (narrative, used_llm). Falls back to deterministic on any failure."""
    settings = get_settings()
    engine_type = manifest_facts.get("engine_type", "")
    if engine_type == "autorag":
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        llm_call = structured_openai_llm_call
        model = settings.openai_model
        fallback_model = None
    else:
        api_key = settings.ai_gateway_api_key.get_secret_value() if settings.ai_gateway_api_key else None
        llm_call = structured_llm_call
        model = settings.ai_gateway_model
        fallback_model = settings.openai_model

    if not api_key:
        return _deterministic_narrative(manifest_facts), False

    try:
        context = {
            "engine_type": manifest_facts.get("engine_type"),
            "task": manifest_facts.get("task"),
            "primary_metric": manifest_facts.get("primary_metric"),
            "primary_metric_value": manifest_facts.get("primary_metric_value"),
            "secondary_metrics": manifest_facts.get("secondary_metrics", {}),
            "io_schema": manifest_facts.get("io_schema", {}),
            "input_schema": manifest_facts.get("input_schema", [])[:20],
            "runtime": manifest_facts.get("runtime", {}),
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the VectorForge artifact narrator. Write concise, accurate documentation "
                    "for this ML artifact. Return ONLY structured JSON matching the schema. "
                    "Do NOT invent metric values, commands, or file paths — those are injected separately."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context),
            },
        ]
        parsed = llm_call(
            system_prompt=messages[0]["content"],
            user_message=messages[1]["content"],
            tool_name="emit_artifact_narrative",
            tool_description="Return concise documentation for a VectorForge ML artifact.",
            output_schema=model_json_schema(ArtifactNarrative),
            api_key=api_key,
            model=model,
            fallback_model=fallback_model,
        )
        narrative = ArtifactNarrative.model_validate(parsed)

        # Check 1: schema parse succeeded (if we got here it did)
        # Check 2: validate sample_input against io_schema
        io_schema = manifest_facts.get("io_schema", {})
        engine_type = manifest_facts.get("engine_type", "")
        if not _validate_sample_against_io_schema(narrative.sample_input, io_schema, engine_type):
            synth = _synthesize_sample(manifest_facts.get("input_schema", []), io_schema, engine_type)
            narrative = narrative.model_copy(update={"sample_input": synth})

        return narrative, True

    except Exception:
        return _deterministic_narrative(manifest_facts), False
