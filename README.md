# Bareeq Alysr Backend

Flask API backend for Bareeq Alysr.

## Runtime Architecture

- Active runtime: Flask (`app/flask_app.py`)
- Local entrypoint: `run.py`
- Deployment entrypoint: `wsgi.py`
- Legacy FastAPI code is archived under `app/legacy_fastapi/`

## Run locally

1. Create and activate a virtual environment.
2. Use Python 3.12 (recommended for deployment parity and dependency compatibility).
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables using .env.example.
5. Start the server:

```bash
python run.py
```

## Seed development accounts

Generate multiple customer and merchant accounts:

```bash
python seed.py --customers 20 --merchants 10 --password Seed@123
```

Notes:
- Customers are created with auto-generated unique `customer_code`.
- Merchants can look up customers using code via `GET /merchants/lookup-customer/<code>`.
- Customers can regenerate code via `POST /customers/me/regenerate-code`.

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

## Cutover and deployment runbook

- docs/cutover_runbook.md

## Test credentials (development only)

- customer@test.com / password123
- merchant@test.com / password123
