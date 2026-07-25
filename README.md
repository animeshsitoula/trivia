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
Built by **Animesh Sitoula** · DA2 · Trinity Computer Council
