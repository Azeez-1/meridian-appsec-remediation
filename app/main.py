"""
Meridian Health Services — Digital Health Platform API
FastAPI service for managing patient records and appointments.
"""

import os
import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Application setup ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meridian-health")

app = FastAPI(
    title="Meridian Health Services API",
    description="Digital health platform for patient management",
    version="2.1.4"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEBUG_PASSWORD = os.environ.get("DEBUG_PASSWORD", "")


# ── In-memory data store (no database for simplicity) ─────────────────────────
patients_db: dict = {
    "P001": {
        "id": "P001",
        "name": "James Thompson",
        "dob": "1978-03-15",
        "nhs_number": "943 476 5461",
        "conditions": ["hypertension", "type-2-diabetes"],
        "gp": "Dr. Sarah Chen",
        "clinic": "Bristol"
    },
    "P002": {
        "id": "P002",
        "name": "Amara Okafor",
        "dob": "1992-11-28",
        "nhs_number": "412 833 1029",
        "conditions": ["asthma"],
        "gp": "Dr. Marcus Williams",
        "clinic": "Bath"
    },
    "P003": {
        "id": "P003",
        "name": "Eleanor Davies",
        "dob": "1955-07-04",
        "nhs_number": "728 194 3847",
        "conditions": ["atrial-fibrillation", "osteoporosis"],
        "gp": "Dr. Sarah Chen",
        "clinic": "Exeter"
    }
}

appointments_db: list = [
    {"id": "A001", "patient_id": "P001", "date": "2024-12-10", "type": "follow-up", "status": "scheduled"},
    {"id": "A002", "patient_id": "P002", "date": "2024-12-11", "type": "annual-review", "status": "scheduled"},
    {"id": "A003", "patient_id": "P003", "date": "2024-12-09", "type": "urgent", "status": "completed"},
]

# ── Models ────────────────────────────────────────────────────────────────────
class AppointmentCreate(BaseModel):
    patient_id: str
    date: str
    appointment_type: str
    notes: Optional[str] = None

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    conditions: Optional[list] = None
    gp: Optional[str] = None

# ── Authentication helper ─────────────────────────────────────────────────────
def get_api_key(x_api_key: str = Header(default=None)):
    """Simple API key check. In production this would use a proper auth system."""
    configured_keys = os.environ.get("VALID_API_KEYS")
    if not configured_keys:
        raise HTTPException(status_code=500, detail="Server misconfigured: no API keys configured")
    valid_keys = configured_keys.split(",")
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "meridian-health",
        "version": "2.1.4",
        "timestamp": datetime.utcnow().isoformat(),
        "patients_registered": len(patients_db)
    }

# ── Patient endpoints ─────────────────────────────────────────────────────────
@app.get("/api/patients")
def list_patients(api_key: str = Depends(get_api_key)):
    """List all registered patients. Requires API key."""
    return {"patients": list(patients_db.values()), "total": len(patients_db)}

@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str, api_key: str = Depends(get_api_key)):
    """Get a specific patient by ID."""
    patient = patients_db.get(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient

@app.patch("/api/patients/{patient_id}")
def update_patient(patient_id: str, update: PatientUpdate, api_key: str = Depends(get_api_key)):
    """Update patient details."""
    patient = patients_db.get(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    if update.name:       patient["name"]       = update.name
    if update.conditions: patient["conditions"]  = update.conditions
    if update.gp:         patient["gp"]          = update.gp
    patients_db[patient_id] = patient
    logger.info(f"Patient {patient_id} updated")
    return patient

# ── Appointment endpoints ─────────────────────────────────────────────────────
@app.get("/api/appointments")
def list_appointments(api_key: str = Depends(get_api_key)):
    return {"appointments": appointments_db, "total": len(appointments_db)}

@app.post("/api/appointments")
def create_appointment(appt: AppointmentCreate, api_key: str = Depends(get_api_key)):
    if appt.patient_id not in patients_db:
        raise HTTPException(status_code=404, detail=f"Patient {appt.patient_id} not found")
    new_appt = {
        "id": f"A{len(appointments_db) + 1:03d}",
        "patient_id": appt.patient_id,
        "date": appt.date,
        "type": appt.appointment_type,
        "status": "scheduled",
        "notes": appt.notes,
        "created_at": datetime.utcnow().isoformat()
    }
    appointments_db.append(new_appt)
    logger.info(f"Appointment created for patient {appt.patient_id}")
    return new_appt

# ── Record export ──────────────────────────────────────────────────────────────
@app.get("/api/records/{patient_id}/export")
def export_patient_records(patient_id: str, api_key: str = Depends(get_api_key)):
    """Export a patient's record as a hashed snapshot."""
    patient = patients_db.get(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    try:
        record_hash = hashlib.sha256(str(patient).encode()).hexdigest()
    except Exception:
        logger.exception(f"Failed to export patient {patient_id}")
        raise HTTPException(status_code=500, detail="Export failed")

    return {
        "patient_id": patient_id,
        "export_time": datetime.utcnow().isoformat(),
        "record_hash": record_hash,
        "data": patient
    }

# ── Audit log ─────────────────────────────────────────────────────────────────
audit_log: list = []

@app.post("/api/audit")
def log_audit_event(event_type: str, resource: str, detail: str, api_key: str = Depends(get_api_key)):
    """Log an audit event — simulates the audit trail functionality."""
    event = {
        "id": len(audit_log) + 1,
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "resource": resource,
        "detail": detail,
    }
    audit_log.append(event)
    return event

@app.get("/api/audit")
def get_audit_log(api_key: str = Depends(get_api_key)):
    return {"events": audit_log, "total": len(audit_log)}

# ── Clinic summary ────────────────────────────────────────────────────────────
@app.get("/api/clinics/summary")
def clinic_summary(api_key: str = Depends(get_api_key)):
    """Summary of patients per clinic."""
    clinics: dict = {}
    for patient in patients_db.values():
        clinic = patient.get("clinic", "Unknown")
        clinics[clinic] = clinics.get(clinic, 0) + 1
    return {"clinics": clinics, "total_patients": len(patients_db)}
