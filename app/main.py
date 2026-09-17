"""
Meridian Health Services — Digital Health Platform API
FastAPI service for managing patient records and appointments.
"""

import os
import hashlib
import logging
from datetime import datetime
from typing import Optional
import sqlite3
import json

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Application setup ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("meridian-health")

# ── Persistent audit log storage ───────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audit_log.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_audit_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            resource TEXT NOT NULL,
            detail TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_audit_db()
def init_data_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            dob TEXT NOT NULL,
            nhs_number TEXT NOT NULL,
            conditions TEXT NOT NULL,
            gp TEXT NOT NULL,
            clinic TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT
        )
    """)

    # Seed starting data only if the tables are empty, so edits made after
    # the first run survive future restarts instead of being overwritten.
    existing = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO patients (id, name, dob, nhs_number, conditions, gp, clinic) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("P001", "James Thompson", "1978-03-15", "943 476 5461",
                 json.dumps(["hypertension", "type-2-diabetes"]), "Dr. Sarah Chen", "Bristol"),
                ("P002", "Amara Okafor", "1992-11-28", "412 833 1029",
                 json.dumps(["asthma"]), "Dr. Marcus Williams", "Bath"),
                ("P003", "Eleanor Davies", "1955-07-04", "728 194 3847",
                 json.dumps(["atrial-fibrillation", "osteoporosis"]), "Dr. Sarah Chen", "Exeter"),
            ]
        )
        conn.executemany(
            "INSERT INTO appointments (id, patient_id, date, type, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("A001", "P001", "2024-12-10", "follow-up", "scheduled", None, None),
                ("A002", "P002", "2024-12-11", "annual-review", "scheduled", None, None),
                ("A003", "P003", "2024-12-09", "urgent", "completed", None, None),
            ]
        )

    conn.commit()
    conn.close()

init_data_db()

def patient_row_to_dict(row):
    patient = dict(row)
    patient["conditions"] = json.loads(patient["conditions"])
    return patient

app = FastAPI(
    title="Meridian Health Services API",
    description="Digital health platform for patient management",
    version="2.1.4"
)

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["x-api-key", "Content-Type"],
)

DEBUG_PASSWORD = os.environ.get("DEBUG_PASSWORD", "")


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
    conn = get_db_connection()
    patient_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    conn.close()
    return {
        "status": "ok",
        "service": "meridian-health",
        "version": "2.1.4",
        "timestamp": datetime.utcnow().isoformat(),
        "patients_registered": patient_count
    }

# ── Patient endpoints ─────────────────────────────────────────────────────────
@app.get("/api/patients")
def list_patients(api_key: str = Depends(get_api_key)):
    """List all registered patients. Requires API key."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM patients").fetchall()
    conn.close()
    patients = [patient_row_to_dict(row) for row in rows]
    return {"patients": patients, "total": len(patients)}

@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str, api_key: str = Depends(get_api_key)):
    """Get a specific patient by ID."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient_row_to_dict(row)

@app.patch("/api/patients/{patient_id}")
def update_patient(patient_id: str, update: PatientUpdate, api_key: str = Depends(get_api_key)):
    """Update patient details."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    patient = patient_row_to_dict(row)
    if update.name:       patient["name"]       = update.name
    if update.conditions: patient["conditions"]  = update.conditions
    if update.gp:         patient["gp"]          = update.gp

    conn.execute(
        "UPDATE patients SET name = ?, conditions = ?, gp = ? WHERE id = ?",
        (patient["name"], json.dumps(patient["conditions"]), patient["gp"], patient_id)
    )
    conn.commit()
    conn.close()
    logger.info(f"Patient {patient_id} updated")
    return patient

# ── Appointment endpoints ─────────────────────────────────────────────────────
@app.get("/api/appointments")
def list_appointments(api_key: str = Depends(get_api_key)):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM appointments").fetchall()
    conn.close()
    appointments = [dict(row) for row in rows]
    return {"appointments": appointments, "total": len(appointments)}

@app.post("/api/appointments")
def create_appointment(appt: AppointmentCreate, api_key: str = Depends(get_api_key)):
    conn = get_db_connection()
    patient = conn.execute("SELECT id FROM patients WHERE id = ?", (appt.patient_id,)).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Patient {appt.patient_id} not found")

    count = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
    new_id = f"A{count + 1:03d}"
    created_at = datetime.utcnow().isoformat()

    conn.execute(
        "INSERT INTO appointments (id, patient_id, date, type, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (new_id, appt.patient_id, appt.date, appt.appointment_type, "scheduled", appt.notes, created_at)
    )
    conn.commit()
    conn.close()

    logger.info(f"Appointment created for patient {appt.patient_id}")
    return {
        "id": new_id,
        "patient_id": appt.patient_id,
        "date": appt.date,
        "type": appt.appointment_type,
        "status": "scheduled",
        "notes": appt.notes,
        "created_at": created_at
    }

# ── Record export ──────────────────────────────────────────────────────────────
@app.get("/api/records/{patient_id}/export")
def export_patient_records(patient_id: str, api_key: str = Depends(get_api_key)):
    """Export a patient's record as a hashed snapshot."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    patient = patient_row_to_dict(row)

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

@app.post("/api/audit")
def log_audit_event(event_type: str, resource: str, detail: str, api_key: str = Depends(get_api_key)):
    """Log an audit event to persistent storage — survives restarts."""
    timestamp = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO audit_log (timestamp, event_type, resource, detail) VALUES (?, ?, ?, ?)",
        (timestamp, event_type, resource, detail)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return {
        "id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "resource": resource,
        "detail": detail,
    }

@app.get("/api/audit")
def get_audit_log(api_key: str = Depends(get_api_key)):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    conn.close()
    events = [dict(row) for row in rows]
    return {"events": events, "total": len(events)}

# ── Clinic summary ────────────────────────────────────────────────────────────
@app.get("/api/clinics/summary")
def clinic_summary(api_key: str = Depends(get_api_key)):
    """Summary of patients per clinic."""
    conn = get_db_connection()
    rows = conn.execute("SELECT clinic FROM patients").fetchall()
    conn.close()
    clinics: dict = {}
    for row in rows:
        clinic = row["clinic"] or "Unknown"
        clinics[clinic] = clinics.get(clinic, 0) + 1
    return {"clinics": clinics, "total_patients": len(rows)}
