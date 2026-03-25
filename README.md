# Bareeq Alysr Backend

Flask API backend for Bareeq Alysr.

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables using .env.example.
4. Start the server:

```bash
python run.py
```

## PythonAnywhere deployment

1. Clone repository on PythonAnywhere.
2. Create a virtualenv and install dependencies:

```bash
mkvirtualenv bareeq-alysr-env --python=python3.12
pip install -r /home/<username>/bareeq-alysr-backend/requirements.txt
```

3. Set environment variables in Web app settings.
4. In the WSGI file on PythonAnywhere, point to:

```python
from wsgi import application
```

5. Reload the web app.

## Health check

- GET /health

## Test credentials (development only)

- customer@test.com / password123
- merchant@test.com / password123
