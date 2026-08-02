"""
Trivia Submission System Backend

Framework:
- FastAPI

Database:
- PostgreSQL on Supabase, via SQLAlchemy ORM (Weeks + Questions + Submissions + SubmissionFiles)

Question storage:
- Stored in the `questions` table in Supabase Postgres, editable
  directly in the Table Editor -- no redeploy needed to change a
  question's wording.

File storage:
- Answer files + readme.txt are uploaded to Supabase Storage
  (not local disk -- local disk is wiped on every redeploy/restart
  on most free hosts, so nothing important can live there).

Features:
- Fetch the active week's question for a chosen subject + class level
- Accept participant submissions (name, email, ID card, one or more files)
- Upload each submission's answer file(s) + a readme.txt to
  Supabase Storage under <name>_<uid>/
- Track server-side start_time / submit_time / time_taken per submission
- Each id_card_no may submit AT MOST 3 subjects per week, and never the
  same subject twice in the same week
- Leaderboard ranked by score, tie-broken by time_taken

Author:
- Animesh
"""

from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from database import SessionLocal, Week, Question, Submission, SubmissionFile
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
# --------------------------------------------------

_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://127.0.0.1:5500,http://localhost:5500"
)
ALLOWED_ORIGINS = [
        "https://animeshsitoula.github.io",
        "https://trivia-m42in9vjt-animeshsitoula09-2898s-projects.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".txt",
    ".docx"
}

TAB_SWITCH_FLAG_THRESHOLD = 3

# Max number of DIFFERENT subjects one id_card_no may submit per week
MAX_SUBMISSIONS_PER_WEEK = 3


@app.get("/health")
def health_check():
    return {"status": "ok"}


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


@app.get("/week/active")
def get_active_week_number():
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)
        return {
            "week_number": active_week.week_number,
            "week": f"Week {active_week.week_number:02d}"
        }
    finally:
        db.close()


# --------------------------------------------------
# Fetch the question for one subject + class in the active week
# --------------------------------------------------
@app.get("/questions/active")
def get_active_question(subject: str, class_level: str):
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)

        subject_key = subject.strip().lower()
        class_key = class_level.strip()

        question = db.query(Question).filter(
            Question.week_id == active_week.id,
            Question.subject == subject_key,
            Question.class_level == class_key
        ).first()

        if question is None:
            raise HTTPException(
                status_code=404,
                detail=f"No question found for subject '{subject}' in Class {class_level}"
            )

        start_time = datetime.utcnow()

        return {
            "subject": subject_key.capitalize(),
            "week_number": active_week.week_number,
            "week": f"Week {active_week.week_number:02d}",
            "question": question.question_text,
            "question_id": question.id,
            "week_id": active_week.id,
            "start_time": start_time.isoformat()
        }
    finally:
        db.close()


# --------------------------------------------------
# List every subject with a question for the active week
# --------------------------------------------------
@app.get("/questions/active/all")
def get_all_active_questions():
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)

        questions = db.query(Question).filter(
            Question.week_id == active_week.id
        ).all()

        return [{"subject": question.subject} for question in questions]
    finally:
        db.close()


# --------------------------------------------------
# How many subjects has this id_card_no already submitted this week,
# and which ones -- useful for the frontend to grey out used subjects
# before someone even tries to submit a 4th or repeat one.
# --------------------------------------------------
@app.get("/submissions/status")
def get_submission_status(id_card_no: str):
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)

        existing = db.query(Submission).filter(
            Submission.id_card_no == id_card_no,
            Submission.week_id == active_week.id
        ).all()

        used_subjects = [s.subject for s in existing]

        return {
            "week_id": active_week.id,
            "submissions_used": len(used_subjects),
            "submissions_remaining": max(0, MAX_SUBMISSIONS_PER_WEEK - len(used_subjects)),
            "used_subjects": used_subjects
        }
    finally:
        db.close()


