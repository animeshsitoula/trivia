-- Weeks table
CREATE TABLE weeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number INTEGER NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 0
);


-- Submissions table
-- Questions are NOT stored here / in any table -- they live as
-- text files under questions/week_<NN>/<subject>.txt
CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,
    email TEXT NOT NULL,

    -- Globally unique: one submission per person, ever
    id_card_no TEXT NOT NULL UNIQUE,

    week_id INTEGER NOT NULL,
    subject TEXT NOT NULL,

    file_path TEXT NOT NULL,

    score INTEGER,

    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (week_id)
    REFERENCES weeks(id)
);
