"""
Trivia Submission System Backend

Framework:
- FastAPI

Database:
- PostgreSQL on Supabase, via SQLAlchemy ORM (Weeks + Questions + Submissions)

Question storage:
- Stored in the `questions` table in Supabase Postgres, editable
  directly in the Table Editor -- no redeploy needed to change a
  question's wording.

File storage:
- Answer files + readme.txt are uploaded to Supabase Storage
  (not local disk -- local disk is wiped on every redeploy/restart
  on most free hosts, so nothing important can live there).

Features:
- Fetch the active week's question for a chosen subject
- Accept participant submissions (name, email, ID card, file)
- Upload each submission's answer file + a readme.txt to
  Supabase Storage under submissions/<name>_<uid>/
- Enforce ONE submission per ID card number, ever (not per week)

Author:
- Animesh
"""

from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from database import SessionLocal, Week, Question, Submission
from supabase import create_client
from dotenv import load_dotenv

import uuid
import os
from datetime import datetime

load_dotenv()

# --------------------------------------------------
# Supabase Storage client
# --------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "submissions")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set "
        "(in .env locally, or Render's Environment tab when deployed)."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# --------------------------------------------------
# CORS
# Allowed origins come from an env var so you can add your
# live frontend URL without touching code, e.g:
#   CORS_ORIGINS=http://127.0.0.1:5500,https://yourname.github.io
# --------------------------------------------------

_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://127.0.0.1:5500,http://localhost:5500"
)
ALLOWED_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Allowed answer file types
ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".txt",
    ".docx"
}

# Submissions with this many or more tab switches get auto-flagged
# for manual review (filter by `flagged` in Supabase's Table Editor).
# This is a signal, not proof of cheating -- adjust as needed.
TAB_SWITCH_FLAG_THRESHOLD = 3


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


@app.get("/week/active")
def get_active_week_number():
    db = SessionLocal()
    active_week = _get_active_week(db)
    db.close()

    return {
        "week_number": active_week.week_number,
        "week": f"Week {active_week.week_number:02d}"
    }


def _get_active_week(db):
    """Returns the Week row where is_active is True, or raises 404."""
    active_week = db.query(Week).filter(
        Week.is_active == True
    ).first()

    if active_week is None:
        raise HTTPException(
            status_code=404,
            detail="No active week found"
        )

    return active_week



# --------------------------------------------------
# Fetch the question for one subject in the active week
# --------------------------------------------------
@app.get("/questions/active")
def get_active_question(subject: str):

    db = SessionLocal()
    active_week = _get_active_week(db)

    subject_key = subject.strip().lower()

    question = db.query(Question).filter(
        Question.week_id == active_week.id,
        Question.subject == subject_key
    ).first()

    db.close()

    if question is None:
        raise HTTPException(
            status_code=404,
            detail=f"No question found for subject '{subject}'"
        )

    return {
        "subject": subject_key.capitalize(),
        "week_number": active_week.week_number,
        "week": f"Week {active_week.week_number:02d}",
        "question": question.question_text,
        "week_id": active_week.id
    }


# --------------------------------------------------
# List every subject with a question for the active week
# --------------------------------------------------
@app.get("/questions/active/all")
def get_all_active_questions():

    db = SessionLocal()
    active_week = _get_active_week(db)

    questions = db.query(Question).filter(
        Question.week_id == active_week.id
    ).all()

    db.close()

    return [
        {"subject": question.subject} for question in questions
    ]


# --------------------------------------------------
# Submit participant answer
#
# - One submission per id_card_no, ever.
# - Uploads the answer file + a readme.txt to Supabase
#   Storage, under submissions/<name>_<uid>/, instead of
#   writing to local disk.
# --------------------------------------------------
@app.post("/submissions")
def create_submission(
    name: str = Form(...),
    email: str = Form(...),
    id_card_no: str = Form(...),
    week_id: int = Form(...),
    subject: str = Form(...),
    tab_switch_count: int = Form(0),
    file: UploadFile = File(...)
):

    db = SessionLocal()

    # Prevent duplicate submission -> only one per ID card, ever
    existing = db.query(Submission).filter(
        Submission.id_card_no == id_card_no
    ).first()

    if existing:
        db.close()
        raise HTTPException(
            status_code=409,
            detail="This ID card number has already submitted an answer"
        )

    extension = os.path.splitext(file.filename)[1]

    if extension.lower() not in ALLOWED_EXTENSIONS:
        db.close()
        raise HTTPException(
            status_code=400,
            detail="Invalid file format"
        )

    # Build a unique folder path for this participant inside
    # the Supabase Storage bucket.
    # Example: submissions bucket -> Animesh_a82f91bc/<file>
    user_uuid = str(uuid.uuid4())[:8]
    safe_name = "".join(
        ch for ch in name if ch.isalnum() or ch in (" ", "_", "-")
    ).strip().replace(" ", "_") or "participant"

    folder_name = f"{safe_name}_{user_uuid}"
    submission_time = datetime.utcnow()

    # Read the uploaded file into memory and upload it to
    # Supabase Storage (answer files are small, so this is fine)
    file_bytes = file.file.read()
    unique_filename = str(uuid.uuid4()) + extension
    storage_path = f"{folder_name}/{unique_filename}"

    try:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            storage_path,
            file_bytes,
            {"content-type": file.content_type or "application/octet-stream"}
        )
    except Exception as upload_error:
        db.close()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to upload answer file: {upload_error}"
        )

    # Upload a readme.txt with the submission's metadata
    readme_text = (
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"ID Card No: {id_card_no}\n"
        f"Subject: {subject}\n"
        f"Submitted At (UTC): {submission_time}\n"
        f"Answer File: {unique_filename}\n"
    )
    readme_path = f"{folder_name}/readme.txt"

    try:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            readme_path,
            readme_text.encode("utf-8"),
            {"content-type": "text/plain"}
        )
    except Exception as upload_error:
        db.close()
        raise HTTPException(
            status_code=502,
            detail=f"Failed to upload readme: {upload_error}"
        )

    # Save submission details in the database
    new_submission = Submission(
        name=name,
        email=email,
        id_card_no=id_card_no,
        week_id=week_id,
        subject=subject,
        file_path=storage_path,
        submitted_at=submission_time,
        tab_switch_count=tab_switch_count,
        flagged=tab_switch_count >= TAB_SWITCH_FLAG_THRESHOLD
    )

    try:
        db.add(new_submission)
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        raise HTTPException(
            status_code=409,
            detail="This ID card number has already submitted an answer"
        )

    db.close()

    return {
        "message": "Submission received",
        "name": name
    }