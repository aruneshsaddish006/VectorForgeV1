"""LangGraph StateGraph assembly for the VectorForge conversational workflow.

Node execution order:
  START → intake → decomposer → dataset_sourcing ↩ (loop per sub-problem)
                                                  → output_compiler → END

Conditional routing is driven by state.status:
  "intake"           → intake
  "decomposing"      → decomposer
  "dataset_sourcing" → dataset_sourcing
  "compiling_output" → output_compiler
  "complete"         → END

Each node may interrupt() mid-execution. The graph is compiled once per
process (app startup) with the AsyncSqliteSaver checkpointer injected so
long-running conversations survive process restarts.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from conversational.graph.nodes.dataset_sourcing import dataset_sourcing_node
from conversational.graph.nodes.decomposer import decomposer_node
from conversational.graph.nodes.intake import intake_node
from conversational.graph.nodes.output_compiler import output_compiler_node
from conversational.graph.state import ConversationalState


def _route(state: ConversationalState) -> str:
    status = state.get("status", "intake")
    routes = {
        "intake": "intake",
        "decomposing": "decomposer",
        "dataset_sourcing": "dataset_sourcing",
        "compiling_output": "output_compiler",
        "complete": END,
    }
    return routes.get(status, "intake")


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Build and compile the VectorForge conversational StateGraph.

    Args:
        checkpointer: AsyncSqliteSaver (or any BaseCheckpointSaver) injected at
                      app startup. When None the graph still compiles but cannot
                      resume interrupted sessions.

    Returns:
        Compiled LangGraph graph.
    """
    builder = StateGraph(ConversationalState)

    builder.add_node("intake", intake_node)
    builder.add_node("decomposer", decomposer_node)
    builder.add_node("dataset_sourcing", dataset_sourcing_node)
    builder.add_node("output_compiler", output_compiler_node)

    builder.add_conditional_edges(START, _route)

    builder.add_conditional_edges("intake", _route)
    builder.add_conditional_edges("decomposer", _route)
    builder.add_conditional_edges("dataset_sourcing", _route)
    builder.add_conditional_edges("output_compiler", _route)

    return builder.compile(checkpointer=checkpointer)
