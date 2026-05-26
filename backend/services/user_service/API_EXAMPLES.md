# User Service API Examples

Base URL: `http://localhost:8001` (direct) or `http://localhost/api/users` (via Traefik gateway).

OpenAPI docs: `http://localhost:8001/docs`

---

## 1. Register

```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "securePass123",
    "full_name": "Alice Wang"
  }'
```

Response (201):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "alice@example.com",
    "full_name": "Alice Wang",
    "role": "candidate",
    "created_at": "2026-05-26T12:00:00Z"
  }
}
```

Error (409) — duplicate email:

```json
{"detail": "Email already registered"}
```

---

## 2. Login

```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "securePass123"
  }'
```

Response (200): same shape as register.

Error (401):

```json
{"detail": "Invalid email or password"}
```

---

## 3. Get Profile

```bash
TOKEN="eyJhbGciOiJIUzI1NiIs..."

curl http://localhost:8001/profile \
  -H "Authorization: Bearer $TOKEN"
```

Response (200):

```json
{
  "id": "4fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "alice@example.com",
  "full_name": "Alice Wang",
  "phone": null,
  "location": null,
  "summary": null,
  "linkedin_url": null,
  "github_url": null,
  "skills": null,
  "experience": null,
  "education": null,
  "updated_at": null
}
```

---

## 4. Update Profile

```bash
curl -X PUT http://localhost:8001/profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+86 13800138000",
    "location": "Shanghai",
    "summary": "Senior engineer skilled in Python, AWS, and Terraform.",
    "linkedin_url": "https://linkedin.com/in/alicewang",
    "github_url": "https://github.com/alicewang",
    "skills": ["Python", "Docker", "Kubernetes", "AWS"],
    "experience": [
      {
        "company": "Acme Corp",
        "title": "Senior Backend Engineer",
        "start_date": "2020-01",
        "end_date": "2023-06",
        "description": "Built microservices with Python and Docker",
        "current": false
      },
      {
        "company": "Startup Inc",
        "title": "Tech Lead",
        "start_date": "2023-07",
        "description": "Leading a team of 5 engineers",
        "current": true
      }
    ],
    "education": [
      {
        "school": "Fudan University",
        "degree": "BSc",
        "field_of_study": "Computer Science",
        "start_date": "2016-09",
        "end_date": "2020-06",
        "gpa": "3.8"
      }
    ]
  }'
```

Response (200) — note skills are normalized and augmented by auto-extraction:

```json
{
  "id": "4fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "alice@example.com",
  "full_name": "Alice Wang",
  "phone": "+86 13800138000",
  "location": "Shanghai",
  "summary": "Senior engineer skilled in Python, AWS, and Terraform.",
  "linkedin_url": "https://linkedin.com/in/alicewang",
  "github_url": "https://github.com/alicewang",
  "skills": ["aws", "docker", "kubernetes", "python", "terraform"],
  "experience": [
    {"company": "Acme Corp", "title": "Senior Backend Engineer", ...},
    {"company": "Startup Inc", "title": "Tech Lead", ...}
  ],
  "education": [
    {"school": "Fudan University", "degree": "BSc", ...}
  ],
  "updated_at": "2026-05-26T12:05:00Z"
}
```

---

## Running Tests

```bash
# Ensure a test PostgreSQL database exists
createdb jobpilot_test

# From the backend directory
cd backend
pip install -r services/user_service/requirements.txt
cd services/user_service
pytest tests/ -v
```

Test output (7 auth + 9 profile = 16 tests):

```
tests/test_auth.py::test_register_success PASSED
tests/test_auth.py::test_register_duplicate_email PASSED
tests/test_auth.py::test_register_short_password PASSED
tests/test_auth.py::test_register_invalid_email PASSED
tests/test_auth.py::test_login_success PASSED
tests/test_auth.py::test_login_wrong_password PASSED
tests/test_auth.py::test_login_nonexistent_user PASSED
tests/test_profile.py::test_get_profile_empty PASSED
tests/test_profile.py::test_get_profile_no_auth PASSED
tests/test_profile.py::test_get_profile_bad_token PASSED
tests/test_profile.py::test_update_profile_skills PASSED
tests/test_profile.py::test_update_profile_experience PASSED
tests/test_profile.py::test_update_profile_education PASSED
tests/test_profile.py::test_update_profile_summary_extracts_skills PASSED
tests/test_profile.py::test_update_profile_partial PASSED
```

---

## Database Migrations

```bash
# From backend/services/user_service
alembic upgrade head      # Apply all migrations
alembic downgrade -1      # Roll back one revision
alembic revision --autogenerate -m "description"  # Create new migration
```
