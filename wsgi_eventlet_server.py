import os
import eventlet
eventlet.monkey_patch()

from app import app

def main():
    port = int(os.environ.get('PORT', 5000))
    listener = eventlet.listen(('0.0.0.0', port))
    print(f"[eventlet-server] Starting eventlet WSGI server on 0.0.0.0:{port}")
    try:
        eventlet.wsgi.server(listener, app)
    except Exception as e:
        print(f"[eventlet-server] Server exited with: {e}")

if __name__ == '__main__':
    main()
