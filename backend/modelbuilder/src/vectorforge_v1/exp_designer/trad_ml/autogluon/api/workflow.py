from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from vectorforge_v1.exp_designer.trad_ml.autogluon.workflow.graph import autoresearch_graph

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.get("/mermaid", response_class=PlainTextResponse)
def get_workflow_mermaid() -> str:
    return autoresearch_graph.get_graph().draw_mermaid()
