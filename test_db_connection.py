#!/usr/bin/env python3
"""
Database connection tester.

This file is intentionally safe to import so pytest collection does not try to
connect to a deployment-only database. Run it directly to test the configured DB:

    python test_db_connection.py
"""

import os
import sys

from sqlalchemy.engine import make_url

__test__ = False


def find_database_url():
    for key in (
        "DATABASE_URL",
        "RAILWAY_DATABASE_URL",
        "POSTGRES_URL",
        "POSTGRESQL_URL",
        "PG_URI",
        "SQLALCHEMY_DATABASE_URI",
        "DB_URL",
    ):
        value = os.environ.get(key)
        if value and value.strip():
            return key, value.strip()
    return "local sqlite fallback", "sqlite:///chat.db"


def normalize_database_url(database_url):
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def main():
    env_name, database_url = find_database_url()
    database_url = normalize_database_url(database_url)
    parsed = make_url(database_url)

    print("Testing database connection...")
    print(f"Source: {env_name}")
    print(f"Database: {parsed.database or '(default)'}")
    print(f"Host: {parsed.host or '(local file)'}")
    print()

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(database_url)
        with engine.connect() as connection:
            if parsed.drivername.startswith("sqlite"):
                result = connection.execute(text("SELECT sqlite_version()"))
                version = f"SQLite {result.fetchone()[0]}"
            else:
                result = connection.execute(text("SELECT version()"))
                version = result.fetchone()[0]

            print("Connection successful.")
            print(f"Database version: {version[:80]}")

            if not parsed.drivername.startswith("sqlite"):
                result = connection.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        ORDER BY table_name
                        """
                    )
                )
                tables = [row[0] for row in result]
                print(f"Existing tables: {', '.join(tables) if tables else 'none'}")

        return 0
    except ImportError:
        print("SQLAlchemy is not installed.")
        print("Run: pip install -r requirements.txt")
        return 1
    except Exception as exc:
        print(f"Connection failed: {exc}")
        print()
        print("For Render internal database URLs, run this inside Render or use an external URL locally.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
