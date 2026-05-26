# Contributing to JobPilot

## Local Development Setup

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- Git

### Quick Start

```bash
# 1. Clone and set up
cp .env.example .env
make setup

# 2. Start infrastructure services
docker-compose up -d postgres redis elasticsearch

# 3. Install backend deps
cd backend && pip install -e .

# 4. Install frontend deps
cd frontend && npm install

# 5. Start the full stack
make up
```

### Running Specific Services Locally

```bash
# Start a single service + its dependencies
docker-compose up -d postgres redis
cd backend/services/user_service
python main.py  # requires uvicorn: uvicorn service.main:app --reload --port 8001
```

## Code Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) with 100 char line limit
- Use **type hints** for all function signatures
- Format with **Black** and sort imports with **isort**:
  ```bash
  pip install black isort
  black backend/
  isort backend/
  ```
- Run **Ruff** for linting:
  ```bash
  ruff check backend/
  ```
- Naming conventions:
  - `snake_case` for functions, variables, modules
  - `PascalCase` for classes
  - `UPPER_CASE` for constants

### Frontend (TypeScript/React)

- Use **Prettier** for formatting:
  ```bash
  cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"
  ```
- TypeScript strict mode enabled — run type checking before commits:
  ```bash
  cd frontend && npx tsc --noEmit
  ```
- Follow React conventions:
  - Components: `PascalCase`
  - Hooks: `useXxx`
  - Files: `kebab-case.tsx` for pages, `PascalCase.tsx` for components

## Commit Process

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and run tests: `cd backend/services/xxx && pytest tests/ -v`
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat(user-service): add email verification
   fix(resume-service): OCR memory leak on large images
   docs(readme): update architecture diagram
   ```
4. Push and create a PR against `main`

## Testing

### Running Tests by Service

```bash
# user-service
cd backend/services/user_service
TEST_DATABASE_URL=postgresql+asyncpg://jobpilot:jobpilot_secret@localhost:5432/jobpilot_test \
  pytest tests/ -v

# resume-service
cd backend/services/resume_service
TEST_DATABASE_URL=postgresql+asyncpg://jobpilot:jobpilot_secret@localhost:5432/jobpilot_test \
  pytest tests/ -v

# match-service
cd backend/services/match_service
pytest tests/ -v

# apply-service
cd backend/services/apply_service
pytest tests/ -v

# interview-service
cd backend/services/interview_service
pytest tests/ -v

# agent-service
cd backend/services/agent_service
pytest tests/ -v
```

### Running Frontend Tests

```bash
cd frontend
npx tsc --noEmit          # Type check
npx prettier --check "src/"  # Format check
npm run build             # Build check
```

### Test Naming Conventions

- Files: `test_{module}.py`
- Functions: `test_{what}_{condition}`
- Classes: `Test{Feature}`
- Use `pytest.mark.asyncio` for async tests

## Project Structure

```
backend/
├── common/              # Shared library (config, db, auth, redis, es, milvus, neo4j)
└── services/
    ├── user_service/    # Auth, profiles, verification, password reset
    ├── resume_service/  # Resume parsing, AI generation, ATS scoring
    ├── match_service/   # Job search, vector matching, comparison, crawling
    ├── apply_service/   # Application tracking, smart form filling
    ├── interview_service/  # AI interviews, LiveKit, multimodal analysis
    └── agent_service/   # Temporal workflows, event tracking, monitoring
```

Each service follows a standard structure:
```
service_name/
├── main.py          # FastAPI app + routes
├── models.py        # SQLAlchemy ORM models
├── schemas.py       # Pydantic request/response models
├── service.py       # Business logic
├── Dockerfile       # Multi-stage build
├── requirements.txt
├── alembic/         # Database migrations
├── tests/           # Test files
│   ├── conftest.py  # Fixtures
│   └── test_*.py    # Test modules
└── crawler/         # (match-service only) Scrapy spiders
```

## Architecture Decisions

See [docs/adr/](docs/adr/) for key architecture decision records:
- [ADR-001](docs/adr/001-milvus-over-faiss.md) — Why Milvus over Faiss
- [ADR-002](docs/adr/002-temporal-workflow-engine.md) — Why Temporal
- [ADR-003](docs/adr/003-microservices-architecture.md) — Why microservices
- [ADR-004](docs/adr/004-neo4j-skill-graph.md) — Why Neo4j
- [ADR-005](docs/adr/005-livekit-interview.md) — Why LiveKit

## API Reference

Full API documentation is available at each service's OpenAPI docs:
- User Service:  http://localhost:8001/docs
- Resume Service: http://localhost:8002/docs
- Match Service: http://localhost:8003/docs
- Apply Service: http://localhost:8004/docs
- Interview Service: http://localhost:8005/docs
- Agent Service: http://localhost:8006/docs

## Getting Help

- Open an issue on GitHub
- Check existing [ADR docs](docs/adr/) for architecture context
