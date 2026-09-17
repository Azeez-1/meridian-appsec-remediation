# Meridian Health Services — Digital Health Platform API

A FastAPI service for managing patient records and appointments across Meridian's clinic network, currently serving 84,000 registered patients.

## Features

- Patient record management (list, retrieve, update)
- Appointment scheduling
- Record export with integrity hashing
- Audit logging for record access
- Per-clinic patient summaries

## Tech Stack

- **Framework:** FastAPI
- **Language:** Python 3.11
- **Testing:** pytest, httpx
- **CI/CD:** GitHub Actions — automated secret scanning (TruffleHog), static analysis (Bandit), and dependency auditing (pip-audit) on every push and pull request

## Local Development

```bash
cd app
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API documentation: http://localhost:8000/docs
Health check: http://localhost:8000/health

## Authentication

All endpoints except `/health` require an API key header:

```
x-api-key: dev-key-12345
```

Override valid keys with the `VALID_API_KEYS` environment variable (comma-separated).

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/api/patients` | List all patients |
| GET | `/api/patients/{id}` | Get a patient by ID |
| PATCH | `/api/patients/{id}` | Update patient details |
| GET | `/api/appointments` | List appointments |
| POST | `/api/appointments` | Create an appointment |
| GET | `/api/records/{id}/export` | Export a patient record |
| POST | `/api/audit` | Log an audit event |
| GET | `/api/audit` | Retrieve the audit log |
| GET | `/api/clinics/summary` | Patient counts per clinic |

## Running Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

## CI Pipeline

Every push and pull request runs through three stages: secret scanning, static analysis, and dependency auditing. All three must pass before a merge.

## Data Storage

Patient and appointment data currently live in an in-memory store for simplicity. A persistent database is a planned follow-up.
