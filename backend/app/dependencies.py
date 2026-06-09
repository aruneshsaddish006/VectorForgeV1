from __future__ import annotations

from typing import Any

import psycopg
from fastapi import Header, HTTPException, status
from psycopg.rows import dict_row

from app.db import connect_db
from app.services.auth_service import db_error


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.email, u.full_name, u.avatar_url
                    FROM auth_sessions s
                    JOIN app_users u ON u.id = s.user_id
                    WHERE s.token = %s
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                      AND u.status = 'active'
                    """,
                    (token,),
                )
                user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

        return {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"),
            "token": token,
        }
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc
