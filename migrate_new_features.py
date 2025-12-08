#!/usr/bin/env python3
"""
Migration script for new features: Group Management, Multi-Device Sync, Enhanced Typing
"""

import os
import sys
from sqlalchemy import create_engine, text

# Determine database URL
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

if not DATABASE_URL:
    DATABASE_URL = 'sqlite:///chat.db'

print(f"Using database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

engine = create_engine(DATABASE_URL)

def run_migration():
    """Run all migration steps"""
    with engine.connect() as conn:
        # Create group_admin table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS group_admin (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role VARCHAR(20) DEFAULT 'admin',
                    can_add_members BOOLEAN DEFAULT 1,
                    can_remove_members BOOLEAN DEFAULT 1,
                    can_edit_group BOOLEAN DEFAULT 1,
                    can_send_messages BOOLEAN DEFAULT 1,
                    appointed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES "group" (id),
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            """))
            conn.commit()
            print("✓ Created group_admin table")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"✗ Error creating group_admin table: {e}")
        
        # Create device_session table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS device_session (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    device_token VARCHAR(255) UNIQUE NOT NULL,
                    device_name VARCHAR(100),
                    device_type VARCHAR(50),
                    ip_address VARCHAR(50),
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            """))
            conn.commit()
            print("✓ Created device_session table")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"✗ Error creating device_session table: {e}")
        
        # Create group_invitation table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS group_invitation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    invited_by INTEGER NOT NULL,
                    invited_user VARCHAR(100) NOT NULL,
                    invite_token VARCHAR(100) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES "group" (id),
                    FOREIGN KEY (invited_by) REFERENCES user (id)
                )
            """))
            conn.commit()
            print("✓ Created group_invitation table")
        except Exception as e:
            if "already exists" not in str(e).lower():
                print(f"✗ Error creating group_invitation table: {e}")
        
        # Add created_at to group table if missing
        try:
            conn.execute(text("""
                ALTER TABLE "group" ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            conn.commit()
            print("✓ Added created_at column to group table")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"Note: created_at column might already exist in group table")

if __name__ == "__main__":
    print("Starting migration for new features...")
    run_migration()
    print("\nMigration complete!")