# --------------------------------------------------
# Submit participant answer
#
# - Same id_card_no may submit up to MAX_SUBMISSIONS_PER_WEEK
#   DIFFERENT subjects per week; never the same subject twice.
# - Accepts one or more files, uploaded to Supabase Storage under
#   <name>_<uid>/, plus a readme.txt with submission metadata.
# - start_time comes from the /questions/active response; submit_time
#   and time_taken are computed server-side, here, at submit time.
# --------------------------------------------------
@app.post("/submissions")
def create_submission(
    name: str = Form(...),
    email: str = Form(...),
    id_card_no: str = Form(...),
    week_id: int = Form(...),
    subject: str = Form(...),
    question_id: int = Form(...),
    start_time: str = Form(...),
    tab_switch_count: int = Form(0),
    files: List[UploadFile] = File(...)
):
    db = SessionLocal()

    try:
        # Check 1: has this person already submitted THIS subject this week?
        already_this_subject = db.query(Submission).filter(
            Submission.id_card_no == id_card_no,
            Submission.week_id == week_id,
            Submission.subject == subject
        ).first()

        if already_this_subject:
            raise HTTPException(
                status_code=409,
                detail="You have already submitted an answer for this subject this week"
            )

        # Check 2: has this person already hit the total cap for this week?
        submissions_this_week = db.query(Submission).filter(
            Submission.id_card_no == id_card_no,
            Submission.week_id == week_id
        ).count()

        if submissions_this_week >= MAX_SUBMISSIONS_PER_WEEK:
            raise HTTPException(
                status_code=409,
                detail=f"You have already submitted the maximum of "
                       f"{MAX_SUBMISSIONS_PER_WEEK} answers this week"
            )

        # Validate every file's extension BEFORE saving any of them
        for f in files:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file format: {f.filename}"
                )

        submit_time = datetime.utcnow()

        try:
            parsed_start = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")

        time_taken_seconds = int((submit_time - parsed_start).total_seconds())

        user_uuid = str(uuid.uuid4())[:8]
        safe_name = "".join(
            ch for ch in name if ch.isalnum() or ch in (" ", "_", "-")
        ).strip().replace(" ", "_") or "participant"

        # Include the subject in the folder name now, since one person
        # can have multiple submissions (one folder per submission,
        # not one folder per person overwriting itself)
        folder_name = f"{safe_name}_{subject}_{user_uuid}"

        uploaded_paths = []

        for f in files:
            ext = os.path.splitext(f.filename)[1]
            file_bytes = f.file.read()
            unique_filename = str(uuid.uuid4()) + ext
            storage_path = f"{folder_name}/{unique_filename}"

            try:
                supabase.storage.from_(SUPABASE_BUCKET).upload(
                    storage_path, file_bytes,
                    {"content-type": f.content_type or "application/octet-stream"}
                )
            except Exception as upload_error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to upload {f.filename}: {upload_error}"
                )

            uploaded_paths.append((storage_path, f.filename))

        readme_text = (
            f"Name: {name}\nEmail: {email}\nID Card No: {id_card_no}\nSubject: {subject}\n"
            f"Submitted At (UTC): {submit_time}\n"
            f"Files: {', '.join(fname for _, fname in uploaded_paths)}\n"
        )
        readme_path = f"{folder_name}/readme.txt"
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            readme_path, readme_text.encode("utf-8"), {"content-type": "text/plain"}
        )

        new_submission = Submission(
            name=name,
            email=email,
            id_card_no=id_card_no,
            week_id=week_id,
            question_id=question_id,
            subject=subject,
            submitted_at=submit_time,
            start_time=parsed_start,
            submit_time=submit_time,
            time_taken=time_taken_seconds,
            tab_switch_count=tab_switch_count,
            flagged=tab_switch_count >= TAB_SWITCH_FLAG_THRESHOLD
        )

        db.add(new_submission)
        db.flush()

        for storage_path, original_name in uploaded_paths:
            db.add(SubmissionFile(
                submission_id=new_submission.id,
                file_path=storage_path,
                original_filename=original_name
            ))

        db.commit()

        remaining = MAX_SUBMISSIONS_PER_WEEK - (submissions_this_week + 1)

        return {
            "message": "Submission received",
            "name": name,
            "submissions_remaining": remaining
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not save submission: {e}")

    finally:
        db.close()


# --------------------------------------------------
# Leaderboard -- ranked by score, tie-broken by time_taken.
# Optional ?class_level=11 filter.
# --------------------------------------------------
@app.get("/leaderboard")
def get_leaderboard(class_level: str = None):
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)

        query = db.query(Submission).filter(
            Submission.week_id == active_week.id,
            Submission.score.isnot(None)
        )

        if class_level is not None:
            query = query.join(Question, Submission.question_id == Question.id).filter(
                Question.class_level == class_level
            )

        submissions = query.order_by(
            Submission.score.desc(),
            Submission.time_taken.asc()
        ).limit(10).all()

        leaderboard = []
        for s in submissions:
            question = db.query(Question).filter(Question.id == s.question_id).first()
            leaderboard.append({
                "name": s.name,
                "subject": question.subject if question else s.subject,
                "class_level": question.class_level if question else None,
                "score": s.score,
                "time_taken": s.time_taken
            })

        return {
            "week_number": active_week.week_number,
            "leaderboard": leaderboard
        }
    finally:
        db.close()
