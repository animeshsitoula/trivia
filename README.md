# Weekly Trivia Submission System

A full-stack weekly trivia platform for **Trinity International School** (SciTech Guild × Trinity Computer Council). Participants pick a subject, answer that week's question, and upload their solution — one submission per ID card, ever.

**Stack:** FastAPI + SQLAlchemy + SQLite (backend) · HTML/CSS/JS (frontend) · MathJax (equation rendering)

---

## Project Structure

```
trivia/
│
├── backend/
│   ├── main.py              # FastAPI app — routes for questions & submissions
│   ├── database.py          # SQLAlchemy models (Week, Submission) + DB connection
│   ├── setup_week.py        # Seeds/activates a week and its sample questions
│   ├── schema.sql           # Reference SQL schema (not used at runtime)
│   │
│   ├── questions/           # Question bank — plain text, NOT the database
│   │   └── week_01/
│   │       ├── physics.txt
│   │       ├── maths.txt     # supports LaTeX: \(...\) inline, $$...$$ display
│   │       ├── computer.txt
│   │       ├── chemistry.txt
│   │       └── biology.txt
│   │
│   ├── submissions/         # Auto-created. One folder per participant.
│   │   └── Name_uid/
│   │       ├── readme.txt   # name, email, ID, subject, timestamp
│   │       └── <answer file>
│   │
│   └── uploads/             # Auto-created. Holds trivia.db (SQLite file).
│
└── frontend/
    ├── index.html           # Subject picker
    ├── answer.html          # Question display + submission form
    ├── success.html         # Confirmation screen
    ├── answer.js            # Fetches question, handles submit
    └── templates/
        └── style.css
```

## How it works

1. **`index.html`** shows five subject cards → clicking one links to `answer.html?subject=<name>`.
2. **`answer.js`** calls `GET /questions/active?subject=<name>`, which reads the active week from the database, then loads the matching `questions/week_XX/<subject>.txt` file straight off disk.
3. On submit, `POST /submissions` checks the ID card number hasn't been used before (globally, across all weeks), saves the uploaded file plus a `readme.txt` into `submissions/<Name>_<uid>/`, and records the entry in SQLite.
4. **`success.html`** confirms the submission using the name passed back from the API.

## Running locally

```bash
cd backend
pip install fastapi sqlalchemy python-multipart uvicorn
python setup_week.py          # seeds week 1 + sample questions (pass a number to seed a different week)
uvicorn main:app --reload     # runs on http://127.0.0.1:8000
```

Then serve `frontend/` with a local server on port 5500 (e.g. VS Code "Live Server") and open `index.html` — don't open the HTML files directly via `file://`, since the backend's CORS policy only allows `http://127.0.0.1:5500` / `http://localhost:5500`.

## Adding/updating questions

Add or edit a `.txt` file inside `questions/week_XX/` named after the subject (`physics.txt`, `maths.txt`, etc). Equations can be written in LaTeX:

```
$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$
```

MathJax renders it automatically on `answer.html`.

## Notes

- `submissions/` and `uploads/` (containing `trivia.db`) are git-ignored — they hold real participant data and should never be committed.
- One ID card number can submit **once total**, not once per week.

---

# Trivia Project — Line-by-Line Walkthrough

This is the companion to the reference guide — instead of explaining concepts
in the abstract, this goes through your **actual files**, line by line, so you
can see exactly what each statement does and why it's written that way. Read
this alongside the real files open in your editor.

---

## PART 1 — `database.py`

```python
from sqlalchemy import (
    create_engine, Column, Integer, Boolean, DateTime,
    String, ForeignKey, UniqueConstraint
)
```
Imports everything needed to define the connection and the table structures.
`create_engine` builds the connection; the rest (`Column`, `Integer`, etc.)
are the building blocks for describing table columns.

```python
from sqlalchemy.orm import sessionmaker, declarative_base
```
`sessionmaker` builds the "session factory" you'll use in every endpoint.
`declarative_base` gives you the shared parent class every model inherits from.

```python
from datetime import datetime
from dotenv import load_dotenv
import os
```
`datetime` is Python's built-in date/time module — used for timestamp
columns. `load_dotenv` reads a local `.env` file into environment variables.
`os` lets you read those environment variables with `os.getenv(...)`.

```python
load_dotenv()
```
Runs once, at import time. Loads `.env` into the environment if the file
exists locally. On Render, there's no `.env` file, so this line just does
nothing there — harmless either way.

```python
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to a .env file locally, "
        "or to Render's Environment tab when deployed."
    )
```
Reads the connection string from the environment rather than hardcoding it
(so the real Supabase password never lives in your code/GitHub). If it's
missing entirely, the app refuses to start with a clear message — better
than failing later with a confusing connection error.

