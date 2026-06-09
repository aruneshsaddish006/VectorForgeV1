# Forge AI Mock Backend

Python mock API for the AI Strategy & Use-Case Intelligence Platform demo flow.

## Project structure

```text
backend/
  main.py                 # Thin uvicorn entry point
  app/
    main.py               # FastAPI app factory and router registration
    core/config.py        # App settings and CORS configuration
    db/connection.py      # Postgres connection helper
    schemas/              # Pydantic request/response contracts
    services/             # Business logic and database operations
    routers/              # HTTP route handlers
../db/
  schema.sql              # Database schema
  init_db.py              # Schema initializer
```

To add a new service, create a schema file under `app/schemas`, put the business logic in `app/services`, expose HTTP handlers from `app/routers`, then include the router in `app/main.py`.

## Setup with uv

```bash
cd backend
uv venv
uv sync
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

The backend reads database settings from `backend/.env`. The frontend reads `NEXT_PUBLIC_API_URL` from `frontend/.env.local` and falls back to `http://localhost:8000`.

## Add packages

Use `pyproject.toml` as the dependency source of truth.

```bash
uv add fastapi "uvicorn[standard]" "psycopg[binary]" python-dotenv
uv sync
```

## Initialize PostgreSQL schema

Confirm `backend/.env` contains database credentials, then run the initializer.

```bash
cd ../db
uv run --project ../backend python init_db.py
```

## Key Endpoints

- `GET /health`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/google`
- `POST /api/auth/logout`
- `GET /api/workspaces`
- `POST /api/workspaces`
- `GET /api/projects?workspaceId={workspace_id}`
- `POST /api/projects`
- `GET /api/datasets?workspaceId={workspace_id}`
- `GET /api/models?workspaceId={workspace_id}`
- `GET /api/workspaces/{workspace_id}/projects/{project_id}/assets`
- `GET /api/demo-workspace`
- `GET /api/strategy`
- `GET /api/data-sources`
- `POST /api/exa/runs`
- `GET /api/exa/runs/{run_id}`
- `POST /api/datasets/{dataset_id}/confirm`
- `POST /api/training/runs`
- `POST /api/deployments`
- `POST /api/billing/approve`

## Auth behavior

- Email signup creates an `app_users` record, password credential, and password identity.
- Email login validates the password hash and creates a new session.
- Google auth currently uses a mock provider payload and stores the identity in `auth_identities` with `provider = 'google'`. A production Google OAuth or Google Identity Services token verification step can reuse the same endpoint contract.


kill -9 $(lsof -ti:8001) && echo "killed"

kill -9 $(lsof -ti:8000) && echo "killed"

kill -9 $(lsof -ti:3000) && echo "killed"