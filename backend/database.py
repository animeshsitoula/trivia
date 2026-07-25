"""
Database Configuration and Models

Database:
- SQLite

ORM:
- SQLAlchemy

Contains:
- Database connection
- Tables:
    - Weeks
    - Submissions

Note on questions:
Questions are NOT stored in the database. They live as plain text
files on disk, one file per subject, inside a folder named after the
week number:

    questions/
        week_07/
            physics.txt
            maths.txt
            computer.txt
            chemistry.txt
            biology.txt

The active Week row just tells the backend which "week_XX" folder to
read from. This makes it trivial to update a week's questions by
editing/replacing a text file instead of touching the database.
"""
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Boolean,
    DateTime,
    String,
    ForeignKey
)

from sqlalchemy.orm import (
    sessionmaker,
    declarative_base
)

from datetime import datetime
import os

# --------------------------------------------------
# Create uploads folder if it does not exist
# Database file will be stored here
# --------------------------------------------------

os.makedirs(
    "uploads",
    exist_ok=True
)

# --------------------------------------------------
# Database Configuration
# --------------------------------------------------

DATABASE_URL = "sqlite:///./uploads/trivia.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)

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
# Submission Table
# Stores participant submission details
# Uploaded answer files are stored on the filesystem
# (see UPLOAD_FOLDER in main.py) and their path is
# stored here for reference.
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

    # Subject chosen (e.g. "physics"). Questions live in
    # files, so there is no questions.id to reference.
    subject = Column(
        String,
        nullable=False
    )

    # Location of uploaded answer file
    file_path = Column(
        String,
        nullable=False
    )

    # Filled later during checking
    score = Column(
        Integer,
        nullable=True
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
