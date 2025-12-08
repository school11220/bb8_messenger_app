#!/bin/bash
# Startup script for BB84 Chat
cd "$(dirname "$0")"
unset DATABASE_URL
unset RAILWAY_DATABASE_URL
unset POSTGRES_URL
unset POSTGRESQL_URL
unset PG_URI
unset DB_URL
source venv/bin/activate
python app.py
