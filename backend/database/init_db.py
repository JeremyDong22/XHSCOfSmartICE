# Database initialization script
# Version 1.0 - Creates tables and migrates existing data
#
# Run this script to:
# 1. Create PostgreSQL database if it doesn't exist
# 2. Create all tables
# 3. Migrate existing accounts from account_config.json
# 4. Optionally import existing JSON scrape results
#
# Usage:
#   cd backend && uv run python -m database.init_db
#   cd backend && uv run python -m database.init_db --migrate-results

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import DatabaseConnection, init_database
from database.models import Base, Account, Post, ScrapeTask
from database.repositories import AccountRepository, PostRepository, ScrapeTaskRepository


# Database configuration
DATABASE_NAME = "xhs_scraper"
DATABASE_USER = os.getenv("POSTGRES_USER", "postgres")
DATABASE_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DATABASE_HOST = os.getenv("POSTGRES_HOST", "localhost")
DATABASE_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = f"postgresql+asyncpg://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"


async def create_database_if_not_exists():
    """
    Create the xhs_scraper database if it doesn't exist.
    Connects to the default 'postgres' database to execute CREATE DATABASE.
    """
    import asyncpg

    # Connect to default postgres database
    admin_url = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/postgres"

    try:
        conn = await asyncpg.connect(admin_url)

        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            DATABASE_NAME
        )

        if not exists:
            print(f"Creating database '{DATABASE_NAME}'...")
            await conn.execute(f'CREATE DATABASE "{DATABASE_NAME}"')
            print(f"Database '{DATABASE_NAME}' created successfully.")
        else:
            print(f"Database '{DATABASE_NAME}' already exists.")

        await conn.close()
        return True

    except Exception as e:
        print(f"Error creating database: {e}")
        print("\nMake sure PostgreSQL is running and accessible.")
        print(f"Connection details: {DATABASE_HOST}:{DATABASE_PORT} as {DATABASE_USER}")
        return False


async def create_tables(db: DatabaseConnection):
    """Create all database tables"""
    print("Creating database tables...")
    await db.create_tables()
    print("Tables created successfully.")


async def migrate_accounts_from_config(db: DatabaseConnection):
    """
    Migrate existing accounts from account_config.json to database.
    Preserves account_id and active status.
    """
    config_path = Path(__file__).parent.parent.parent / "account_config.json"

    if not config_path.exists():
        print("No account_config.json found, skipping account migration.")
        return 0

    print(f"Migrating accounts from {config_path}...")

    with open(config_path, "r") as f:
        config = json.load(f)

    accounts = config.get("accounts", {})
    migrated_count = 0

    async with db.session() as session:
        repo = AccountRepository(session)

        for account_id_str, account_data in accounts.items():
            account_id = int(account_id_str)

            # Check if already exists
            existing = await repo.get_by_account_id(account_id)
            if existing:
                print(f"  Account {account_id} already exists, skipping.")
                continue

            # Create account
            is_active = account_data.get("active", True)
            nickname = account_data.get("nickname")
            last_used = account_data.get("last_used")

            account = await repo.create(
                account_id=account_id,
                nickname=nickname,
                is_active=is_active,
            )

            if last_used:
                try:
                    account.last_used_at = datetime.fromisoformat(last_used)
                except ValueError:
                    pass

            migrated_count += 1
            print(f"  Migrated account {account_id} (active={is_active})")

    print(f"Migrated {migrated_count} accounts.")
    return migrated_count


