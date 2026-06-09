from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "forge-ai-mock-api", "time": datetime.now(timezone.utc).isoformat()}
