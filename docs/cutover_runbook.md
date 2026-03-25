# Backend To Flutter Cutover Runbook

## Scope
This runbook covers the remaining phases after Flask-first implementation:
- backend repository publish hygiene
- PythonAnywhere deployment steps
- Flutter release gates
- final cutover checklist

## Current Baseline
- Active runtime is Flask from app/flask_app.py
- Legacy FastAPI runtime is archived under app/legacy_fastapi/
- Local test suite passes with contract coverage for auth/customer/merchant/admin

## Phase 5: Publish Backend Repository

### Target
- Deployment source of truth: bareeq-alysr-backend main branch
- Repository contents must be backend-only runtime and deployment files

### Verification Checklist
1. Ensure backend root has run.py, wsgi.py, requirements.txt, pytest.ini, runtime.txt
2. Ensure no Flutter app folders are present (lib/, android/, ios/, etc.)
3. Ensure legacy FastAPI runtime is archived, not active

### Optional subtree split flow (from monorepo)
Use this only when extracting backend history from a larger repo:

```bash
git subtree split --prefix backend -b backend-split
git remote add backend-origin <backend-repo-url>
git push backend-origin backend-split:main --force
```

## Phase 6: PythonAnywhere Deployment

### Environment
1. Create virtual environment with Python 3.12
2. Install dependencies from requirements.txt
3. Set environment variables in PythonAnywhere web app settings

### WSGI
Use WSGI entrypoint:

```python
from wsgi import application
```

### Smoke Tests
After reload, verify:
1. GET /health returns success true and data.status healthy
2. POST /auth/login works with known test credentials
3. GET /auth/me works with bearer token from login

## Phase 7: Flutter Integration Order

### Gate 1
- login
- register
- token persistence

### Gate 2
- customer purchase request view
- customer accept/reject purchase request
- customer transaction payment flow

### Gate 3
- merchant customer lookup
- merchant send/create purchase request
- merchant transactions and settlements list

### Gate 4
- admin read-only dashboards and stats

## Phase 8: Release Gates Validation

Each gate must satisfy all criteria:
1. API contract tests remain green in backend
2. Flutter integration tests for the gate pass
3. Manual smoke test for the gate endpoints and screens pass
4. No schema contract break introduced for previous gates

## Phase 9: Final Cutover

1. Mark web frontend as archived in documentation
2. Keep backend repo main as deployment source of truth
3. Confirm startup docs reference only run.py and wsgi.py
4. Confirm mobile release notes map to backend endpoint contracts

## Rollback Strategy

If production issues appear after cutover:
1. Roll back PythonAnywhere app to previous known-good backend revision
2. Keep database backup snapshot before major rollout
3. Re-run health/auth/customer/merchant smoke checks before re-enabling traffic
