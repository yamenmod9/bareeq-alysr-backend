"""
WSGI configuration for PythonAnywhere deployment
This file serves the Flask application with API routes
"""
import os
import sys

# Add project directory to path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables with ABSOLUTE path for SQLite
db_path = os.path.join(project_home, 'instance', 'bareeq_alysr.db')
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

# Ensure instance directory exists
instance_dir = os.path.join(project_home, 'instance')
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

from app.flask_app import flask_app, init_database

# Initialize database
init_database(flask_app)

# Use Flask app (with API routes registered via flask_routes.py)
application = flask_app
print("✅ Flask application ready with API routes")
