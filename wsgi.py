import eventlet
# Ensure eventlet monkey-patching happens as early as possible (before importing
# any other modules that may create thread locks). Gunicorn will import this
# module when using `wsgi:app` in the Procfile, so this guarantees the patch
# runs before app code is loaded in worker processes.
eventlet.monkey_patch()

# Import the Flask app object so gunicorn can serve it. Import after the
# monkey_patch call above to avoid "RLock(s) were not greened" warnings.
from app import app

# Expose 'app' for gunicorn (wsgi:app)
