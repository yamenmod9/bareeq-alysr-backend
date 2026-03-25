"""Bareeq Al-Yusr Flask application runner."""
import os
import sys

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.flask_app import flask_app, init_database


def run_server():
    """Run the Flask server."""
    init_database(flask_app)

    print("""
    =========================================
      Bareeq Al-Yusr - Flask API Server
    =========================================
    API Server: http://localhost:8000
    Health:     http://localhost:8000/health
    Test Data:  http://localhost:8000/admin/create-test-data
    """)

    flask_app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )


if __name__ == "__main__":
    run_server()
