#!/usr/bin/env python3
"""Database migration script to add new columns"""
import os
import sys
from sqlalchemy import create_engine, text

# Get database path
basedir = os.path.abspath(os.path.dirname(__file__))
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL or not DATABASE_URL.strip():
    # Use SQLite for local development
    DATABASE_PATH = os.path.join(basedir, 'chat.db')
    DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

print(f"Migrating database: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)

def run_migrations():
    with engine.connect() as conn:
        # Add deleted column to message table
        try:
            conn.execute(text("ALTER TABLE message ADD COLUMN deleted BOOLEAN DEFAULT 0"))
            conn.commit()
            print("✓ Added 'deleted' column to message table")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("• 'deleted' column already exists")
            else:
                print(f"✗ Error adding 'deleted' column: {e}")
        
        # Add deleted_for column to message table
        try:
            conn.execute(text("ALTER TABLE message ADD COLUMN deleted_for VARCHAR(500)"))
            conn.commit()
            print("✓ Added 'deleted_for' column to message table")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("• 'deleted_for' column already exists")
            else:
                print(f"✗ Error adding 'deleted_for' column: {e}")

if __name__ == "__main__":
    print("Starting database migration...")
    try:
        run_migrations()
        print("\n✓ Migration completed successfully!")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)
