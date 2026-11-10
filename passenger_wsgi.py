import os
import sys

# Ensure project root is in Python's import search path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from a2wsgi import ASGIMiddleware
from app.main import app

# cPanel CloudLinux Passenger looks for a WSGI callable named "application"
application = ASGIMiddleware(app)
