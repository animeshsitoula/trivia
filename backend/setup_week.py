"""
One-off helper for local testing.

Run this once to:
1. Create the database tables (weeks, submissions)
2. Mark week 7 as the active week
3. Create the matching questions/week_07/ folder with sample
   question files for each subject

Usage:
    python setup_week.py
"""
from database import Base, engine, SessionLocal, Week
import os
import sys

# Default week to seed/activate. Override by running:
#   python setup_week.py 2
WEEK_NUMBER = int(sys.argv[1]) if len(sys.argv) > 1 else 1


# Question files support LaTeX for equations:
#   \( ... \)   -> inline math, e.g. \(x^2 + y^2 = r^2\)
#   $$ ... $$   -> centered display math, e.g. $$\frac{-b \pm \sqrt{b^2-4ac}}{2a}$$
# MathJax (loaded in answer.html) renders these automatically.

SAMPLE_QUESTIONS = {
    "physics": "A block slides down a frictionless incline of angle 30 degrees. "
               "Derive an expression for its acceleration and explain your reasoning.",
    "maths": "Solve for x using the quadratic formula:\n\n"
             "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
             "given the equation \\(2x^2 - 4x - 6 = 0\\). Show your working.",
    "computer": "Explain the difference between a stack and a queue, and give one real-world "
                "example of where each is used.",
    "chemistry": "Explain why noble gases are chemically unreactive in terms of electron configuration.",
    "biology": "Describe the process of osmosis and explain why it matters for plant cells.",
}


def main():
    # 1. Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # 2. Make sure only week 7 is active
    db.query(Week).update({Week.is_active: False})

    week = db.query(Week).filter(Week.week_number == WEEK_NUMBER).first()
    if week is None:
        week = Week(week_number=WEEK_NUMBER, is_active=True)
        db.add(week)
    else:
        week.is_active = True

    db.commit()
    db.close()

    # 3. Write sample question files
    folder = os.path.join("questions", f"week_{WEEK_NUMBER:02d}")
    os.makedirs(folder, exist_ok=True)

    for subject, question_text in SAMPLE_QUESTIONS.items():
        path = os.path.join(folder, f"{subject}.txt")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(question_text)

    print(f"Week {WEEK_NUMBER} is now active.")
    print(f"Question files ready in: {folder}/")


if __name__ == "__main__":
    main()