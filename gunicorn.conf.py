"""
Gunicorn configuration for Bracketeer production deployment.

This configuration optimizes Gunicorn for combat robotics tournament management,
balancing performance with real-time WebSocket requirements.
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:80"
backlog = 2048

# Worker processes
workers = 1  # SocketIO requires single worker for WebSocket coordination
worker_class = "eventlet"  # Required for Flask-SocketIO
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeout settings
timeout = 30
keepalive = 2

# Process naming
proc_name = 'bracketeer'

# Logging
accesslog = 'logs/access.log'
errorlog = 'logs/error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process management
pidfile = 'bracketeer.pid'
user = None  # Set to your app user in production
group = None  # Set to your app group in production

# SSL (configure if using HTTPS)
# keyfile = "/path/to/private.key"
# certfile = "/path/to/certificate.crt"

# Development vs Production
def when_ready(server):
    """Called when the server is started."""
    server.log.info("Bracketeer server is ready. Listening on %s", bind)

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

# Production optimizations
preload_app = True  # Load application before forking workers
enable_stdio_inheritance = True

# Environment-specific settings
if os.getenv('BRACKETEER_ENV') == 'development':
    bind = "127.0.0.1:8000"
    reload = True
    loglevel = 'debug'
    accesslog = '-'  # Log to stdout
    errorlog = '-'   # Log to stderr
elif os.getenv('BRACKETEER_ENV') == 'production':
    workers = 1  # Still single worker for SocketIO
    worker_class = "eventlet"
    timeout = 60
    max_requests = 5000
    # Enable detailed logging in production
    capture_output = True
    enable_stdio_inheritance = True