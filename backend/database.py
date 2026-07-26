"""
Database Configuration and Models

Database:
- PostgreSQL (hosted on Supabase)

ORM:
- SQLAlchemy

Contains:
- Database connection
- Tables:
    - Weeks
    - Questions
    - Submissions

Questions live in the `questions` table (one row per week+subject),
editable directly in Supabase's Table Editor. The active Week row
just tells the backend which week's questions to serve.

Configuration:
DATABASE_URL is read from an environment variable, not hardcoded.
Set it in a local .env file (see .env.example) and in Render's
Environment tab for the deployed version. Example value, from
Supabase -> Project Settings -> Database -> Connection string (URI):

    postgresql://postgres:YOUR-PASSWORD@db.xxxxxxxxxxxx.supabase.co:5432/postgres?sslmode=require
"""
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Boolean,
    DateTime,
    String,
    ForeignKey,
    UniqueConstraint
)

from sqlalchemy.orm import (
    sessionmaker,
    declarative_base
)

from datetime import datetime
from dotenv import load_dotenv
import os

# Loads variables from a local .env file, if one exists.
# On Render, environment variables are set directly in the
# dashboard, so this line is a harmless no-op there.
load_dotenv()

# --------------------------------------------------
# Database Configuration
# --------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to a .env file locally, "
        "or to Render's Environment tab when deployed."
    )

engine = create_engine(DATABASE_URL)

# Creates database sessions
SessionLocal = sessionmaker(
    bind=engine
)

# Base class for SQLAlchemy models
Base = declarative_base()

# --------------------------------------------------
# Week Table
#
# Stores weekly trivia information.
# Only one week should normally be marked active;
# that is what points the backend at questions/week_XX/
# --------------------------------------------------

class Week(Base):

    __tablename__ = "weeks"

    id = Column(
        Integer,
        primary_key=True
    )

    week_number = Column(
        Integer,
        unique=True,
        nullable=False
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=False
    )

# --------------------------------------------------
# Question Table
#
# Stores one row per (week, subject) question. Editable
# directly in Supabase's Table Editor -- no redeploy needed
# to change a question's wording.
# --------------------------------------------------

class Question(Base):
    __tablename__ = "questions"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    week_id = Column(
        Integer,
        ForeignKey("weeks.id"),
        nullable=False
    )

    # e.g. "physics", "maths", "computer", "chemistry", "biology"
    subject = Column(
        String,
        nullable=False
    )

    # Supports LaTeX: \(...\) inline, $$...$$ display (rendered
    # by MathJax on the frontend)
    question_text = Column(
        String,
        nullable=False
    )

    # Only one question per subject per week
    __table_args__ = (
        UniqueConstraint("week_id", "subject"),
    )

# --------------------------------------------------
# Submission Table
# Stores participant submission details.
# Uploaded answer files live in Supabase Storage
# (bucket configured via SUPABASE_BUCKET); file_path
# stores the path *within that bucket*, not a local path.
#
# id_card_no is globally unique -> one submission per
# person, ever, for the whole competition (not per week).
# --------------------------------------------------

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    name = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        nullable=False
    )

    # Unique ID card number
    # Prevents the same person submitting more than once,
    # across any week.
    id_card_no = Column(
        String,
        nullable=False,
        unique=True
    )

    week_id = Column(
        Integer,
        ForeignKey("weeks.id"),
        nullable=False
    )

    # Subject chosen (e.g. "physics"). Kept as a plain string here
    # (not a foreign key to questions.id) so a submission still
    # makes sense even if a question gets edited/deleted later.
    subject = Column(
        String,
        nullable=False
    )

    # Path to the answer file INSIDE the Supabase Storage
    # bucket, e.g. "Animesh_a82f91bc/3f9c1b2e.pdf"
    file_path = Column(
        String,
        nullable=False
    )

    # Filled later during checking
    score = Column(
        Integer,
        nullable=True
    )

    # How many times the answering tab lost focus/was switched
    # away from while this person was on answer.html. A signal
    # for manual review, not an automatic disqualification.
    tab_switch_count = Column(
        Integer,
        nullable=False,
        default=0
    )

    # Auto-set True when tab_switch_count crosses a threshold
    # (see main.py). Filter by this in Supabase's Table Editor
    # to review flagged submissions.
    flagged = Column(
        Boolean,
        nullable=False,
        default=False
    )

    submitted_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

# --------------------------------------------------
# Create tables automatically
# Runs when database.py is executed
# --------------------------------------------------

if __name__ == "__main__":
    try:
        connection = engine.connect()
        print(
            "Database connection successful"
        )
        connection.close()
    except Exception as e:

        print(
            "Database connection failed:",
            e
        )

    Base.metadata.create_all(
        bind=engine
    )