async def migrate_scrape_results(db: DatabaseConnection):
    """
    Import existing JSON scrape results into the database.
    Reads from output/ folder and creates Post records.
    """
    output_path = Path(__file__).parent.parent.parent / "output"

    if not output_path.exists():
        print("No output folder found, skipping results migration.")
        return 0

    json_files = list(output_path.glob("*.json"))
    if not json_files:
        print("No JSON result files found, skipping results migration.")
        return 0

    print(f"Migrating {len(json_files)} scrape result files...")
    total_posts = 0
    new_posts = 0

    async with db.session() as session:
        post_repo = PostRepository(session)

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                keyword = data.get("keyword", "")
                account_id = data.get("account_id")
                scraped_at_str = data.get("scraped_at")
                posts = data.get("posts", [])

                if not posts:
                    continue

                scraped_at = None
                if scraped_at_str:
                    try:
                        scraped_at = datetime.fromisoformat(scraped_at_str)
                    except ValueError:
                        scraped_at = datetime.utcnow()

                for post_data in posts:
                    note_id = post_data.get("note_id")
                    if not note_id:
                        continue

                    # Check if post already exists
                    existing = await post_repo.get_by_note_id(note_id)
                    total_posts += 1

                    if existing:
                        # Update last_seen
                        existing.last_seen_at = datetime.utcnow()
                        existing.times_seen += 1
                        continue

                    # Create new post
                    await post_repo.upsert(
                        note_id=note_id,
                        account_id=account_id,
                        title=post_data.get("title"),
                        permanent_url=post_data.get("permanent_url"),
                        tokenized_url=post_data.get("tokenized_url"),
                        author_name=post_data.get("author"),
                        author_avatar_url=post_data.get("author_avatar"),
                        author_profile_url=post_data.get("author_profile_url"),
                        likes=post_data.get("likes", 0),
                        cover_image_url=post_data.get("cover_image"),
                        is_video=post_data.get("is_video", False),
                        card_width=post_data.get("card_width"),
                        card_height=post_data.get("card_height"),
                        publish_date=post_data.get("publish_date"),
                        scraped_at=scraped_at,
                        keyword=keyword,
                    )
                    new_posts += 1

                print(f"  Processed {json_file.name}: {len(posts)} posts")

            except Exception as e:
                print(f"  Error processing {json_file.name}: {e}")

    print(f"Migration complete: {new_posts} new posts imported, {total_posts - new_posts} duplicates skipped.")
    return new_posts


async def main():
    """Main initialization function"""
    parser = argparse.ArgumentParser(description="Initialize XHS Scraper Database")
    parser.add_argument(
        "--migrate-results",
        action="store_true",
        help="Also migrate existing JSON scrape results to database",
    )
    parser.add_argument(
        "--drop-tables",
        action="store_true",
        help="Drop all tables before creating (WARNING: destroys data!)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("XHS Scraper Database Initialization")
    print("=" * 60)
    print(f"Database: {DATABASE_NAME}")
    print(f"Host: {DATABASE_HOST}:{DATABASE_PORT}")
    print(f"User: {DATABASE_USER}")
    print("=" * 60)

    # Step 1: Create database if needed
    if not await create_database_if_not_exists():
        print("\nFailed to create database. Exiting.")
        return 1

    # Step 2: Initialize connection
    print("\nConnecting to database...")
    db = DatabaseConnection(DATABASE_URL)

    try:
        # Optional: Drop tables first
        if args.drop_tables:
            print("\nWARNING: Dropping all tables...")
            await db.drop_tables()
            print("Tables dropped.")

        # Step 3: Create tables
        await create_tables(db)

        # Step 4: Migrate accounts
        print("\n" + "-" * 40)
        await migrate_accounts_from_config(db)

        # Step 5: Optionally migrate scrape results
        if args.migrate_results:
            print("\n" + "-" * 40)
            await migrate_scrape_results(db)

        print("\n" + "=" * 60)
        print("Database initialization complete!")
        print("=" * 60)

        # Print summary
        async with db.session() as session:
            account_repo = AccountRepository(session)
            post_repo = PostRepository(session)

            accounts = await account_repo.get_all()
            post_count = await post_repo.get_total_count()

            print(f"\nDatabase Summary:")
            print(f"  Accounts: {len(accounts)}")
            print(f"  Posts: {post_count}")

    finally:
        await db.close()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
