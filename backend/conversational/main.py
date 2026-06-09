"""VectorForge Conversational API — FastAPI application entry point.

Start with:
    uvicorn conversational.main:app --reload --port 8000

The graph is compiled once at startup inside the lifespan context manager.
AsyncSqliteSaver is kept open for the lifetime of the process so LangGraph
checkpoints survive between request/response cycles.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from conversational.api.routes import router
from conversational.graph.checkpointer import get_checkpointer
from conversational.graph.graph import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_checkpointer() as checkpointer:
        app.state.graph = build_graph(checkpointer=checkpointer)
        yield
    app.state.graph = None


app = FastAPI(
    title="VectorForge Conversational API",
    description=(
        "Stateful LangGraph conversational API that decomposes business problems "
        "into ML experiments for AutoGluon and AutoRAG."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["ops"])
async def health() -> dict:
    graph_ready = getattr(app.state, "graph", None) is not None
    return {"status": "ok" if graph_ready else "starting", "graph_ready": graph_ready}
