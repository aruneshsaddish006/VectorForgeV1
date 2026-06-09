from __future__ import annotations

import os
from pathlib import Path

import psycopg
from fastapi import HTTPException, status
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def get_connection_kwargs() -> dict[str, str | int]:
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database is not configured. Missing: {joined}",
        )

    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "sslmode": os.getenv("DB_SSLMODE", "require"),
    }


def connect_db() -> psycopg.Connection:
    return psycopg.connect(**get_connection_kwargs())
