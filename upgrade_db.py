#!/usr/bin/env python3
"""
Initialize or upgrade the database schema with all new columns
"""
import os
import sys
from sqlalchemy import text

# Add the parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def upgrade_database():
    """Add new columns to existing tables"""
    with app.app_context():
        try:
            # Check if we're using PostgreSQL or SQLite
            engine_name = db.engine.name
            print(f"Database engine: {engine_name}")
            
            # Get existing columns for User table
            if engine_name == 'postgresql':
                user_cols = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='user';")).fetchall()
                msg_cols = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='message';")).fetchall()
                user_existing = {r[0] for r in user_cols}
                msg_existing = {r[0] for r in msg_cols}
                
                # User table new columns
                user_new_cols = {
                    'status': "VARCHAR(50) DEFAULT 'online'",
                    'status_message': "VARCHAR(200)",
                    'last_seen': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    'avatar_url': "VARCHAR(500)",
                    'show_last_seen': "BOOLEAN DEFAULT TRUE",
                    'show_read_receipts': "BOOLEAN DEFAULT TRUE",
                    'allow_messages_from': "VARCHAR(20) DEFAULT 'everyone'"
                }
                
                for col, definition in user_new_cols.items():
                    if col not in user_existing:
                        try:
                            db.session.execute(text(f"ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS {col} {definition};"))
                            print(f"✓ Added column 'user.{col}'")
                        except Exception as e:
                            print(f"✗ Error adding user.{col}: {e}")
                
                # Message table new columns
                msg_new_cols = {
                    'message_type': "VARCHAR(20) DEFAULT 'text'",
                    'file_url': "VARCHAR(500)",
                    'file_name': "VARCHAR(255)",
                    'reply_to_id': "INTEGER",
                    'pinned': "BOOLEAN DEFAULT FALSE",
                    'starred': "BOOLEAN DEFAULT FALSE"
                }
                
                for col, definition in msg_new_cols.items():
                    if col not in msg_existing:
                        try:
                            db.session.execute(text(f"ALTER TABLE message ADD COLUMN IF NOT EXISTS {col} {definition};"))
                            print(f"✓ Added column 'message.{col}'")
                        except Exception as e:
                            print(f"✗ Error adding message.{col}: {e}")
                            
                # Change encrypted_message to TEXT for larger files
                try:
                    db.session.execute(text("ALTER TABLE message ALTER COLUMN encrypted_message TYPE TEXT;"))
                    print(f"✓ Changed message.encrypted_message to TEXT")
                except Exception as e:
                    print(f"Note: encrypted_message type change: {e}")
                
            else:  # SQLite
                user_cols = db.session.execute(text("PRAGMA table_info('user');")).fetchall()
                msg_cols = db.session.execute(text("PRAGMA table_info('message');")).fetchall()
                user_existing = {r[1] for r in user_cols}
                msg_existing = {r[1] for r in msg_cols}
                
                # User table new columns
                user_new_cols = {
                    'status': "VARCHAR(50) DEFAULT 'online'",
                    'status_message': "VARCHAR(200)",
                    'last_seen': "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    'avatar_url': "VARCHAR(500)",
                    'show_last_seen': "BOOLEAN DEFAULT 1",
                    'show_read_receipts': "BOOLEAN DEFAULT 1",
                    'allow_messages_from': "VARCHAR(20) DEFAULT 'everyone'"
                }
                
                for col, definition in user_new_cols.items():
                    if col not in user_existing:
                        try:
                            db.session.execute(text(f"ALTER TABLE user ADD COLUMN {col} {definition};"))
                            print(f"✓ Added column 'user.{col}'")
                        except Exception as e:
                            print(f"✗ Error adding user.{col}: {e}")
                
                # Message table new columns
                msg_new_cols = {
                    'message_type': "VARCHAR(20) DEFAULT 'text'",
                    'file_url': "VARCHAR(500)",
                    'file_name': "VARCHAR(255)",
                    'reply_to_id': "INTEGER",
                    'pinned': "BOOLEAN DEFAULT 0",
                    'starred': "BOOLEAN DEFAULT 0"
                }
                
                for col, definition in msg_new_cols.items():
                    if col not in msg_existing:
                        try:
                            db.session.execute(text(f"ALTER TABLE message ADD COLUMN {col} {definition};"))
                            print(f"✓ Added column 'message.{col}'")
                        except Exception as e:
                            print(f"✗ Error adding message.{col}: {e}")
            
            db.session.commit()
            print("\n✓ Database upgrade completed successfully!")
            
            # Create MessageReaction table if it doesn't exist
            try:
                db.create_all()
                print("✓ Created MessageReaction table")
            except Exception as e:
                print(f"MessageReaction table: {e}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Database upgrade failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("BB84 Chat - Database Upgrade Script")
    print("=" * 60)
    upgrade_database()
    print("=" * 60)
