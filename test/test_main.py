"""
Meridian Health Services — API Tests
These run in the CI pipeline security scan stage.
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import app

client = TestClient(app)
VALID_KEY = "dev-key-12345"
HEADERS = {"x-api-key": VALID_KEY}


def test_health_check():
    """Health endpoint should return 200 without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "meridian-health"


def test_health_includes_patient_count():
    response = client.get("/health")
    assert "patients_registered" in response.json()


def test_list_patients_requires_auth():
    """Patient data must require authentication."""
    response = client.get("/api/patients")
    assert response.status_code == 401


def test_list_patients_with_valid_key():
    response = client.get("/api/patients", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "patients" in data
    assert data["total"] >= 3


def test_get_patient_by_id():
    response = client.get("/api/patients/P001", headers=HEADERS)
    assert response.status_code == 200
    patient = response.json()
    assert patient["id"] == "P001"
    assert "name" in patient
    assert "conditions" in patient


def test_get_nonexistent_patient_returns_404():
    response = client.get("/api/patients/P999", headers=HEADERS)
    assert response.status_code == 404


def test_list_appointments():
    response = client.get("/api/appointments", headers=HEADERS)
    assert response.status_code == 200
    assert "appointments" in response.json()


def test_create_appointment():
    payload = {
        "patient_id": "P001",
        "date": "2024-12-20",
        "appointment_type": "follow-up",
        "notes": "Routine blood pressure check"
    }
    response = client.post("/api/appointments", json=payload, headers=HEADERS)
    assert response.status_code == 200
    appt = response.json()
    assert appt["patient_id"] == "P001"
    assert appt["status"] == "scheduled"


def test_create_appointment_invalid_patient():
    payload = {
        "patient_id": "P999",
        "date": "2024-12-20",
        "appointment_type": "follow-up"
    }
    response = client.post("/api/appointments", json=payload, headers=HEADERS)
    assert response.status_code == 404


def test_clinic_summary():
    response = client.get("/api/clinics/summary", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "clinics" in data
    assert "total_patients" in data


def test_invalid_api_key_rejected():
    response = client.get("/api/patients", headers={"x-api-key": "wrong-key"})
    assert response.status_code == 401


def test_audit_log_creation():
    payload = {"event_type": "view", "resource": "patient/P001", "detail": "Viewed patient record"}
    response = client.post("/api/audit", params=payload, headers=HEADERS)
    assert response.status_code == 200


def test_export_patient_records():
    response = client.get("/api/records/P001/export", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "record_hash" in data
    assert data["patient_id"] == "P001"


def test_export_nonexistent_patient_returns_404():
    """Regression test: the export endpoint used to swallow this into a 500."""
    response = client.get("/api/records/P999/export", headers=HEADERS)
    assert response.status_code == 404
