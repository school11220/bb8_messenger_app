#!/bin/bash
# Startup script for BB84 Chat
cd "$(dirname "$0")"
unset DATABASE_URL
unset RAILWAY_DATABASE_URL
unset POSTGRES_URL
unset POSTGRESQL_URL
unset PG_URI
unset DB_URL

if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi

"$PYTHON" app.py
