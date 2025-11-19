#!/bin/bash
# Start the BB84 Chat application
# Make sure to update the DATABASE_URL in .env file with your External Database URL from Render

cd "/home/shivam/Downloads/BB84 messenger"

# Initialize database tables
echo "Initializing database..."
.venv/bin/python init_db.py

echo ""
echo "Starting server on http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

# Start the server
.venv/bin/python app.py
