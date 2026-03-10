# =============================================================================
# Gunicorn Configuration for Production
# =============================================================================
# Optimized for AWS t2.micro / t3.small instances
# =============================================================================

import multiprocessing
import os

# -----------------------------------------------------------------------------
# Server Socket
# -----------------------------------------------------------------------------
# IMPORTANT: Bind to 127.0.0.1 only - Nginx handles public traffic
# Port 8000 must NOT be publicly accessible
bind = "127.0.0.1:8000"
backlog = 2048

# -----------------------------------------------------------------------------
# Worker Processes
# -----------------------------------------------------------------------------
# For t2.micro (1 vCPU): 2 workers
# For t3.small (2 vCPU): 4 workers
# Formula: (2 x CPU cores) + 1, but limited for small instances
workers = int(os.getenv("GUNICORN_WORKERS", 4))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
threads = 1

# -----------------------------------------------------------------------------
# Timeouts
# -----------------------------------------------------------------------------
timeout = 120  # Worker timeout (seconds)
graceful_timeout = 30  # Graceful shutdown timeout
keepalive = 5  # Keep-alive connections timeout

# -----------------------------------------------------------------------------
# Process Naming
# -----------------------------------------------------------------------------
proc_name = "studybuddy-backend"

# -----------------------------------------------------------------------------
# Server Mechanics
# -----------------------------------------------------------------------------
daemon = False
pidfile = "/tmp/gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
errorlog = "-"  # stderr
accesslog = "-"  # stdout
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# -----------------------------------------------------------------------------
# Temp Directory
# -----------------------------------------------------------------------------
# Use application-specific temp directory, NOT /app (permission issues)
worker_tmp_dir = os.getenv("TEMP_DIR", "/home/ubuntu/studybuddy/backend/tmp")

# -----------------------------------------------------------------------------
# Hooks
# -----------------------------------------------------------------------------
def on_starting(server):
    """Called just before the master process is initialized."""
    pass

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    pass

def when_ready(server):
    """Called just after the server is started."""
    pass

def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    pass

def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    pass

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    pass

def nworkers_changed(server, new_value, old_value):
    """Called just after num_workers has been changed."""
    pass

def on_exit(server):
    """Called just before exiting Gunicorn."""
    pass

# -----------------------------------------------------------------------------
# Security
# -----------------------------------------------------------------------------
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
