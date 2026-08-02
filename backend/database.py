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
    id = Column(Integer, primary_key=True, autoincrement=True)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    subject = Column(String, nullable=False)
    class_level = Column(String, nullable=True)   # NEW
    question_text = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("week_id", "subject", "class_level"),)

class SubmissionFile(Base):
    __tablename__ = "submission_files"
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False)
    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    id_card_no = Column(String, nullable=False, unique=True)
    week_id = Column(Integer, ForeignKey("weeks.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)   # NEW
    subject = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    score = Column(Integer, nullable=True)
    tab_switch_count = Column(Integer, nullable=False, default=0)
    flagged = Column(Boolean, nullable=False, default=False)
    start_time = Column(DateTime, nullable=True)      # NEW
    submit_time = Column(DateTime, nullable=True)     # NEW
    time_taken = Column(Integer, nullable=True)        # NEW, in seconds
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    file_path = Column(String, nullable=True)
