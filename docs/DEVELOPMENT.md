# JobPilot Development Guide

## Environment Setup

```bash
# Prerequisites
# - Docker & Docker Compose
# - Python 3.11+
# - Node.js 20+
# - Git

# Clone and initialize
cp .env.example .env
make setup
make up
```

## Adding a New Microservice

1. Create directory: `backend/services/my_service/`
2. Required files per service:
   ```
   my_service/
   ├── __init__.py       # Empty
   ├── main.py           # FastAPI app + routes
   ├── models.py         # SQLAlchemy models
   ├── schemas.py        # Pydantic request/response
   ├── service.py        # Business logic
   ├── Dockerfile        # Multi-stage build
   ├── requirements.txt
   ├── alembic/          # DB migrations
   └── tests/
       ├── __init__.py
       ├── conftest.py   # Fixtures
       └── test_*.py     # Test modules
   ```
3. Register in `docker-compose.yml` via the `x-common-backend` anchor
4. Add Traefik labels for routing
5. Add healthcheck (`curl /health`)
6. Add CORS + exception handlers in `main.py`

## Code Style

### Python

```bash
pip install black isort ruff
black backend/
isort backend/
ruff check backend/
```

- PEP 8, 100 char line limit, snake_case
- Type hints on all function signatures
- One class per file where practical

### TypeScript

```bash
cd frontend
npx prettier --write "src/**/*.{ts,tsx,css}"
npx tsc --noEmit
```

- PascalCase components, camelCase functions
- Use `interface` for prop types

## Running Tests

```bash
# Per service
cd backend/services/user_service
TEST_DATABASE_URL=postgresql+asyncpg://... pytest tests/ -v

# Single test
pytest tests/test_auth.py::test_register_success -v

# With coverage
pytest tests/ --cov=. --cov-report=term
```

## Commit Convention

```
feat(service): description       # New feature
fix(service): description        # Bug fix
polish: description              # Code quality
docs: description                # Documentation
security: description            # Security fix
```

## Common Patterns

### Exception handling
```python
from common.exceptions import NotFoundError, ValidationError

if not user:
    raise NotFoundError("User not found")
```

### Retry
```python
from common.resilience import async_retry

@async_retry(max_retries=3, exceptions=(httpx.HTTPError,))
async def call_external_api():
    ...
```

### Business metrics
```python
from common.metrics import business_counter

business_counter("user_registrations_total")
```
