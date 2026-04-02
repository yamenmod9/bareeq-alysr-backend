# WSGI configuration for PythonAnywhere
# Copy this content to your WSGI file at /var/www/yourusername_pythonanywhere_com_wsgi.py

import sys
import os

# Add your project directory to the sys.path
# Replace 'yourusername' with your actual PythonAnywhere username
project_home = '/home/yourusername/music-app-backend'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables (you can also set these in PythonAnywhere Web tab)
os.environ['SECRET_KEY'] = 'change-this-to-a-secure-secret-key'
os.environ['JWT_SECRET_KEY'] = 'change-this-to-a-secure-jwt-key'
os.environ['LASTFM_API_KEY'] = 'set-your-lastfm-api-key'

from app import app as application
