"""FastAPI route handlers for the VectorForge conversational LangGraph API.

Endpoints
---------
POST   /api/v1/conversations                      — start new session
GET    /api/v1/conversations/{session_id}          — get session state + pending interrupt
POST   /api/v1/conversations/{session_id}/respond  — resume graph with user answer
POST   /api/v1/conversations/{session_id}/upload-dataset  — upload file → S3 → resume
GET    /api/v1/conversations/{session_id}/final-output    — retrieve compiled output

Interrupt / resume pattern:
  1. graph.ainvoke() runs until interrupt() is called inside a node.
  2. GET /conversations/{id} returns the pending interrupt payload.
  3. Client POSTs /respond with the resume payload.
  4. Route calls graph.ainvoke(Command(resume=payload), config) to continue.

S3 upload pattern:
  1. Client POSTs /upload-dataset with multipart file + problem_id.
  2. Route uploads to S3 via s3.upload_dataset().
  3. Route resumes graph with {"s3_path": "s3://..."} so dataset_sourcing_node
     gets the path and continues to column confirmation.
"""

from __future__ import annotations

import json
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any

import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from conversational.graph.checkpointer import thread_config
from conversational.graph.state import initial_state
from conversational.models.schemas import (
    InterruptType,
    RespondRequest,
    StartConversationRequest,
    UploadDatasetResponse,
)
from conversational.services.redis_cache import write_session_output
from conversational.services.s3 import upload_dataset

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conversations"])

_ALLOWED_EXTENSIONS = {".csv", ".pdf", ".parquet"}
_EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".parquet": "application/octet-stream",
}


def _graph(request: Request):
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph not yet initialised. Retry in a moment.",
        )
    return graph


@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Start a new conversational session",
)
async def start_conversation(
    body: StartConversationRequest,
    request: Request,
) -> dict[str, Any]:
    """Create a new session and run the graph until the first interrupt.

    Uses the client-supplied session_id when provided so the frontend can
    generate a UUID and correlate the session across services.
    """
    graph = _graph(request)
    session_id = body.session_id or str(uuid.uuid4())
    config = thread_config(session_id)

    state = initial_state(session_id=session_id, first_message=body.message)

    await graph.ainvoke(state, config=config)

    # Read the full snapshot — ainvoke returns the pre-interrupt state only.
    # The snapshot has the complete state (including agent messages) after the node ran.
    snapshot = await graph.aget_state(config)
    state_values = snapshot.values if snapshot is not None else {}
    interrupt_payload = _extract_interrupt(snapshot) if snapshot is not None else None

    return {
        "data": {
            "session_id": session_id,
            "status": state_values.get("status", "intake"),
            "interrupt": interrupt_payload,
            "messages": state_values.get("messages", []),
        }
    }


@router.post(
    "/conversations/stream",
    summary="Start a conversational session with token/progress SSE streaming",
)
async def start_conversation_stream(
    body: StartConversationRequest,
    request: Request,
) -> StreamingResponse:
    """Create a session and stream the first graph run.

    Plain agent chat messages are emitted as token events so the UI can render a
    live bubble. Structured strategy/card generation emits progress events only;
    the final card payload is sent in the complete snapshot.
    """
    graph = _graph(request)
    session_id = body.session_id or str(uuid.uuid4())
    config = thread_config(session_id)
    state = initial_state(session_id=session_id, first_message=body.message)

    async def event_stream():
        async for event in _stream_graph_run(
            graph,
            graph_input=state,
            config=config,
            session_id=session_id,
            initial_phase="intake",
        ):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/conversations/{session_id}",
    summary="Get current session state and pending interrupt",
)
async def get_conversation(
    session_id: str,
    request: Request,
) -> dict[str, Any]:
    """Return the current graph state for a session."""
    graph = _graph(request)
    config = thread_config(session_id)

    snapshot = await graph.aget_state(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    state_values = snapshot.values
    interrupt_payload = _extract_interrupt(snapshot)

    # Return raw dict — avoids Pydantic stripping extra interrupt fields
    # (problem_id, problem_name, engine, accepted_formats, etc.) that the
    # frontend normaliseInterrupt reads directly from the payload.
    return {
        "data": {
            "session_id": session_id,
            "status": state_values.get("status", "intake"),
            "messages": state_values.get("messages", []),
            "interrupt": interrupt_payload,
            "final_output": state_values.get("final_output"),
        }
    }


@router.post(
    "/conversations/{session_id}/respond",
    summary="Resume the graph with a user response to an interrupt (SSE streaming)",
)
async def respond_to_interrupt(
    session_id: str,
    body: RespondRequest,
    request: Request,
) -> StreamingResponse:
    """Resume a paused graph and stream state updates as Server-Sent Events.

    Each SSE event is a JSON object with a ``type`` field:
      - ``status``  — node transitioned to a new graph status
      - ``message`` — a new agent message was produced by a node
      - ``complete``— graph reached an interrupt or finished; includes full state
      - ``error``   — unhandled exception during streaming

    LangGraph checkpoints after every node regardless of whether ``ainvoke`` or
    ``astream`` is used, so the checkpoint guarantee is unchanged.
    """
    graph = _graph(request)
    config = thread_config(session_id)

    snapshot = await graph.aget_state(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    resume_payload = body.model_dump(exclude_none=True)

    user_text = _answers_to_text(resume_payload)
    if user_text:
        await graph.aupdate_state(
            config,
            {
                "messages": [{
                    "role": "user",
                    "content": user_text,
                    "agent_name": None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "card_type": None,
                    "card_data": None,
                }]
            },
        )

    async def event_stream():
        async for event in _stream_graph_run(
            graph,
            graph_input=Command(resume=resume_payload),
            config=config,
            session_id=session_id,
            initial_phase=snapshot.values.get("status", "intake"),
        ):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/conversations/{session_id}/upload-dataset",
    summary="Upload a dataset file to S3 and resume the paused graph",
)
async def upload_dataset_endpoint(
    session_id: str,
    request: Request,
    problem_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Upload a dataset file (CSV, PDF, or Parquet) for a specific ML sub-problem.

    Handles two graph states transparently:
      - dataset_source_choice: auto-advances to awaiting_upload, then resumes with s3_path
      - awaiting_upload: resumes directly with s3_path

    This means the frontend can call this endpoint from either the choice card or the
    awaiting_upload card without needing a separate /respond call first.
    """
    graph = _graph(request)
    config = thread_config(session_id)

    snapshot = await graph.aget_state(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Validate file type by extension.
    filename = file.filename or "dataset.csv"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Accepted: .csv, .pdf, .parquet",
        )

    # Detect content-type from extension when the browser sends a generic value.
    content_type = file.content_type or _EXTENSION_CONTENT_TYPES.get(ext, "application/octet-stream")
    if content_type in ("application/octet-stream", "binary/octet-stream"):
        content_type = _EXTENSION_CONTENT_TYPES.get(ext, content_type)

    interrupt_payload = _extract_interrupt(snapshot)
    current_type = (interrupt_payload or {}).get("type")

    logger.info(
        "Upload request | session=%s problem_id=%s filename=%s ext=%s interrupt_type=%s",
        session_id, problem_id, filename, ext, current_type,
    )

    _UPLOAD_INTERRUPT_TYPES = {
        InterruptType.DATASET_SOURCE_CHOICE.value,
        InterruptType.AWAITING_UPLOAD.value,
    }
    if current_type not in _UPLOAD_INTERRUPT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Graph is not awaiting dataset input (current interrupt: {current_type!r}). "
                "Submit the dataset source choice first."
            ),
        )

    # Look up the human-readable problem name for a clean S3 key.
    ml_problems: list[dict] = snapshot.values.get("ml_sub_problems") or []
    prob = next((p for p in ml_problems if p.get("id") == problem_id), None)
    prob_name: str = prob.get("name", "") if prob else ""

    file_data = await file.read()
    logger.info("Reading file complete | filename=%s size=%d bytes", filename, len(file_data))

    try:
        s3_path = await upload_dataset(
            session_id=session_id,
            prob_id=problem_id,
            filename=filename,
            data=file_data,
            content_type=content_type,
            prob_name=prob_name,
        )
    except Exception as exc:
        logger.error("S3 upload failed | session=%s error=%s", session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"S3 upload failed: {exc}",
        )

    logger.info("S3 upload done | s3_path=%s", s3_path)

    # If the graph is still at the choice interrupt, advance it to awaiting_upload
    # before sending the s3_path.
    if current_type == InterruptType.DATASET_SOURCE_CHOICE.value:
        logger.info("Advancing graph from dataset_source_choice → awaiting_upload")
        await graph.ainvoke(Command(resume={"choice": "upload"}), config=config)

    logger.info("Resuming graph with s3_path | prob_id=%s", problem_id)
    await graph.ainvoke(
        Command(resume={"s3_path": s3_path, "prob_id": problem_id, "filename": filename}),
        config=config,
    )
    logger.info("Graph resumed successfully | session=%s", session_id)

    return {
        "data": UploadDatasetResponse(
            session_id=session_id,
            prob_id=problem_id,
            s3_path=s3_path,
            message=f"Uploaded {filename} ({ext[1:].upper()}) to {s3_path}",
        ).model_dump()
    }


@router.get(
    "/conversations/{session_id}/final-output",
    summary="Retrieve the final structured output for downstream orchestrators",
)
async def get_final_output(
    session_id: str,
    request: Request,
) -> dict[str, Any]:
    """Return the compiled FinalOutput once the conversation is complete."""
    graph = _graph(request)
    config = thread_config(session_id)

    snapshot = await graph.aget_state(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    final_output = snapshot.values.get("final_output")
    current_status = snapshot.values.get("status", "unknown")

    if not final_output:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conversation not yet complete. Current status: {current_status}.",
        )

    # Write-through: ensure Redis is populated even if the respond endpoint
    # missed the write (e.g. server restart between confirm and completion).
    await write_session_output(session_id, final_output)

    return {"data": final_output}


async def _get_interrupt(graph, config: dict) -> dict | None:
    """Fetch the latest snapshot and extract any pending interrupt payload."""
    snapshot = await graph.aget_state(config)
    if snapshot is None:
        return None
    return _extract_interrupt(snapshot)


def _extract_interrupt(snapshot) -> dict | None:
    """Pull the interrupt payload from a graph snapshot, if any."""
    tasks = getattr(snapshot, "tasks", None) or []
    for task in tasks:
        interrupts = getattr(task, "interrupts", None) or []
        if interrupts:
            return getattr(interrupts[0], "value", None)
    return None


async def _stream_graph_run(
    graph,
    graph_input,
    config: dict,
    session_id: str,
    initial_phase: str,
):
    """Stream a graph invocation as SSE.

    Text-only agent messages are split into token events for a live chat feel.
    Strategy/card events stay atomic; while they are being produced the UI gets
    progress updates instead of partial structured output.
    """
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    phase_state = {"phase": initial_phase, "strategy": initial_phase == "decomposing"}

    async def run_graph() -> None:
        try:
            async for chunk in graph.astream(
                graph_input,
                config=config,
                stream_mode="updates",
            ):
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue

                    next_status = update.get("status")
                    if next_status:
                        phase_state["phase"] = next_status
                        if next_status == "decomposing":
                            phase_state["strategy"] = True
                            await queue.put({
                                "type": "progress",
                                "phase": "strategy",
                                "label": "Generating AI strategy",
                                "detail": "Mapping the business problem into feasible ML and RAG use cases.",
                            })
                        else:
                            await queue.put({
                                "type": "status",
                                "status": next_status,
                                "node": node_name,
                            })

                    for msg in update.get("messages", []):
                        if not isinstance(msg, dict) or msg.get("role") != "agent":
                            continue
                        if msg.get("card_type") == "strategy":
                            chat_message = {
                                **msg,
                                "card_type": None,
                                "card_data": None,
                            }
                            await _enqueue_tokenized_message(queue, chat_message, node_name)
                            await queue.put({
                                "type": "progress",
                                "phase": "strategy",
                                "label": "Strategy ready",
                                "detail": "Finalizing the recommendation card and approval checkpoint.",
                            })
                            continue
                        await _enqueue_tokenized_message(queue, msg, node_name)

            await queue.put({"type": "graph_done"})
        except Exception as exc:
            await queue.put({"type": "error", "detail": str(exc)})
        finally:
            await queue.put(None)

    graph_task = asyncio.create_task(run_graph())
    progress_task = asyncio.create_task(_strategy_progress(queue, phase_state))
    had_error = False

    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            if event.get("type") == "graph_done":
                continue
            if event.get("type") == "error":
                had_error = True
            yield _sse(event)
    finally:
        progress_task.cancel()
        if not graph_task.done():
            graph_task.cancel()

    if graph_task.done() and not graph_task.cancelled():
        try:
            graph_task.result()
        except Exception as exc:
            yield _sse({"type": "error", "detail": str(exc)})
            return

    if had_error:
        return

    try:
        final_snap = await graph.aget_state(config)
        if final_snap is None:
            yield _sse({"type": "error", "detail": "Session state lost after streaming."})
            return

        state_vals = final_snap.values
        interrupt_payload = _extract_interrupt(final_snap)
        final_output = state_vals.get("final_output")

        if state_vals.get("status") == "complete" and final_output:
            await write_session_output(session_id, final_output)

        yield _sse({
            "type": "complete",
            "data": {
                "session_id": session_id,
                "status": state_vals.get("status", "unknown"),
                "interrupt": interrupt_payload,
                "messages": state_vals.get("messages", []),
                "final_output": final_output,
            },
        })
    except Exception as exc:
        yield _sse({"type": "error", "detail": f"Failed to emit final state: {exc}"})


async def _enqueue_tokenized_message(
    queue: asyncio.Queue[dict[str, Any] | None],
    message: dict[str, Any],
    node_name: str,
) -> None:
    content = str(message.get("content") or "")
    if not content:
        await queue.put({"type": "message", "message": message, "node": node_name})
        return

    base_event = {
        "agent_name": message.get("agent_name"),
        "timestamp": message.get("timestamp"),
        "card_type": message.get("card_type"),
        "card_data": message.get("card_data"),
        "node": node_name,
    }
    await queue.put({"type": "token_start", **base_event})
    for token in _text_tokens(content):
        await queue.put({"type": "token", "token": token, **base_event})
        await asyncio.sleep(0.01)
    await queue.put({"type": "token_end", "message": message, **base_event})


async def _strategy_progress(
    queue: asyncio.Queue[dict[str, Any] | None],
    phase_state: dict[str, Any],
) -> None:
    updates = [
        ("Analysing the business usecase", "Understanding the business problem statement."),
        ("Auditing constraints", "Checking available data, labels, and feasibility signals."),
        ("Routing model types", "Matching each use case to ML Training execution paths."),
        ("Enriching evidence", "Looking up benchmarks and external context for the recommendation."),
        ("Preparing final AI strategy", "Packaging the strategy so you can confirm or adjust it."),
    ]
    index = 0
    while True:
        await asyncio.sleep(2.0)
        if not phase_state.get("strategy"):
            continue
        label, detail = updates[index % len(updates)]
        index += 1
        await queue.put({
            "type": "progress",
            "phase": "strategy",
            "label": label,
            "detail": detail,
        })


def _text_tokens(content: str) -> list[str]:
    words = content.split(" ")
    if len(words) <= 1:
        return [content]
    return [f"{word} " if index < len(words) - 1 else word for index, word in enumerate(words)]


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _answers_to_text(payload: dict) -> str:
    """Convert a resume payload to a human-readable user message.

    Handles dict answers (keyed by question index), list answers, plain strings,
    and boolean confirmations so the intake/decomposer nodes see them in history.
    """
    answers = payload.get("answers")
    if answers is not None:
        if isinstance(answers, dict):
            return "\n".join(str(v) for v in answers.values())
        if isinstance(answers, list):
            return "\n".join(str(a) for a in answers)
        return str(answers)

    if "confirmed" in payload:
        return "Confirmed." if payload["confirmed"] else "Not confirmed."
    if "approved" in payload:
        return "Approved." if payload["approved"] else "Not approved."
    if "choice" in payload:
        return f"Choice: {payload['choice']}"

    return ""
