#!/bin/bash
# Start the BB84 Chat application
# Make sure to update the DATABASE_URL in .env file with your External Database URL from Render

cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi

# Initialize database tables
echo "Initializing database..."
"$PYTHON" init_db.py

echo ""
echo "Starting server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

# Start the server
"$PYTHON" app.py
