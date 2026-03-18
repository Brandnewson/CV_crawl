"""Database setup script for job pipeline."""

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv


def parse_db_url(db_url: str) -> dict:
    """Parse DATABASE_URL into components."""
    # Format: postgresql://user:pass@host:port/dbname or postgresql://host/dbname
    url = db_url.replace("postgresql://", "").replace("postgres://", "")

    # Check for user:pass@host format
    if "@" in url:
        creds, rest = url.split("@", 1)
        if ":" in creds:
            user, password = creds.split(":", 1)
        else:
            user, password = creds, ""
    else:
        user, password = "", ""
        rest = url

    # Parse host:port/dbname
    if "/" in rest:
        host_port, dbname = rest.rsplit("/", 1)
    else:
        host_port = rest
        dbname = "job_pipeline"

    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host = host_port
        port = "5432"

    return {
        "host": host or "localhost",
        "port": port,
        "dbname": dbname,
        "user": user or None,
        "password": password or None,
    }


def create_database_if_not_exists(db_url: str) -> bool:
    """
    Create the database if it doesn't exist.

    Returns True if database was created, False if it already existed.
    """
    params = parse_db_url(db_url)
    dbname = params.pop("dbname")

    try:
        conn = psycopg2.connect(dbname="postgres", **{k: v for k, v in params.items() if v})
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = cur.fetchone() is not None

            if not exists:
                cur.execute(f'CREATE DATABASE "{dbname}"')
                print(f"Created database: {dbname}")
                return True
            else:
                print(f"Database already exists: {dbname}")
                return False

    except psycopg2.Error as e:
        print(f"Error creating database: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()


def run_schema(db_url: str) -> list[str]:
    """
    Run the schema SQL file against the database.

    Returns list of tables created/verified.
    """
    schema_path = Path(__file__).parent / "schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    tables_created = []

    try:
        conn = psycopg2.connect(db_url)

        with conn.cursor() as cur:
            cur.execute(schema_sql)

            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)

            tables_created = [row[0] for row in cur.fetchall()]

        conn.commit()
        return tables_created

    except psycopg2.Error as e:
        print(f"Error running schema: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()


def main() -> None:
    """Main entry point for database setup."""
    print("=" * 60)
    print("Job Pipeline - Database Setup")
    print("=" * 60)

    # Load environment from CV_crawl root
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"\nWarning: .env file not found at {env_path}")
        print("Trying environment variables...")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("\nERROR: DATABASE_URL not found in environment")
        print("Create a .env file with DATABASE_URL=postgresql://localhost/job_pipeline")
        sys.exit(1)

    print(f"\nUsing database URL: {db_url}")

    # Create database if needed
    print("\nStep 1: Checking/creating database...")
    try:
        create_database_if_not_exists(db_url)
    except Exception as e:
        print(f"Could not create database automatically: {e}")
        print("Continuing to try schema setup anyway...")

    # Run schema
    print("\nStep 2: Running schema...")
    try:
        tables = run_schema(db_url)
        print(f"\nSchema applied successfully!")
        print(f"Tables verified: {', '.join(tables)}")
    except Exception as e:
        print(f"\nERROR: Failed to run schema: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Database setup complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
