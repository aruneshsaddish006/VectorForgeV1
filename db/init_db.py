from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")


REQUIRED_ENV = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


def get_connection_kwargs() -> dict[str, str | int]:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing required database environment variables: {joined}")

    return {
      "host": os.environ["DB_HOST"],
      "port": int(os.environ["DB_PORT"]),
      "dbname": os.environ["DB_NAME"],
      "user": os.environ["DB_USER"],
      "password": os.environ["DB_PASSWORD"],
      "sslmode": os.getenv("DB_SSLMODE", "require"),
    }


def main() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    with psycopg.connect(**get_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)

    print("Database schema initialized successfully.")


if __name__ == "__main__":
    main()
