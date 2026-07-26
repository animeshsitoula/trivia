"""
Activates a week and scaffolds its question folder.

Sets is_active=True on the chosen week's row in the database
(and False on every other week, so only one is ever active at
a time), then makes sure questions/week_XX/ exists with a
placeholder .txt per subject.

Usage:
    python setup_week.py          # activates week 1 (default)
    python setup_week.py 3        # activates week 3 instead
"""
from database import Base, engine, SessionLocal, Week
from dotenv import load_dotenv
import os
import sys

load_dotenv()

# Default week to activate. Override by running:
#   python setup_week.py 2
WEEK_NUMBER = int(sys.argv[1]) if len(sys.argv) > 1 else 1

PLACEHOLDER_QUESTIONS = {
    "physics": "TODO: add this week's physics question here.",
    "maths": "TODO: add this week's maths question here. "
             "LaTeX is supported: \\(x^2\\) inline, $$\\frac{a}{b}$$ display.",
    "computer": "TODO: add this week's computer science question here.",
    "chemistry": "TODO: add this week's chemistry question here.",
    "biology": "TODO: add this week's biology question here.",
}


def main():
    # 1. Make sure tables exist (safe to re-run)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # 2. Deactivate every week, then activate the chosen one
    db.query(Week).update({Week.is_active: False})

    week = db.query(Week).filter(Week.week_number == WEEK_NUMBER).first()
    if week is None:
        week = Week(week_number=WEEK_NUMBER, is_active=True)
        db.add(week)
    else:
        week.is_active = True

    db.commit()
    db.close()

    # 3. Scaffold the question folder for that week
    folder = os.path.join("questions", f"week_{WEEK_NUMBER:02d}")
    os.makedirs(folder, exist_ok=True)

    for subject, placeholder in PLACEHOLDER_QUESTIONS.items():
        path = os.path.join(folder, f"{subject}.txt")
        # Never overwrite a question you've already written
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(placeholder)

    print(f"Week {WEEK_NUMBER} is now active.")
    print(f"Question files ready in: {folder}/")


if __name__ == "__main__":
    main()