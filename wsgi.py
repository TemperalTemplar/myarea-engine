"""WSGI entry point for Gunicorn."""
import eventlet
eventlet.monkey_patch()

from app import create_app, socketio
import os

app = create_app(os.getenv("FLASK_ENV", "production"))

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
