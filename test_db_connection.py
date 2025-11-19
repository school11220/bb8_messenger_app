#!/usr/bin/env python3
"""
Quick database connection tester for Render PostgreSQL
Run this locally to verify your database credentials work
"""

import os
import sys

# Your Render database URL
DATABASE_URL = "postgresql://bb84_chat_db_user:ANJp2szOmn3balbo0ndvwa51CbMA5vna@dpg-d4erovuuk2gs739nq80g-a/bb84_chat_db"

print("🔍 Testing Render PostgreSQL Connection...")
print(f"📡 Database: {DATABASE_URL.split('@')[1].split('/')[1]}")
print(f"🌐 Host: {DATABASE_URL.split('@')[1].split('/')[0]}")
print()

try:
    from sqlalchemy import create_engine, text
    
    # Convert postgres:// to postgresql:// if needed
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Test connection
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print("✅ Connection Successful!")
        print(f"📊 PostgreSQL Version: {version[:50]}...")
        print()
        
        # Check if tables exist
        result = connection.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        tables = [row[0] for row in result]
        
        if tables:
            print(f"📋 Existing Tables: {', '.join(tables)}")
        else:
            print("📋 No tables found (will be created on first app run)")
        
        print()
        print("🎉 Database is ready to use!")
        print()
        print("Next steps:")
        print("1. Push your code to GitHub")
        print("2. Deploy on Render")
        print("3. Add DATABASE_URL environment variable in Render dashboard")
        
except ImportError:
    print("❌ SQLAlchemy not installed")
    print("Run: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Connection Failed: {str(e)}")
    print()
    print("Common issues:")
    print("1. Check if database URL is correct")
    print("2. Verify database is running in Render dashboard")
    print("3. Make sure you're using Internal Database URL, not External")
    sys.exit(1)
