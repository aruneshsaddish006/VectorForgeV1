"""
artifact_forge LangGraph workflow.

Graph:
  START
    ↓
  build_manifest_facts          ← gather io_schema / input_schema / task facts
    ↓
  author_narrative              ← LLM ArtifactNarrative (falls back deterministically)
    ↓ (narrative_ok?)
  ├─ fail_artifact              ← terminal non-fatal failure
  └─ generate_package           ← engine-dispatched: copies model, renders templates, writes pkg dir
       ↓ (generation_ok?)
       ├─ fail_artifact
       └─ run_smoke             ← OpenSandbox / vercel-stub / local  (never raises into graph)
            ↓
          reconcile_artifact    ← stamp smoke_status into manifest; degrade sample_input if needed
            ↓ (artifact_status?)
            ├─ fail_artifact
            └─ seal_and_record  ← write artifact fields into status.json; emit terminal event
                 ↓
               END
"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from vectorforge_v1.artifact_forge.workflow.nodes import (
    author_narrative,
    build_manifest_facts,
    fail_artifact,
    generate_package,
    reconcile_artifact,
    run_smoke,
    seal_and_record,
)
from vectorforge_v1.artifact_forge.workflow.routes import (
    route_after_generation,
    route_after_narrative,
    route_after_reconcile,
    route_after_smoke,
)
from vectorforge_v1.artifact_forge.workflow.state import ArtifactForgeState


def build_artifact_forge_graph():
    builder = StateGraph(ArtifactForgeState)

    # ── nodes ──────────────────────────────────────────────────────────────
    builder.add_node("build_manifest_facts", build_manifest_facts)
    builder.add_node("author_narrative",     author_narrative)
    builder.add_node("generate_package",     generate_package)
    builder.add_node("run_smoke",            run_smoke)
    builder.add_node("reconcile_artifact",   reconcile_artifact)
    builder.add_node("seal_and_record",      seal_and_record)
    builder.add_node("fail_artifact",        fail_artifact)

    # ── edges ──────────────────────────────────────────────────────────────
    builder.add_edge(START, "build_manifest_facts")
    builder.add_edge("build_manifest_facts", "author_narrative")

    builder.add_conditional_edges("author_narrative",   route_after_narrative)
    builder.add_conditional_edges("generate_package",   route_after_generation)
    builder.add_conditional_edges("run_smoke",          route_after_smoke)
    builder.add_conditional_edges("reconcile_artifact", route_after_reconcile)

    builder.add_edge("seal_and_record", END)
    builder.add_edge("fail_artifact",   END)

    return builder.compile(checkpointer=InMemorySaver())


artifact_forge_graph = build_artifact_forge_graph()
