"""LangGraph checkpointer setup for VectorForge.

Uses AsyncPostgresSaver backed by AWS RDS PostgreSQL so the long-running
conversational graph can be resumed after process restart.

Checkpoint rows are keyed by thread_id = session_id (UUID), giving a clean
  session_id → checkpoint_id
mapping that other agents can query directly from the `checkpoints` table.

Usage in main.py lifespan:
    async with get_checkpointer() as checkpointer:
        graph = build_graph().compile(checkpointer=checkpointer)

Usage in route handlers:
    config = thread_config(session_id)
    state = await graph.aget_state(config)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from conversational.config import get_settings


@asynccontextmanager
async def get_checkpointer() -> AsyncGenerator[AsyncPostgresSaver | MemorySaver, None]:
    """Yield AsyncPostgresSaver when Postgres is configured, else MemorySaver.

    MemorySaver is suitable for local dev and testing — state is lost on restart.
    Set DB_HOST + DB_PASSWORD in .env to enable durable Postgres checkpointing.
    """
    settings = get_settings()

    if not settings.postgres_configured:
        import logging
        logging.getLogger(__name__).warning(
            "DB_HOST / DB_PASSWORD not set — using in-memory checkpointer. "
            "Sessions will not survive process restart."
        )
        yield MemorySaver()
        return

    # autocommit=True is required — AsyncPostgresSaver.setup() runs
    # CREATE INDEX CONCURRENTLY which cannot execute inside a transaction block.
    # LangGraph manages its own transaction boundaries, so autocommit is safe here.
    async with AsyncConnectionPool(
        conninfo=settings.postgres_conninfo,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        yield checkpointer


def thread_config(session_id: str) -> dict:
    """Return the LangGraph config dict for a given session_id (thread_id).

    thread_id maps directly to the session UUID — every checkpoint row in
    Postgres carries this as its primary lookup key.
    """
    return {"configurable": {"thread_id": session_id}}
