#!/usr/bin/env python3
"""
Wrapper to monkey-patch eventlet before exec'ing gunicorn.
Use this as the Procfile start command to ensure greening happens in the worker
processes and avoid the "RLock(s) were not greened" warning.
"""
import os
import sys
import eventlet

def main():
    # Patch standard library for eventlet
    eventlet.monkey_patch()

    # Build gunicorn command
    workers = os.environ.get('WEB_CONCURRENCY', '1')
    gunicorn_cmd = [
        'gunicorn',
        '--worker-class', 'eventlet',
        '-w', str(workers),
        'wsgi:app'
    ]

    # Allow overriding the command via GUNICORN_CMD env var
    override = os.environ.get('GUNICORN_CMD')
    if override:
        gunicorn_cmd = override.split()

    # Exec gunicorn (replaces this process)
    os.execvp(gunicorn_cmd[0], gunicorn_cmd)

if __name__ == '__main__':
    main()
