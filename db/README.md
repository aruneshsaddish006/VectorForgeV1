# Forge AI Database

Database schema and initializer for the Forge AI application.

## Files

- `schema.sql` creates the application tables, indexes, triggers, and migration records.
- `init_db.py` loads `backend/.env`, reads `schema.sql`, and applies it to Postgres.

## Initialize schema

```bash
cd db
uv run --project ../backend python init_db.py
```
