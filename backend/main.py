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
from starlette.middleware.cors import CORSMiddleware
from typing import List
from database import SessionLocal, Week, Question, Submission, SubmissionFile,Admin
from supabase import create_client
from dotenv import load_dotenv
from sqlalchemy import text

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
#
# allow_origins   -> exact-match stable domains (GitHub Pages,
#                    Vercel production domain, custom college domain
#                    once that's live)
# allow_origin_regex -> matches any Vercel PREVIEW deploy URL, since
#                    those get a new random hash every push
#                    (e.g. trivia-<hash>-animeshsitoula09-2898s-projects.vercel.app)
# --------------------------------------------------

ALLOWED_ORIGINS = [
    "https://animeshsitoula.github.io",
    "https://trivia-two-livid.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://trivia-.*-animeshsitoula09-2898s-projects\.vercel\.app",
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

@app.get("/admin/login")
def admin_login(username: str = Form(...), password: str = Form(...)):
    db=SessionLocal()
    try:
        result = db.execute(
            text(
                """
                    SELECT admin_id, username FROM admin
                    WHERE username = :username
                    AND password_hash = crypt(:password, password_hash)
                """
            ),
            {"username":username, "password":password}
        ).first()

        if result is None:
            raise HTTPException(status_code=401, detail = "Invalid login credentials")

        return result

    finally:
        db.close()

@app.get("/admin/weeks", dependencies=[Depends(verify_admin)])
def admin_list_weeks():
    db = SessionLocal()
    try:
        weeks = db.query(Week).order_by(Week.week_number.asc()).all()
        return [
            {"id": w.id, "week_number": w.week_number, "is_active": w.is_active}
            for w in weeks
        ]
    finally:
        db.close()


@app.get("/admin/questions", dependencies=[Depends(verify_admin)])
def admin_list_questions(week_id: int = None, subject: str = None):
    db = SessionLocal()
    try:
        query = db.query(Question, Week.week_number).join(Week, Question.week_id == Week.id)

        if week_id is not None:
            query = query.filter(Question.week_id == week_id)
        if subject is not None:
            query = query.filter(Question.subject == subject)

        results = query.order_by(Week.week_number.desc()).all()

        return [
            {
                "id": q.id,
                "week_id": q.week_id,
                "week_number": week_number,
                "subject": q.subject,
                "class_level": q.class_level,
                "question_text": q.question_text
            }
            for q, week_number in results
        ]
    finally:
        db.close()


@app.post("/admin/questions", dependencies=[Depends(verify_admin)])
def admin_create_question(payload: QuestionIn):
    db = SessionLocal()
    try:
        new_question = Question(
            week_id=payload.week_id,
            subject=payload.subject,
            class_level=payload.class_level,
            question_text=payload.question_text
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)

        return {"id": new_question.id, "message": "Question created"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create question: {e}")
    finally:
        db.close()


@app.put("/admin/questions/{question_id}", dependencies=[Depends(verify_admin)])
def admin_update_question(question_id: int, payload: QuestionIn):
    db = SessionLocal()
    try:
        question = db.query(Question).filter(Question.id == question_id).first()

        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")

        question.week_id = payload.week_id
        question.subject = payload.subject
        question.class_level = payload.class_level
        question.question_text = payload.question_text

        db.commit()
        return {"message": "Question updated"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update question: {e}")
    finally:
        db.close()


@app.delete("/admin/questions/{question_id}", dependencies=[Depends(verify_admin)])
def admin_delete_question(question_id: int):
    db = SessionLocal()
    try:
        question = db.query(Question).filter(Question.id == question_id).first()

        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")

        db.delete(question)
        db.commit()
        return {"message": "Question deleted"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Could not delete question (it may have existing submissions referencing it): {e}"
        )
    finally:
        db.close()


@app.get("/admin/submissions", dependencies=[Depends(verify_admin)])
def admin_list_submissions(
    week_id: int = None,
    subject: str = None,
    flagged: bool = None,
    ungraded: bool = None
):
    db = SessionLocal()
    try:
        query = db.query(Submission)

        if week_id is not None:
            query = query.filter(Submission.week_id == week_id)
        if subject is not None:
            query = query.filter(Submission.subject == subject)
        if flagged is not None:
            query = query.filter(Submission.flagged == flagged)
        if ungraded is not None and ungraded:
            query = query.filter(Submission.score.is_(None))

        submissions = query.order_by(Submission.submitted_at.desc()).all()

        result = []
        for s in submissions:
            files = db.query(SubmissionFile).filter(
                SubmissionFile.submission_id == s.id
            ).all()

            file_list = []
            for f in files:
                signed = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(
                    f.file_path, 3600  # link valid for 1 hour
                )
                file_list.append({
                    "id": f.id,
                    "original_filename": f.original_filename,
                    "download_url": signed.get("signedURL") or signed.get("signed_url")
                })

            result.append({
                "id": s.id,
                "name": s.name,
                "id_card_no": s.id_card_no,
                "subject": s.subject,
                "time_taken": s.time_taken,
                "tab_switch_count": s.tab_switch_count,
                "flagged": s.flagged,
                "score": s.score,
                "files": file_list
            })

        return result
    finally:
        db.close()


@app.patch("/admin/submissions/{submission_id}/score", dependencies=[Depends(verify_admin)])
def admin_set_score(submission_id: int, payload: ScoreIn):
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()

        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")

        submission.score = payload.score
        db.commit()
        return {"message": "Score updated"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update score: {e}")
    finally:
        db.close()


@app.get("/admin/stats", dependencies=[Depends(verify_admin)])
def admin_stats():
    db = SessionLocal()
    try:
        active_week = db.query(Week).filter(Week.is_active == True).first()

        if active_week is None:
            return {"active_week": None, "total_submissions": 0, "ungraded": 0, "flagged": 0}

        total = db.query(Submission).filter(Submission.week_id == active_week.id).count()
        ungraded = db.query(Submission).filter(
            Submission.week_id == active_week.id,
            Submission.score.is_(None)
        ).count()
        flagged = db.query(Submission).filter(
            Submission.week_id == active_week.id,
            Submission.flagged == True
        ).count()

        return {
            "active_week": active_week.week_number,
            "total_submissions": total,
            "ungraded": ungraded,
            "flagged": flagged
        }
    finally:
        db.close()