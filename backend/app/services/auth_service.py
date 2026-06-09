from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from typing import Any
from uuid import uuid4

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db import connect_db
from app.schemas.auth import GoogleAuthRequest, LoginRequest, SignupRequest


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_ITERATIONS = 260_000
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


def signup(payload: SignupRequest) -> dict[str, Any]:
    email = normalize_email(payload.email)
    password_hash, password_salt, password_iterations = hash_password(payload.password)

    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT id FROM app_users WHERE email = %s", (email,))
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An account already exists for this email.",
                    )

                cursor.execute(
                    """
                    INSERT INTO app_users (email, full_name, status)
                    VALUES (%s, %s, 'active')
                    RETURNING id, email, full_name, avatar_url
                    """,
                    (email, payload.full_name.strip()),
                )
                user = cursor.fetchone()

                cursor.execute(
                    """
                    INSERT INTO user_password_credentials (user_id, password_hash, password_salt, password_iterations)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user["id"], password_hash, password_salt, password_iterations),
                )
                cursor.execute(
                    """
                    INSERT INTO auth_identities (user_id, provider, provider_user_id, email)
                    VALUES (%s, 'password', %s, %s)
                    """,
                    (user["id"], email, email),
                )

        return {
            "status": "signed_up",
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "fullName": user["full_name"],
                "avatarUrl": user.get("avatar_url"),
            },
        }
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def login(payload: LoginRequest) -> dict[str, Any]:
    email = normalize_email(payload.email)

    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                      u.id,
                      u.email,
                      u.full_name,
                      u.avatar_url,
                      u.status,
                      c.password_hash,
                      c.password_salt,
                      c.password_iterations
                    FROM app_users u
                    JOIN user_password_credentials c ON c.user_id = u.id
                    WHERE u.email = %s
                    """,
                    (email,),
                )
                user = cursor.fetchone()
                if not user or user["status"] != "active":
                    raise invalid_credentials()

                if not verify_password(
                    payload.password,
                    user["password_hash"],
                    user["password_salt"],
                    user["password_iterations"],
                ):
                    raise invalid_credentials()

                organization = get_primary_organization(cursor, str(user["id"]))
                token = create_session(cursor, str(user["id"]), "password")

        return serialize_auth_response(user, organization, token)
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def google_auth(payload: GoogleAuthRequest) -> dict[str, Any]:
    email = normalize_email(payload.email)
    provider_user_id = payload.provider_user_id or email
    base_slug = make_slug(payload.company)

    try:
        with connect_db() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.email, u.full_name, u.avatar_url
                    FROM auth_identities i
                    JOIN app_users u ON u.id = i.user_id
                    WHERE i.provider = 'google' AND i.provider_user_id = %s
                    """,
                    (provider_user_id,),
                )
                user = cursor.fetchone()

                if not user:
                    cursor.execute(
                        "SELECT id, email, full_name, avatar_url FROM app_users WHERE email = %s",
                        (email,),
                    )
                    user = cursor.fetchone()
                    if not user:
                        cursor.execute(
                            """
                            INSERT INTO app_users (email, full_name, avatar_url, status)
                            VALUES (%s, %s, %s, 'active')
                            RETURNING id, email, full_name, avatar_url
                            """,
                            (email, payload.full_name.strip(), payload.avatar_url),
                        )
                        user = cursor.fetchone()

                    cursor.execute(
                        """
                        INSERT INTO auth_identities (user_id, provider, provider_user_id, email, metadata)
                        VALUES (%s, 'google', %s, %s, %s)
                        ON CONFLICT (provider, provider_user_id) DO NOTHING
                        """,
                        (user["id"], provider_user_id, email, Jsonb({"avatarUrl": payload.avatar_url})),
                    )

                organization = get_primary_organization(cursor, str(user["id"]))
                if not organization:
                    slug = reserve_slug(cursor, base_slug)
                    cursor.execute(
                        """
                        INSERT INTO organizations (name, slug, plan)
                        VALUES (%s, %s, 'free')
                        RETURNING id, name, plan
                        """,
                        (payload.company.strip(), slug),
                    )
                    organization = cursor.fetchone()
                    cursor.execute(
                        """
                        INSERT INTO workspace_members (organization_id, user_id, role)
                        VALUES (%s, %s, 'owner')
                        ON CONFLICT (organization_id, user_id) DO NOTHING
                        """,
                        (organization["id"], user["id"]),
                    )

                token = create_session(cursor, str(user["id"]), "google")

        return serialize_auth_response(user, organization, token)
    except HTTPException:
        raise
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def logout(token: str) -> None:
    try:
        with connect_db() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = now()
                    WHERE token = %s AND revoked_at IS NULL
                    """,
                    (token,),
                )
    except psycopg.Error as exc:
        raise db_error(exc) from exc


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )
    return normalized


def make_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or f"workspace-{uuid4().hex[:8]}"


def reserve_slug(cursor: psycopg.Cursor, base_slug: str) -> str:
    slug = base_slug
    for _ in range(8):
        cursor.execute("SELECT 1 FROM organizations WHERE slug = %s", (slug,))
        if not cursor.fetchone():
            return slug
        slug = f"{base_slug}-{uuid4().hex[:4]}"
    return f"{base_slug}-{uuid4().hex[:8]}"


def hash_password(password: str, salt: str | None = None, iterations: int = PASSWORD_ITERATIONS) -> tuple[str, str, int]:
    password_salt = salt or base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("ascii")
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt.encode("utf-8"),
        iterations,
    )
    encoded_hash = base64.urlsafe_b64encode(password_hash).decode("ascii")
    return encoded_hash, password_salt, iterations


def verify_password(password: str, stored_hash: str, salt: str, iterations: int) -> bool:
    candidate_hash, _, _ = hash_password(password, salt=salt, iterations=iterations)
    return hmac.compare_digest(candidate_hash, stored_hash)


def get_primary_organization(cursor: psycopg.Cursor, user_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT o.id, o.name, o.plan
        FROM organizations o
        JOIN workspace_members wm ON wm.organization_id = o.id
        WHERE wm.user_id = %s
        ORDER BY wm.created_at ASC
        LIMIT 1
        """,
        (user_id,),
    )
    return cursor.fetchone()


def create_session(cursor: psycopg.Cursor, user_id: str, provider: str) -> str:
    token = secrets.token_urlsafe(32)
    cursor.execute(
        """
        INSERT INTO auth_sessions (user_id, token, provider, expires_at)
        VALUES (%s, %s, %s, now() + (%s || ' seconds')::interval)
        """,
        (user_id, token, provider, SESSION_TTL_SECONDS),
    )
    return token


def serialize_auth_response(user: dict[str, Any], organization: dict[str, Any] | None, token: str) -> dict[str, Any]:
    response = {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "fullName": user["full_name"],
            "avatarUrl": user.get("avatar_url"),
        },
        "workspace": None,
    }
    if organization:
        response["workspace"] = {
            "id": str(organization["id"]),
            "name": organization["name"],
            "plan": organization["plan"],
        }
    return response


def invalid_credentials() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")


def db_error(exc: psycopg.Error) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Database error: {exc.__class__.__name__}",
    )
