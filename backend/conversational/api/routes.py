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

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from langgraph.types import Command

from conversational.graph.checkpointer import thread_config
from conversational.graph.state import initial_state
from conversational.models.schemas import (
    ConversationStateResponse,
    RespondRequest,
    StartConversationRequest,
    UploadDatasetResponse,
)
from conversational.services.redis_cache import write_session_output
from conversational.services.s3 import upload_dataset

router = APIRouter(tags=["conversations"])


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

    result = await graph.ainvoke(state, config=config)
    interrupt_payload = await _get_interrupt(graph, config)

    return {
        "data": {
            "session_id": session_id,
            "status": result.get("status", "intake"),
            "interrupt": interrupt_payload,
            "messages": result.get("messages", []),
        }
    }


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

    return {
        "data": ConversationStateResponse(
            session_id=session_id,
            status=state_values.get("status", "unknown"),
            messages=state_values.get("messages", []),
            interrupt=interrupt_payload,
            final_output=state_values.get("final_output"),
        ).model_dump()
    }


@router.post(
    "/conversations/{session_id}/respond",
    summary="Resume the graph with a user response to an interrupt",
)
async def respond_to_interrupt(
    session_id: str,
    body: RespondRequest,
    request: Request,
) -> dict[str, Any]:
    """Resume a paused graph with the user's answer.

    The payload in body.response is passed directly to Command(resume=...) and
    forwarded to the node that called interrupt().
    """
    graph = _graph(request)
    config = thread_config(session_id)

    snapshot = await graph.aget_state(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    resume_payload = body.model_dump(exclude_none=True)

    # Append the user's answers as a conversation message so nodes that
    # re-run from the top (e.g. intake) see the answers in message history.
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

    result = await graph.ainvoke(Command(resume=resume_payload), config=config)
    interrupt_payload = await _get_interrupt(graph, config)

    # Write the final JSON output to Redis once the conversation is complete.
    # The output matches conv-output-schema.json exactly — orchestrators read
    # from Redis at key vforge:conv:{session_id} without any transformation.
    final_output = result.get("final_output")
    if result.get("status") == "complete" and final_output:
        await write_session_output(session_id, final_output)

    return {
        "data": {
            "session_id": session_id,
            "status": result.get("status", "unknown"),
            "interrupt": interrupt_payload,
            "messages": result.get("messages", []),
            "final_output": final_output,
        }
    }


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
    """Upload a dataset file for a specific ML sub-problem.

    Stores the file in S3 and resumes the dataset_sourcing_node with the
    resulting S3 path so the graph can proceed to column confirmation.
    """
    graph = _graph(request)
    config = thread_config(session_id)

    snapshot = await graph.aget_state(config)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    file_data = await file.read()
    filename = file.filename or "dataset.csv"
    content_type = file.content_type or "text/csv"

    try:
        s3_path = await upload_dataset(
            session_id=session_id,
            prob_id=problem_id,
            filename=filename,
            data=file_data,
            content_type=content_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"S3 upload failed: {exc}",
        )

    resume_payload = {
        "s3_path": s3_path,
        "prob_id": problem_id,
        "filename": filename,
    }
    await graph.ainvoke(Command(resume=resume_payload), config=config)

    return {
        "data": UploadDatasetResponse(
            session_id=session_id,
            prob_id=problem_id,
            s3_path=s3_path,
            message=f"Uploaded {filename} to {s3_path}",
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
