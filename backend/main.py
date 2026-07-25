"""
Trivia Submission System Backend

Framework:
- FastAPI

Database:
- SQLite using SQLAlchemy ORM (Weeks + Submissions only)

Questions:
- Read from plain text files on disk, not the database.
  See questions/week_XX/<subject>.txt

Features:
- Fetch the active week's question for a chosen subject
- Accept participant submissions (name, email, ID card, file)
- Save each submission's answer file + a readme.txt into its
  own folder under submissions/<name>_<uid>/
- Enforce ONE submission per ID card number, ever (not per week)

Author:
- Animesh
"""

from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from database import SessionLocal, Week, Submission

import shutil
import uuid
import os
from datetime import datetime


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# Allows frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Folders
# --------------------------------------------------

# Where question text files live: questions/week_07/physics.txt
QUESTIONS_FOLDER = "questions"

# Where each participant's answer + readme.txt is stored:
# submissions/Animesh_a1b2c3d4/readme.txt
# submissions/Animesh_a1b2c3d4/<uploaded-file>
SUBMISSIONS_FOLDER = "submissions"

os.makedirs(QUESTIONS_FOLDER, exist_ok=True)
os.makedirs(SUBMISSIONS_FOLDER, exist_ok=True)

# Allowed answer file types
ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".txt",
    ".docx"
}


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


def _get_active_week(db):
    """Returns the single active Week row, or raises 404."""
    active_week = db.query(Week).filter(
        Week.is_active == True
    ).first()

    if active_week is None:
        raise HTTPException(
            status_code=404,
            detail="No active week found"
        )

    return active_week


def _week_folder(week_number: int) -> str:
    return os.path.join(
        QUESTIONS_FOLDER,
        f"week_{week_number:02d}"
    )


# --------------------------------------------------
# Fetch the question for one subject in the active week
# Question text comes from:
#   questions/week_<NN>/<subject>.txt
# --------------------------------------------------
@app.get("/questions/active")
def get_active_question(subject: str):

    db = SessionLocal()
    active_week = _get_active_week(db)
    db.close()

    subject_key = subject.strip().lower()

    question_file = os.path.join(
        _week_folder(active_week.week_number),
        f"{subject_key}.txt"
    )

    if not os.path.isfile(question_file):
        raise HTTPException(
            status_code=404,
            detail=f"No question file found for subject '{subject}'"
        )

    with open(question_file, "r", encoding="utf-8") as f:
        question_text = f.read().strip()

    return {
        "subject": subject_key.capitalize(),
        "week_number": active_week.week_number,
        "week": f"Week {active_week.week_number:02d}",
        "question": question_text,
        "week_id": active_week.id
    }


# --------------------------------------------------
# List every subject that has a question file for the
# active week (used to build a subject picker dynamically,
# if the frontend wants one).
# --------------------------------------------------
@app.get("/questions/active/all")
def get_all_active_questions():

    db = SessionLocal()
    active_week = _get_active_week(db)
    db.close()

    folder = _week_folder(active_week.week_number)

    if not os.path.isdir(folder):
        raise HTTPException(
            status_code=404,
            detail="No questions folder found for the active week"
        )

    subjects = []
    for filename in sorted(os.listdir(folder)):
        if filename.lower().endswith(".txt"):
            subjects.append(os.path.splitext(filename)[0])

    return [
        {"subject": subject} for subject in subjects
    ]


# --------------------------------------------------
# Submit participant answer
#
# - One submission per id_card_no, ever (checked in DB +
#   enforced by a unique column, so a race condition still
#   gets caught by SQLite and turned into a clean 409).
# - Saves the uploaded file and a readme.txt describing the
#   submission into submissions/<name>_<uid>/
# --------------------------------------------------
@app.post("/submissions")
def create_submission(
    name: str = Form(...),
    email: str = Form(...),
    id_card_no: str = Form(...),
    week_id: int = Form(...),
    subject: str = Form(...),
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

    # Create a unique folder for this participant
    # Example: submissions/Animesh_a82f91bc
    user_uuid = str(uuid.uuid4())[:8]
    safe_name = "".join(
        ch for ch in name if ch.isalnum() or ch in (" ", "_", "-")
    ).strip().replace(" ", "_") or "participant"

    folder_name = f"{safe_name}_{user_uuid}"
    user_folder = os.path.join(SUBMISSIONS_FOLDER, folder_name)
    os.makedirs(user_folder, exist_ok=True)

    submission_time = datetime.utcnow()

    # Save the uploaded answer file first, so we know its
    # final name before writing the readme
    unique_filename = str(uuid.uuid4()) + extension
    file_path = os.path.join(user_folder, unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Write readme.txt with the submission's metadata
    readme_path = os.path.join(user_folder, "readme.txt")

    with open(readme_path, "w", encoding="utf-8") as readme:
        readme.write(
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"ID Card No: {id_card_no}\n"
            f"Subject: {subject}\n"
            f"Submitted At (UTC): {submission_time}\n"
            f"Answer File: {unique_filename}\n"
        )

    # Save submission details in the database
    new_submission = Submission(
        name=name,
        email=email,
        id_card_no=id_card_no,
        week_id=week_id,
        subject=subject,
        file_path=file_path,
        submitted_at=submission_time
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
