# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Active support  |

## Reporting a Vulnerability

**Do not open a public GitHub issue.**  
Email `security@jobpilot.io` with detailed steps to reproduce.

We will acknowledge within 48 hours and provide a fix timeline within 5 business days.

## Security Practices

### Authentication

- All API endpoints (except `/auth/login`, `/auth/register`, `/auth/verify-email`, `/auth/forgot-password`, `/auth/reset-password`) require **JWT Bearer token** in the `Authorization` header
- JWT tokens are signed with **HS256** using a configurable secret (`JWT_SECRET_KEY`)
- Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30 minutes)
- Passwords are hashed with **bcrypt** (never stored in plain text)
- Login is **rate-limited**: 5 failed attempts per IP in 5 minutes → 15-minute lockout (Redis-backed)

### Input Validation

- All user input is validated through **Pydantic models** with strict type checking:
  - Emails: `EmailStr` validation
  - URLs: String length max 500
  - Passwords: 6–128 characters
  - String fields: max lengths enforced on all inputs
- File uploads are validated by extension (`.pdf`, `.docx`, `.txt`, `.png`, `.jpg`)
- API responses use Pydantic `response_model` to prevent data leakage

### SQL Injection Prevention

- All database queries use **SQLAlchemy ORM** with parameterized queries
- Raw SQL (`text()`) uses **`:param` bind parameters** — no string interpolation
- Verified: 0 instances of f-string/format-based SQL construction in the codebase

### CORS

- Only whitelisted origins are allowed:
  - `http://localhost:3000` (local development)
  - `http://127.0.0.1:3000`
  - Production domain (configured via `PRODUCTION_DOMAIN` env var)
- Allowed methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
- Allowed headers: Authorization, Content-Type, X-Requested-With, X-Forwarded-For, User-Agent

### Dependency Security

- All Python dependencies are pinned with minimum versions in `requirements.txt`
- CI pipeline runs **Bandit** (static analysis for Python security issues) on every push
- CI pipeline runs **Safety** (known vulnerability check against PyPI advisory DB) on every push
- Frontend dependencies audited via `npm audit`

### Infrastructure

- Elasticsearch runs with `xpack.security.enabled=false` for development; **must enable security in production**
- Neo4j runs with `NEO4J_AUTH=none` for development; **must enable auth in production**
- MinIO uses configurable access keys (`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`)
- All inter-service communication is over internal Docker network `jobpilot-network`
- Traefik handles TLS termination at the gateway (cert-manager in production)

### Production Checklist

- [ ] Set `JWT_SECRET_KEY` to a strong random string (≥ 32 chars)
- [ ] Enable Elasticsearch security (`xpack.security.enabled=true`)
- [ ] Enable Neo4j authentication (`NEO4J_AUTH=neo4j/<password>`)
- [ ] Change MinIO default credentials
- [ ] Set strong LiveKit API key and secret
- [ ] Enable HTTPS/TLS via cert-manager
- [ ] Set `CORS_ORIGIN` to production domain only
- [ ] Run `safety check` on all dependencies before deploy
- [ ] Review `docker-compose.yml` for exposed ports — restrict to Traefik only in production

## Security Scanning in CI

```yaml
# Bandit: Python static security analysis
- name: Bandit Security Scan
  run: |
    pip install bandit
    bandit -r backend/ -f json -o bandit-report.json

# Safety: Dependency vulnerability check
- name: Safety Dependency Check
  run: |
    pip install safety
    safety check --full-report
```

### Baseline

Bandit is configured to run with baseline severity `medium` and above.  
Safety checks against the PyPA advisory database. Both run on every push to `main` and every PR.
