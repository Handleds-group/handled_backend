import argparse

from app.database import engine, init_db
from app.models import Base
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError


def reset_database(clear_redis: bool = False) -> None:
    try:
        Base.metadata.drop_all(bind=engine)
        init_db()
    except OperationalError as exc:
        url = make_url(str(engine.url))
        host = url.host or "unknown-host"
        port = url.port or "unknown-port"
        database = url.database or "unknown-database"
        print("Database reset failed.")
        print(f"Could not connect to Postgres at {host}:{port} (database: {database}).")
        print("This is a connectivity problem, not a reset script problem.")
        print("Check that:")
        print("1. your internet connection is working")
        print("2. the hosted database is up")
        print("3. DATABASE_URL in .env is correct")
        print("4. your DB provider allows connections from your current network/IP")
        print("5. no firewall or VPN is blocking the connection")
        print("")
        print(f"Original error: {exc}")
        return

    if clear_redis:
        from app.redis_client import redis_client

        redis_client.flushdb()
        print("Redis cleared.")

    print("Database reset complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drop all database tables and recreate them from the current SQLAlchemy models."
    )
    parser.add_argument(
        "--with-redis",
        action="store_true",
        help="Also clear the configured Redis database.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    args = parser.parse_args()

    if not args.yes:
        confirmation = input(
            "This will permanently delete all database data. Type RESET to continue: "
        ).strip()
        if confirmation != "RESET":
            print("Reset cancelled.")
            return

    reset_database(clear_redis=args.with_redis)


if __name__ == "__main__":
    main()