```python
engine = create_engine(DATABASE_URL)
```
Builds the actual connection manager to your Supabase Postgres database.
(No `connect_args={"check_same_thread": False}` here — that setting was
SQLite-specific and doesn't apply to Postgres.)

```python
SessionLocal = sessionmaker(bind=engine)
```
A factory. Every time an endpoint runs `SessionLocal()`, it gets a brand
new, independent "conversation" with the database, bound to this `engine`.

```python
Base = declarative_base()
```
The shared parent class. Every model class below inherits from this, and
`Base.metadata.create_all(engine)` (at the bottom of the file) uses it to
know which tables to build.

```python
class Week(Base):
    __tablename__ = "weeks"
```
Declares a new model. `__tablename__` tells SQLAlchemy this class maps to
the real SQL table named `weeks`.

```python
    id = Column(Integer, primary_key=True)
```
The primary key. Being an `Integer` primary key, it auto-increments — no
need to write `AUTOINCREMENT` yourself.

```python
    week_number = Column(Integer, unique=True, nullable=False)
```
Must be a whole number, must be unique across all rows, and can't be left
empty. This is what stops two different weeks from accidentally sharing
the same week number.

```python
    is_active = Column(Boolean, nullable=False, default=False)
```
A true/false flag. `default=False` means if you insert a row without
explicitly setting this, it defaults to "not active" rather than erroring.

```python
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
```
Same idea as before; `autoincrement=True` here is written explicitly (it's
implied by default for integer primary keys, but spelling it out doesn't
hurt and makes the intent obvious to a reader).

```python
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
```
This column's value must match a real `id` in the `weeks` table.
`ForeignKey("weeks.id")` is how "this question belongs to that week" is
expressed — through a reference, not by copying week data into every row.

```python
    subject = Column(String, nullable=False)
    class_level = Column(String, nullable=True)
    question_text = Column(String, nullable=False)
```
Plain text columns. `class_level` is nullable specifically so old rows
(inserted before this column existed) don't become invalid — they'll just
show `NULL`/`None` for this field until you fill it in.

```python
    __table_args__ = (UniqueConstraint("week_id", "subject", "class_level"),)
```
A constraint spanning **three columns together** — no single one of them
needs to be unique alone, but the *combination* must be. This is what
prevents two questions existing for the same week+subject+class at once.
The trailing comma inside the parentheses is required — it's what makes
this a one-element **tuple** rather than just parentheses around a single
value; without it, Python wouldn't treat this as a tuple at all.

```python
class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
```
Straightforward required text fields.

```python
    id_card_no = Column(String, nullable=False, unique=True)
```
Globally unique — enforces "one submission per person, ever" (or, if
you're now wiping the table weekly, effectively "per week" instead, since
old rows won't exist to conflict with).

```python
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
```
Links this submission back to which week and which specific question it
answers. `question_id` is nullable to stay compatible with any old rows
saved before this column existed.

```python
    subject = Column(String, nullable=False)
```
Stored as plain text here (not just derived from `question_id`) so a
submission still makes sense to read even if its linked question is later
edited or deleted.

```python
    file_path = Column(String, nullable=True)
```
Legacy field from before multiple files were supported. Nullable now,
since new submissions store their files in the separate `submission_files`
table instead.

```python
    score = Column(Integer, nullable=True)
```
Empty until you manually grade it. This is exactly the field the
leaderboard query filters on (`Submission.score.isnot(None)`).

```python
    tab_switch_count = Column(Integer, nullable=False, default=0)
    flagged = Column(Boolean, nullable=False, default=False)
```
`tab_switch_count` starts at 0 and is incremented by frontend JS.
`flagged` gets computed in the backend (`tab_switch_count >= THRESHOLD`)
and stored, so you can filter flagged submissions directly in Supabase's UI
without recalculating anything.

```python
    start_time = Column(DateTime, nullable=True)
    submit_time = Column(DateTime, nullable=True)
    time_taken = Column(Integer, nullable=True)
```
The three timestamp-tracking fields. All nullable so old submissions
(saved before this feature existed) don't become invalid rows.

```python
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```
**Important: `datetime.utcnow` — no parentheses.** This passes the
*function itself* as the default, not the result of calling it. SQLAlchemy
calls this function fresh, itself, at the moment each new row is actually
inserted — giving each row its own real insert timestamp. If you wrote
`datetime.utcnow()` (with parentheses), it would be evaluated once, when
the Python file is first loaded, and every single row would get frozen to
that same original moment — a subtle, easy-to-miss bug.

```python
class SubmissionFile(Base):
    __tablename__ = "submission_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```
One row per uploaded file, linked back to its parent submission via
`submission_id`. This is what allows one submission to have *many* files —
each file gets its own row here, rather than trying to cram multiple paths
into one string column.

```python
if __name__ == "__main__":
    try:
        connection = engine.connect()
        print("Database connection successful")
        connection.close()
    except Exception as e:
        print("Database connection failed:", e)

    Base.metadata.create_all(bind=engine)
```
`if __name__ == "__main__":` means this block only runs when you execute
`python database.py` directly — **not** when `main.py` imports from this
file (which happens on every server start). This is purely a manual
connection test + "build any missing tables" helper, not something that
runs as part of normal app startup.

---

## PART 2 — `main.py`

```python
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from database import SessionLocal, Week, Question, Submission, SubmissionFile
from supabase import create_client
from dotenv import load_dotenv

import uuid
import os
from datetime import datetime
```
- `List` (from `typing`) is needed to type-hint "a list of UploadFile
  objects" (`files: List[UploadFile]`) for the multi-file endpoint.
- Everything is imported from `database` that main.py actually uses —
  notably `SubmissionFile` had to be added here; forgetting it caused
  every submission to silently fail with a `NameError`.
- `uuid` generates unique, effectively-impossible-to-collide identifiers,
  used for both saved filenames and per-participant folder names.

```python
load_dotenv()
```
Same as in `database.py` — loads local `.env` values if present.

```python
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "submissions")
```
Reads Supabase Storage credentials from the environment. The third line's
second argument, `"submissions"`, is a **default value** — if
`SUPABASE_BUCKET` isn't set in the environment at all, it falls back to
the literal string `"submissions"` instead of being `None`.

```python
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set "
        "(in .env locally, or Render's Environment tab when deployed)."
    )
```
Fails loudly and immediately at startup if these are missing, rather than
failing confusingly later the first time a file upload is attempted.

```python
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
```
Builds the actual client object used later for `supabase.storage...` calls.

```python
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
```
Creates the FastAPI application. Passing `None` for all three disables the
auto-generated `/docs`, `/redoc`, and raw schema pages — useful once
you're live, since otherwise anyone can see (and even execute) every
endpoint's exact shape.

```python
_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://127.0.0.1:5500,http://localhost:5500"
)
ALLOWED_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]
```
Reads a comma-separated list of allowed frontend origins from the
environment (falling back to local dev defaults if unset), then:
- `.split(",")` breaks the string into a list at each comma
- the `for origin in ... if origin.strip()` part is a **list
  comprehension** — it builds a new list by taking each `origin`, calling
  `.strip()` to remove stray whitespace, and only keeping it `if
  origin.strip()` is non-empty (filters out any accidental blank entries
  from something like a trailing comma).

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Registers the CORS middleware with your computed allowlist. `["*"]` for
methods/headers means "allow any HTTP method/header" — fine for this
project's scale, more permissive than you'd want on something handling
sensitive user data at large scale.

```python
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".txt", ".docx"}
```
A Python **set** (curly braces, no key:value pairs) — used because
checking "is this value in the set" (`ext in ALLOWED_EXTENSIONS`) is fast
and sets naturally have no duplicates, which fits this use case perfectly
(you never need duplicates or ordering here, just membership testing).

```python
TAB_SWITCH_FLAG_THRESHOLD = 3
```
A plain constant — kept as a named variable, not a magic number buried in
logic, so it's easy to find and adjust later without hunting through code.

```python
@app.get("/health")
def health_check():
    return {"status": "ok"}
```
The simplest possible endpoint — proves the server is alive and reachable.

```python
def _get_active_week(db):
    """Returns the Week row where is_active is True, or raises 404."""
    active_week = db.query(Week).filter(Week.is_active == True).first()

    if active_week is None:
        raise HTTPException(status_code=404, detail="No active week found")

    return active_week
```
A **helper function**, not an endpoint itself (no `@app.get`/`@app.post`
decorator) — its leading underscore is a Python convention signaling "this
is internal, not meant to be imported/used from outside this file." Pulled
out because nearly every endpoint needs "find the active week or fail,"
and repeating that same query+check in five different places would be
repetitive and error-prone if it ever needed to change.

```python
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
```
- `f"Week {active_week.week_number:02d}"` — an **f-string** (formatted
  string) with a format spec. `:02d` means "format this integer with at
  least 2 digits, zero-padded" — so week `2` displays as `"Week 02"`, not
  `"Week 2"`.
- `try` / `finally` guarantees `db.close()` runs whether `_get_active_week`
  succeeds or raises the 404 — no path through this function can leave the
  session open.

```python
@app.get("/questions/active")
def get_active_question(subject: str, class_level: str):
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)

        subject_key = subject.strip().lower()
        class_key = class_level.strip()
```
`subject.strip().lower()` removes accidental leading/trailing whitespace
and normalizes case, so `"Physics"`, `" physics"`, and `"physics"` in the
URL all match the same stored `"physics"` row. `class_level` is only
`.strip()`'d, not lowercased — since class values like `"11"`/`"12"` are
numeric strings where case doesn't apply.

```python
        question = db.query(Question).filter(
            Question.week_id == active_week.id,
            Question.subject == subject_key,
            Question.class_level == class_key
        ).first()
```
Three conditions, comma-separated inside one `.filter()` call — all must
match (SQL `AND`). This is the pattern that must never use Python's `and`
keyword instead (see the reference guide, section 3.4, for why).

```python
        if question is None:
            raise HTTPException(
                status_code=404,
                detail=f"No question found for subject '{subject}' in Class {class_level}"
            )
```
Note this uses the *original* `subject`/`class_level` (not the normalized
`_key` versions) in the error message — purely so the message echoes back
exactly what the caller sent, for clarity.

```python
        start_time = datetime.utcnow()
```
Generated here, at the exact moment the question is served — this is the
server-side timestamp the whole time-tracking feature depends on.

```python
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
```
`.capitalize()` turns `"physics"` into `"Physics"` for display purposes
only — the underlying stored/compared value stays lowercase.
`start_time.isoformat()` converts the Python `datetime` object into a
standard text format (e.g. `"2026-08-02T14:32:05.123456"`) that can travel
safely inside JSON and be parsed back into a real datetime later by
`datetime.fromisoformat(...)` in the submission endpoint.

```python
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
```
Every field the frontend's `FormData` must include, with matching types.
`tab_switch_count: int = Form(0)` has an actual default (`0`), unlike the
others which use `Form(...)` (required, no default) — meaning if the
frontend somehow doesn't send this field, it just defaults to zero instead
of the request failing outright.

```python
    db = SessionLocal()

    try:
        existing = db.query(Submission).filter(
            Submission.id_card_no == id_card_no
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="This ID card number has already submitted an answer"
            )
```
The duplicate check runs **first**, before touching any files — a
deliberate ordering choice (cheap database check before expensive/risky
file operations), so a rejected duplicate never leaves an orphaned
uploaded file sitting around.

```python
        for f in files:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file format: {f.filename}"
                )
```
`os.path.splitext("photo.PNG")` returns `("photo", ".PNG")` — a tuple;
`[1]` grabs just the extension, `.lower()` normalizes it so `.PNG` and
`.png` are treated identically. **Every** file is checked before any of
them are uploaded — if even one file in a multi-file submission is
invalid, the whole submission is rejected up front, rather than partially
uploading some files and then failing.

```python
        submit_time = datetime.utcnow()

        try:
            parsed_start = datetime.fromisoformat(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")

        time_taken_seconds = int((submit_time - parsed_start).total_seconds())
```
- `submit_time` — the server-side "now," at the exact moment of submission.
- `datetime.fromisoformat(start_time)` parses the text timestamp (that was
  sent back from `/questions/active`) into a real Python `datetime` object
  again. Wrapped in its own `try`/`except` because this string comes from
  the client — if it's ever malformed (tampered with, or a bug elsewhere),
  this fails cleanly with a 400 instead of crashing the whole request.
- `(submit_time - parsed_start)` — subtracting two `datetime` objects gives
  a `timedelta` object (a duration). `.total_seconds()` converts that
  duration into a plain number of seconds; `int(...)` rounds it down to a
  whole number, since fractional seconds aren't meaningful here.

```python
        user_uuid = str(uuid.uuid4())[:8]
```
`uuid.uuid4()` generates a full random unique identifier (a long string
like `a3f1c9e2-8b7d-4e21-9f3a-7c8e6d4b2f10`). `str(...)` converts it to
text, and `[:8]` takes just the **first 8 characters** — a shorter, still
extremely unlikely-to-collide identifier, used here purely to keep folder
names readable rather than needing the full-length UUID for uniqueness.

```python
        safe_name = "".join(
            ch for ch in name if ch.isalnum() or ch in (" ", "_", "-")
        ).strip().replace(" ", "_") or "participant"
```
This is a **generator expression** inside `"".join(...)`. Reading it right
to left: for each character `ch` in the person's `name`, keep it only if
`ch.isalnum()` (a letter or digit) or it's a space, underscore, or hyphen
— discarding anything else (symbols, punctuation, anything that could
break a file path). `"".join(...)` glues the surviving characters back
into one string with no separator. `.strip()` trims leading/trailing
spaces, `.replace(" ", "_")` swaps remaining spaces for underscores
(cleaner for folder names), and `or "participant"` is a fallback — if
after all that filtering the result is an empty string (e.g. someone
submitted a name of just emoji/symbols), use the literal word
`"participant"` instead of an unusable blank folder name.

```python
        folder_name = f"{safe_name}_{user_uuid}"
```
Combines the cleaned name and short UUID into one folder path, e.g.
`Animesh_a82f91bc` — human-readable, and still unique even if two people
share the exact same name.

```python
        uploaded_paths = []

        for f in files:
            ext = os.path.splitext(f.filename)[1]
            file_bytes = f.file.read()
            unique_filename = str(uuid.uuid4()) + ext
            storage_path = f"{folder_name}/{unique_filename}"
```
For each file: get its extension again (this time keeping original case,
just for the saved filename — doesn't need normalizing since it's not
being compared to anything), read the raw bytes into memory
(`f.file.read()`), and build a fully unique filename using a **full**
UUID this time (not truncated — the actual saved file needs the strongest
collision-avoidance, unlike the folder name which just needs to be
distinct enough to be readable).

```python
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
```
`f.content_type or "application/octet-stream"` — if the browser didn't
supply a content type for some reason, fall back to a generic
"just binary data" type rather than sending `None`. Each successfully
uploaded file's `(storage_path, original_filename)` pair gets appended as
a **tuple** to `uploaded_paths`, to be used both in the readme text and
later when creating `SubmissionFile` rows.

```python
        readme_text = (
            f"Name: {name}\nEmail: {email}\nID Card No: {id_card_no}\nSubject: {subject}\n"
            f"Submitted At (UTC): {submit_time}\n"
            f"Files: {', '.join(fname for _, fname in uploaded_paths)}\n"
        )
```
Builds a small human-readable text summary uploaded alongside the actual
answer files, for your own manual review convenience.
`', '.join(fname for _, fname in uploaded_paths)` — another generator
expression: for each `(storage_path, fname)` tuple in `uploaded_paths`,
take just `fname` (the `_` is a Python convention meaning "I don't need
this value, just ignoring it"), then join all the filenames with `", "`
between them.

```python
        readme_path = f"{folder_name}/readme.txt"
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            readme_path, readme_text.encode("utf-8"), {"content-type": "text/plain"}
        )
```
`readme_text.encode("utf-8")` converts the Python string into raw bytes —
Supabase Storage's upload function expects bytes, not a text string
directly, so this conversion is required before uploading.

```python
        new_submission = Submission(
            name=name, email=email, id_card_no=id_card_no,
            week_id=week_id, question_id=question_id, subject=subject,
            submitted_at=submit_time, start_time=parsed_start, submit_time=submit_time,
            time_taken=time_taken_seconds, tab_switch_count=tab_switch_count,
            flagged=tab_switch_count >= TAB_SWITCH_FLAG_THRESHOLD
        )
```
Builds the Python object representing the new row — nothing saved yet.
`flagged=tab_switch_count >= TAB_SWITCH_FLAG_THRESHOLD` computes a
boolean directly (`True`/`False`) based on comparing the count to your
constant, storing the *result* of that comparison, not the comparison
itself.

```python
        db.add(new_submission)
        db.flush()

        for storage_path, original_name in uploaded_paths:
            db.add(SubmissionFile(
                submission_id=new_submission.id,
                file_path=storage_path,
                original_filename=original_name
            ))

        db.commit()
```
`db.flush()` sends the `Submission` insert to the database and assigns
`new_submission.id` — without yet making it permanent. This lets the
following loop correctly reference `new_submission.id` when creating each
`SubmissionFile` row. Only the final `db.commit()` makes everything —
the submission row *and* all its file rows — permanent, together, as one
atomic unit.

```python
        return {"message": "Submission received", "name": name}

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not save submission: {e}")

    finally:
        db.close()
```
- First `except HTTPException: ... raise` — catches your own deliberate
  errors (409, 400, 502), rolls back any partial DB work, then `raise`
  with no argument **re-raises the exact same exception**, unchanged, so
  its original status code and message reach the client correctly.
- Second `except Exception as e` — catches anything *unexpected*
  (a genuine bug), rolls back, and wraps it as a 500 while **including the
  real error text** (`{e}`) — this is what exposes true bugs like the
  missing `SubmissionFile` import instead of hiding them behind a
  misleading generic message.
- `finally: db.close()` — runs no matter which of the above paths was
  taken, or if the function succeeded entirely — guaranteeing the session
  always gets closed exactly once.

```python
@app.get("/leaderboard")
def get_leaderboard(class_level: str = None):
```
`class_level: str = None` — a parameter **with a default value** makes it
optional. Calling `/leaderboard` with no query string at all is valid;
`class_level` will just be `None` inside the function.

```python
    db = SessionLocal()
    try:
        active_week = _get_active_week(db)

        query = db.query(Submission).filter(
            Submission.week_id == active_week.id,
            Submission.score.isnot(None)
        )
```
`.isnot(None)` — SQLAlchemy's way of expressing SQL's `IS NOT NULL` (you
can't use Python's `!=` for this comparison against `None` in a filter —
`isnot`/`is_` are the correct SQLAlchemy methods for null checks). This
builds the query object but doesn't execute it yet — nothing's fetched
from the database at this line.

```python
        if class_level is not None:
            query = query.join(Question, Submission.question_id == Question.id).filter(
                Question.class_level == class_level
            )
```
Only joins to `Question` if a class filter was actually requested — this
avoids the (small) extra cost of a join when nobody asked for it.
`query = query.join(...).filter(...)` reassigns `query` to a *new*,
extended version of itself — SQLAlchemy queries are built up step by step
like this, each method returning a new query object rather than mutating
the original in place.

```python
        submissions = query.order_by(
            Submission.score.desc(),
            Submission.time_taken.asc()
        ).limit(10).all()
```
This is where the query actually executes. Sorted by score descending
first; among equal scores, sorted by `time_taken` ascending (faster
correct answers rank higher on ties). `.limit(10)` caps it to the top 10
results — no point fetching/returning more than a leaderboard needs.
`.all()` finally runs the query and returns a real Python list.

```python
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
```
For each submission, look up its linked question (to get `class_level`,
which only lives on `Question`, not `Submission`). `question.subject if
question else s.subject` is a Python **conditional expression** ("ternary")
— "use `question.subject` if `question` is truthy (i.e., not `None`),
otherwise fall back to `s.subject`" — a safety net in case a linked
question was ever deleted after the submission was made.

```python
        return {
            "week_number": active_week.week_number,
            "leaderboard": leaderboard
        }
    finally:
        db.close()
```
Returns the whole computed list, wrapped with the week number for context.

---

## PART 3 — `index.js` (subjects page)

```js
const API_BASE = "https://trivia-ehw5.onrender.com";
```
A single place to define your backend's base URL — every fetch call
builds on top of this, so changing hosts later only requires editing this
one line.

```js
async function loadActiveWeek() {
    const label = document.getElementById("week-label");
    try {
        const response = await fetch(`${API_BASE}/week/active`);
        if (!response.ok) {
            label.textContent = "No active week right now";
            return;
        }
        const data = await response.json();
        label.textContent = `${data.week} — Live Now`;
    } catch (error) {
        console.log("Failed to load active week:", error);
        label.textContent = "Could not load week info";
    }
}
```
- `async function` — required to use `await` inside.
- `` `${API_BASE}/week/active` `` — a **template literal** (backtick
  string). `${...}` inside it inserts the value of that expression
  directly into the string, avoiding manual `+` concatenation.
- `if (!response.ok)` — checks specifically for an HTTP-level failure
  (like a 404) that still successfully returned a response — different
  from the `catch` block below, which only fires if the request never
  even reached the server at all (network failure, CORS block, etc.).
- The `catch` block is a safety net for that second, different kind of
  failure.

```js
document.querySelectorAll(".choose-link").forEach(function (link) {
    link.addEventListener("click", function (event) {
        event.preventDefault();
        const targetHref = link.getAttribute("href");
        pendingHref = targetHref;
        document.getElementById("class-modal").style.display = "flex";
    });
});
```
- `document.querySelectorAll(".choose-link")` finds **every** element with
  that class (there are 5 subject links) and returns something like a
  list. `.forEach(...)` runs the given function once per element found,
  attaching a separate click listener to each one.
- `event.preventDefault()` stops the link's default behavior (navigating
  immediately to its `href`), so your own JS logic can decide what happens
  instead.
- `link.getAttribute("href")` reads the literal `href` value written in
  the HTML (e.g. `"answer.html?subject=physics"`) as a plain string.
- `pendingHref = targetHref` — note there's no `let`/`const` here; this
  works only because `pendingHref` is declared with `let` further down in
  the same file (see next block) — JS hoists `let` declarations to the
  top of their scope in terms of *existence* (though not *usability*
  before the declaration line runs), so by the time this click handler
  actually fires (after page load), the later `let pendingHref = null;`
  line has already run.

```js
let pendingHref = null;
```
Declared once, at the top level of the script — this is a variable shared
across multiple functions/listeners in this file, used to "remember"
which subject link was clicked, between the moment the modal opens and
the moment a class is chosen afterward.

```js
document.querySelectorAll(".modal-choice").forEach(function (btn) {
    btn.addEventListener("click", function () {
        const chosenClass = btn.dataset.class;
        window.location.href = pendingHref + "&class_level=" + encodeURIComponent(chosenClass);
    });
});
```
- `btn.dataset.class` reads the value of a `data-class="11"` HTML
  attribute as `"11"` — `.dataset` is JS's built-in way to access any
  `data-*` attribute on an element, converting the hyphenated attribute
  name into a JS property.
- Builds the final redirect URL by appending `&class_level=...` onto the
  subject link's original `href` (which already had `?subject=...` on it)
  — `&` joins the second parameter, since `?` already introduced the first.

```js
document.querySelector(".modal-close").addEventListener("click", function () {
    document.getElementById("class-modal").style.display = "none";
    pendingHref = null;
});

document.getElementById("class-modal").addEventListener("click", function (event) {
    if (event.target.id === "class-modal") {
        this.style.display = "none";
        pendingHref = null;
    }
});
```
- The close (×) button simply hides the modal again and clears
  `pendingHref` (so an old, stale value can't accidentally be reused).
- The second listener is on the **overlay itself** (the dark background),
  not the box. `event.target` is *whichever specific element was actually
  clicked* — checking `event.target.id === "class-modal"` distinguishes
  "the user clicked the dark backdrop" from "the user clicked something
  inside the gold box" (which would have a different `event.target`),
  letting clicking outside the box close it, while clicking inside it
  doesn't.

```js
loadActiveWeek();
```
The one line that actually kicks off the async function — everything
above just *defines* functions and listeners; this is what makes anything
actually run when the page loads.

---

## PART 4 — `answer.js` (question + submission page)

```js
const params = new URLSearchParams(window.location.search);
const subject = params.get("subject");
const classLevel = params.get("class_level");
```
`window.location.search` is the raw query string portion of the current
URL (e.g. `"?subject=physics&class_level=11"`). Wrapping it in
`URLSearchParams` gives you `.get("key")` to pull out individual values
safely, without writing your own string-parsing logic.

```js
let selectedFiles = [];
```
The array acting as the real source of truth for which files are
currently attached — declared with `let` since it's reassigned/mutated
throughout the file (well, mutated via `.push()`/`.splice()`, not
reassigned, but `let` is still correct/conventional here).

```js
function renderFileList() {
    const listEl = document.getElementById("file-list");
    listEl.innerHTML = "";
```
`listEl.innerHTML = ""` clears out any previously rendered file chips
before redrawing the whole list from scratch. Using `innerHTML` here is
fine — you're clearing to empty, not inserting untrusted text.

```js
    selectedFiles.forEach((file, index) => {
        const chip = document.createElement("div");
        chip.className = "file-chip";
        chip.innerHTML = `<span></span><span class="remove-file">×</span>`;
        chip.querySelector("span").textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
```
- `.forEach((file, index) => {...})` — an **arrow function**, a shorter
  syntax for writing a function, commonly used for short callbacks like
  this. `(file, index)` — `.forEach` automatically supplies both the
  current item (`file`) and its position in the array (`index`).
- `document.createElement("div")` builds a brand new, empty `<div>` in
  memory (not yet visible on the page).
- The `innerHTML` here creates the chip's two empty `<span>` placeholders
  — safe, since the content being inserted is a fixed literal template,
  not untrusted user data.
- `.querySelector("span")` grabs the **first** matching `<span>` inside
  `chip` specifically, then `.textContent = ...` fills it with the actual
  filename and its size — safely, as plain text, even though the filename
  itself came from the user's own computer (a filename could theoretically
  contain HTML-like characters).
- `(file.size / 1024).toFixed(0)` — `file.size` is in bytes; dividing by
  1024 converts to kilobytes; `.toFixed(0)` rounds to a whole number with
  no decimal places, returned as a string.

```js
        chip.querySelector(".remove-file").addEventListener("click", () => {
            selectedFiles.splice(index, 1);
            renderFileList();
        });

        listEl.appendChild(chip);
    });
}
```
- `selectedFiles.splice(index, 1)` removes exactly one item, at position
  `index`, from the array — this is how clicking a chip's × actually
  removes that specific file from the pending submission.
- `renderFileList()` is called again immediately after removal, to redraw
  the whole list reflecting the new, shorter array.
- `listEl.appendChild(chip)` actually inserts the fully-built chip into
  the real page — everything before this line only existed in memory.

```js
document.getElementById("file-upload").addEventListener("change", function () {
    for (const file of this.files) {
        selectedFiles.push(file);
    }
    renderFileList();
    this.value = "";
});
```
- `"change"` fires whenever someone picks file(s) via the input.
- `this.files` refers to whatever the input currently holds (a native
  browser list of selected files) — `for (const file of this.files)`
  loops over each one and `.push()`s it into your own persistent
  `selectedFiles` array, which is what actually accumulates across
  multiple separate clicks of "+ Add file."
- `this.value = ""` resets the raw input afterward — necessary because
  browsers don't fire `"change"` again if you pick the exact same file a
  second time in a row, unless the input's value has been cleared first.

```js
async function loadQuestion() {
    if (!subject || !classLevel) {
        document.getElementById("question-text").textContent =
            "No subject or class selected. Please go back and choose again.";
        document.getElementById("week-label").textContent = "No subject selected";
        return;
    }
```
`!subject || !classLevel` — `!` negates a value's truthiness; an empty or
missing URL parameter (`null`) is falsy, so `!subject` is `true` if
`subject` is missing. `||` means "or" — this whole condition is true if
*either* value is missing, catching someone who reached this page without
going through the proper subject/class-selection flow first.

```js
    try {
        const response = await fetch(
            `${API_BASE}/questions/active?subject=${encodeURIComponent(subject)}&class_level=${encodeURIComponent(classLevel)}`
        );
```
Both values are wrapped in `encodeURIComponent()` before being inserted
into the URL — necessary in case a subject or class value ever contains
characters that would otherwise break the URL's structure.

```python
        if (!response.ok) {
            document.getElementById("question-text").textContent =
                "Could not load a question for this subject right now.";
            document.getElementById("week-label").textContent = "No active week found";
            return;
        }

        const data = await response.json();
```
(This block is JS, despite the accidental Python-style code fence above —
just a formatting note, not a real language difference.) Standard
"check `.ok`, then parse the body" pattern.

```js
        document.getElementById("subject-name").textContent = data.subject;
        document.getElementById("question-ref").textContent = data.week;
        document.getElementById("question-text").textContent = data.question;
        document.getElementById("week-label").textContent = `${data.week} — Live Now`;

        document.getElementById("week-id").value = data.week_id;
        document.getElementById("subject-field").value = subject;
        document.getElementById("question-id").value = data.question_id;
        document.getElementById("start-time").value = data.start_time;
```
Displays the visible parts of the question (`textContent`) and separately
populates the **hidden form fields** (`.value = ...`) that will be read
back out later when the form is submitted — this is how data fetched from
the GET request gets carried forward into the POST request without the
user seeing or interacting with it directly.

```js
        if (window.MathJax && window.MathJax.typesetPromise) {
            MathJax.typesetPromise([document.getElementById("question-text")]);
        }

    } catch (error) {
        console.log("Failed to load question:", error);
        document.getElementById("question-text").textContent =
            "Could not reach the server. Please try again shortly.";
        document.getElementById("week-label").textContent = "Could not load week info";
    }
}
```
`window.MathJax && window.MathJax.typesetPromise` — checks that both the
MathJax library itself has loaded, *and* that this specific function
exists on it, before calling it — avoids a crash if MathJax's script
hasn't finished loading yet by the time this runs.
`MathJax.typesetPromise([element])` tells MathJax to specifically re-scan
just this one element for math notation and render it — necessary because
this text arrived dynamically, after MathJax's one-time automatic page
scan already happened.

```js
async function handleSubmit(event) {
    event.preventDefault();

    if (selectedFiles.length === 0) {
        alert("Please attach at least one file.");
        return;
    }
```
`event.preventDefault()` stops the browser's default full-page-reload form
submission, so this JS function can handle it instead via `fetch()`.
A guard clause: don't even attempt to submit if no files were ever added.

```js
    const form = event.target;
    const formData = new FormData(form);
```
`event.target` is the actual `<form>` element that was submitted.
`new FormData(form)` automatically reads every named input inside that
form and builds a `FormData` object from them — a convenient shortcut
instead of manually reading each field by id.

```js
    const payload = new FormData();
    payload.append("name", formData.get("name"));
    payload.append("email", formData.get("email"));
    payload.append("id_card_no", formData.get("idcard"));
    payload.append("week_id", formData.get("week_id"));
    payload.append("subject", formData.get("subject"));
    payload.append("question_id", formData.get("question_id"));
    payload.append("start_time", formData.get("start_time"));
    payload.append("tab_switch_count", formData.get("tab_switch_count"));
```
A **second**, separate `FormData` object is built here, rather than
reusing `formData` directly. This lets you rename fields on the way out —
e.g. reading the HTML input named `"idcard"` but sending it to the
backend under the key `"id_card_no"`, matching exactly what the FastAPI
endpoint's `Form(...)` parameter names expect.

```js
    selectedFiles.forEach(file => {
        payload.append("files", file);
    });
```
Appends **every** file in your own tracked array under the same key name,
`"files"` — calling `.append()` multiple times with an identical key is
exactly how multiple files get sent under one field, matching FastAPI's
`files: List[UploadFile]` on the receiving end.

```js
    try {
        const response = await fetch(`${API_BASE}/submissions`, {
            method: "POST",
            body: payload
        });

        const result = await response.json();

        if (!response.ok) {
            alert(result.detail || "Submission failed. Please try again.");
            return;
        }
```
`{ method: "POST", body: payload }` — the options object telling `fetch`
to send a POST request with `payload` as its body (no need to manually set
a `Content-Type` header — the browser sets the correct
`multipart/form-data` header automatically when the body is a `FormData`
object). `result.detail || "..."` — falls back to a generic message if
the backend's response happens not to include a `detail` field for some
reason.

```js
        window.location.href = "success.html?name=" + encodeURIComponent(result.name);

    } catch (error) {
        console.log("Submission failed:", error);
        alert("Could not reach the server. Please try again shortly.");
    }
}
```
On success, redirects to the confirmation page, passing the participant's
name along as a URL parameter (read back out there via
`URLSearchParams`, same technique as reading `subject`/`class_level`
earlier in this same file).

```js
function preventQuestionCopying() {
    const questionEl = document.getElementById("question-text");
    if (!questionEl) return;

    questionEl.addEventListener("copy", (event) => event.preventDefault());
    questionEl.addEventListener("cut", (event) => event.preventDefault());
    questionEl.addEventListener("contextmenu", (event) => event.preventDefault());
    questionEl.addEventListener("selectstart", (event) => event.preventDefault());
}
```
`if (!questionEl) return;` — a defensive guard: if this element doesn't
exist on the current page for some reason, exit immediately rather than
crashing trying to call `.addEventListener` on `null`. Each listener
blocks one specific browser behavior (copying, cutting, right-click menu,
starting a text selection) on this element specifically — a deterrent
against casual copy-pasting, not real protection (a screenshot bypasses
all of this instantly).

```js
let tabSwitchCount = 0;

function trackTabSwitching() {
    const countField = document.getElementById("tab-switch-count");
    if (!countField) return;

    function registerSwitch() {
        tabSwitchCount += 1;
        countField.value = tabSwitchCount;
    }

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            registerSwitch();
        }
    });

    window.addEventListener("blur", registerSwitch);
}
```
- `registerSwitch` is a small helper defined *inside* `trackTabSwitching`
  — it only exists within this function's scope, since nothing outside
  needs to call it directly.
- `"visibilitychange"` fires whenever the tab becomes hidden or visible
  again (switching tabs, minimizing). `document.hidden` is `true`
  specifically when it just became hidden — checking this avoids counting
  the moment the tab becomes visible again as a second switch.
- `"blur"` on `window` fires when the whole browser window loses focus
  (e.g. alt-tabbing to a different application) — a second detection
  method covering a case `visibilitychange` sometimes misses.

```js
function init() {
    const form = document.querySelector(".answer-form");
    if (form) {
        form.addEventListener("submit", handleSubmit);
    } else {
        console.log("answer-form not found in the page yet.");
    }
    preventQuestionCopying();
    trackTabSwitching();
    loadQuestion();
}
```
A single entry-point function that wires up everything this page needs.
Checking `if (form)` before attaching the submit listener avoids a crash
if, for some reason, the form element isn't present.

```js
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
```
This handles a timing edge case: if this script tag is encountered
*before* the browser has finished parsing the HTML below it,
`document.readyState` will still be `"loading"` — in that case, wait for
the `"DOMContentLoaded"` event (fired once the full HTML is parsed)
before running `init()`. If the HTML was already fully parsed by the time
this script runs (e.g. the `<script>` tag sits at the very end of
`<body>`, as yours does), `readyState` is no longer `"loading"`, so
`init()` just runs immediately instead. This makes the script safe to
include regardless of exactly where in the page it's placed.

Built by **Animesh Sitoula** · DA2 · Trinity Computer Council
