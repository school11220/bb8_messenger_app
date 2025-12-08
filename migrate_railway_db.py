#!/usr/bin/env python3
"""
Migration script to add missing columns to Railway PostgreSQL database.
Run this script after deploying to Railway to update the database schema.

Usage:
    python migrate_railway_db.py
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from datetime import datetime

def get_database_url():
    """Get database URL from environment variables."""
    candidates = [
        'DATABASE_URL',
        'RAILWAY_DATABASE_URL', 
        'PG_URI',
        'SQLALCHEMY_DATABASE_URI',
        'DB_URL'
    ]
    for key in candidates:
        val = os.environ.get(key)
        if val and val.strip():
            print(f"[migrate] Found DB env var: {key}")
            # Normalize postgres:// to postgresql://
            if val.startswith('postgres://'):
                val = val.replace('postgres://', 'postgresql://', 1)
            return val
    return None

def column_exists(inspector, table_name, column_name):
    """Check if a column exists in a table."""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def table_exists(inspector, table_name):
    """Check if a table exists."""
    return table_name in inspector.get_table_names()

def migrate_database():
    """Add missing columns to the database."""
    database_url = get_database_url()
    
    if not database_url:
        print("[migrate] ERROR: No database URL found in environment variables")
        sys.exit(1)
    
    print(f"[migrate] Connecting to database...")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        print("[migrate] Connected successfully")
        
        # ==================== USER TABLE ====================
        if table_exists(inspector, 'user'):
            print("\n[migrate] Checking 'user' table...")
            
            migrations = [
                ('status', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'online'"),
                ('status_message', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS status_message VARCHAR(200)"),
                ('last_seen', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT NOW()"),
                ('avatar_url', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"),
                ('show_last_seen', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS show_last_seen BOOLEAN DEFAULT TRUE"),
                ('show_read_receipts', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS show_read_receipts BOOLEAN DEFAULT TRUE"),
                ('allow_messages_from', "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS allow_messages_from VARCHAR(20) DEFAULT 'everyone'"),
            ]
            
            for col_name, sql in migrations:
                if not column_exists(inspector, 'user', col_name):
                    print(f"  [+] Adding column: {col_name}")
                    conn.execute(text(sql))
                    conn.commit()
                else:
                    print(f"  [✓] Column exists: {col_name}")
        else:
            print("\n[migrate] WARNING: 'user' table does not exist. Creating tables...")
            from app import db, User
            db.create_all()
            print("  [+] All tables created")
        
        # ==================== MESSAGE TABLE ====================
        if table_exists(inspector, 'message'):
            print("\n[migrate] Checking 'message' table...")
            
            migrations = [
                ('status', "ALTER TABLE message ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'sent'"),
                ('edited', "ALTER TABLE message ADD COLUMN IF NOT EXISTS edited BOOLEAN DEFAULT FALSE"),
                ('message_type', "ALTER TABLE message ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) DEFAULT 'text'"),
                ('file_url', "ALTER TABLE message ADD COLUMN IF NOT EXISTS file_url VARCHAR(500)"),
                ('file_name', "ALTER TABLE message ADD COLUMN IF NOT EXISTS file_name VARCHAR(255)"),
                ('reply_to_id', "ALTER TABLE message ADD COLUMN IF NOT EXISTS reply_to_id INTEGER REFERENCES message(id)"),
                ('pinned', "ALTER TABLE message ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE"),
                ('starred', "ALTER TABLE message ADD COLUMN IF NOT EXISTS starred BOOLEAN DEFAULT FALSE"),
                ('deleted', "ALTER TABLE message ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE"),
                ('deleted_for', "ALTER TABLE message ADD COLUMN IF NOT EXISTS deleted_for VARCHAR(500)"),
            ]
            
            for col_name, sql in migrations:
                if not column_exists(inspector, 'message', col_name):
                    print(f"  [+] Adding column: {col_name}")
                    conn.execute(text(sql))
                    conn.commit()
                else:
                    print(f"  [✓] Column exists: {col_name}")
        
        # ==================== MESSAGE_REACTION TABLE ====================
        if not table_exists(inspector, 'message_reaction'):
            print("\n[migrate] Creating 'message_reaction' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS message_reaction (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER NOT NULL REFERENCES message(id) ON DELETE CASCADE,
                    username VARCHAR(100) NOT NULL,
                    reaction VARCHAR(10) NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()
            print("  [+] Table created")
        else:
            print("\n[migrate] [✓] 'message_reaction' table exists")
        
        # ==================== GROUP TABLE ====================
        if not table_exists(inspector, 'group'):
            print("\n[migrate] Creating 'group' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "group" (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    created_by VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    avatar_url VARCHAR(500)
                )
            """))
            conn.commit()
            print("  [+] Table created")
        else:
            print("\n[migrate] [✓] 'group' table exists")
        
        # ==================== GROUP_ADMIN TABLE ====================
        if not table_exists(inspector, 'group_admin'):
            print("\n[migrate] Creating 'group_admin' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS group_admin (
                    id SERIAL PRIMARY KEY,
                    group_name VARCHAR(100) NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    role VARCHAR(50) DEFAULT 'member',
                    can_add_members BOOLEAN DEFAULT FALSE,
                    can_remove_members BOOLEAN DEFAULT FALSE,
                    can_edit_info BOOLEAN DEFAULT FALSE,
                    can_send_messages BOOLEAN DEFAULT TRUE,
                    joined_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(group_name, username)
                )
            """))
            conn.commit()
            print("  [+] Table created")
        else:
            print("\n[migrate] Checking 'group_admin' table...")
            migrations = [
                ('role', "ALTER TABLE group_admin ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'member'"),
                ('can_add_members', "ALTER TABLE group_admin ADD COLUMN IF NOT EXISTS can_add_members BOOLEAN DEFAULT FALSE"),
                ('can_remove_members', "ALTER TABLE group_admin ADD COLUMN IF NOT EXISTS can_remove_members BOOLEAN DEFAULT FALSE"),
                ('can_edit_info', "ALTER TABLE group_admin ADD COLUMN IF NOT EXISTS can_edit_info BOOLEAN DEFAULT FALSE"),
                ('can_send_messages', "ALTER TABLE group_admin ADD COLUMN IF NOT EXISTS can_send_messages BOOLEAN DEFAULT TRUE"),
                ('joined_at', "ALTER TABLE group_admin ADD COLUMN IF NOT EXISTS joined_at TIMESTAMP DEFAULT NOW()"),
            ]
            
            for col_name, sql in migrations:
                if not column_exists(inspector, 'group_admin', col_name):
                    print(f"  [+] Adding column: {col_name}")
                    conn.execute(text(sql))
                    conn.commit()
                else:
                    print(f"  [✓] Column exists: {col_name}")
        
        # ==================== DEVICE_SESSION TABLE ====================
        if not table_exists(inspector, 'device_session'):
            print("\n[migrate] Creating 'device_session' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS device_session (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) NOT NULL,
                    device_name VARCHAR(100) NOT NULL,
                    device_token VARCHAR(200) UNIQUE NOT NULL,
                    paired_at TIMESTAMP DEFAULT NOW(),
                    last_active TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()
            print("  [+] Table created")
        else:
            print("\n[migrate] [✓] 'device_session' table exists")
        
        # ==================== GROUP_INVITATION TABLE ====================
        if not table_exists(inspector, 'group_invitation'):
            print("\n[migrate] Creating 'group_invitation' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS group_invitation (
                    id SERIAL PRIMARY KEY,
                    group_name VARCHAR(100) NOT NULL,
                    token VARCHAR(200) UNIQUE NOT NULL,
                    created_by VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0
                )
            """))
            conn.commit()
            print("  [+] Table created")
        else:
            print("\n[migrate] [✓] 'group_invitation' table exists")
        
        # ==================== CALL TABLE ====================
        if not table_exists(inspector, 'call'):
            print("\n[migrate] Creating 'call' table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS call (
                    id SERIAL PRIMARY KEY,
                    caller VARCHAR(100) NOT NULL,
                    callee VARCHAR(100) NOT NULL,
                    call_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) DEFAULT 'initiated',
                    started_at TIMESTAMP DEFAULT NOW(),
                    ended_at TIMESTAMP,
                    duration INTEGER DEFAULT 0
                )
            """))
            conn.commit()
            print("  [+] Table created")
        else:
            print("\n[migrate] [✓] 'call' table exists")
        
        print("\n[migrate] ✅ Migration completed successfully!")
        print("[migrate] All tables and columns are up to date.")

if __name__ == '__main__':
    print("=" * 60)
    print("BB8 Messenger - Railway Database Migration")
    print("=" * 60)
    try:
        migrate_database()
    except Exception as e:
        print(f"\n[migrate] ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
