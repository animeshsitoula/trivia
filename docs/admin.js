/* ================================================================
   dashboard.js — Admin dashboard logic

   ASSUMED BACKEND ENDPOINTS (build these in main.py, all requiring
   the admin secret/session the same way /admin/close-week does):

   GET    /admin/weeks
       -> [{ id, week_number, is_active }, ...]

   GET    /admin/questions?week_id=&subject=
       -> [{ id, week_id, week_number, subject, class_level, question_text }, ...]

   POST   /admin/questions          (JSON body: week_id, subject, class_level, question_text)
       -> { id, ... }  (the created row)

   PUT    /admin/questions/{id}     (JSON body: week_id, subject, class_level, question_text)
       -> { id, ... }  (the updated row)

   DELETE /admin/questions/{id}
       -> { message: "deleted" }

   GET    /admin/submissions?week_id=&subject=&flagged=&ungraded=
       -> [{ id, name, id_card_no, subject, time_taken, tab_switch_count,
              score, files: [{ id, original_filename, download_url }] }, ...]

   PATCH  /admin/submissions/{id}/score   (JSON body: { score })
       -> { message: "updated" }

   GET    /admin/stats
       -> { active_week, total_submissions, ungraded, flagged }

   Every admin fetch call below sends the stored secret via a header
   (X-Admin-Secret) — adjust ADMIN_HEADER_NAME/adminSecret below to
   match however your backend actually expects to receive it.
   ================================================================ */

const API_BASE = "https://trivia-ehw5.onrender.com";

// Wherever admin-login.js stores the secret after a successful login —
// adjust the key name if yours differs.
const adminSecret = sessionStorage.getItem("admin_secret");

if (!adminSecret) {
    // No secret in this session at all -- bounce back to login.
    window.location.href = "login.html";
}

function adminHeaders(extra = {}) {
    return Object.assign({ "X-Admin-Secret": adminSecret }, extra);
}

// ----------------------------------------------------------------
// Modal open/close helpers
// ----------------------------------------------------------------

function openModal(modalId) {
    document.getElementById(modalId).removeAttribute("hidden");
}

function closeModal(modalId) {
    document.getElementById(modalId).setAttribute("hidden", "");
}

document.getElementById("question-modal-close").addEventListener("click", function () {
    closeModal("question-modal");
});

document.getElementById("question-form-cancel").addEventListener("click", function () {
    closeModal("question-modal");
});

document.getElementById("delete-cancel-btn").addEventListener("click", function () {
    closeModal("delete-confirm-modal");
});

document.querySelectorAll(".dash-modal-overlay").forEach(function (overlay) {
    overlay.addEventListener("click", function (event) {
        if (event.target === overlay) {
            overlay.setAttribute("hidden", "");
        }
    });
});

// ----------------------------------------------------------------
// Sidebar navigation — show one view, hide the others
// ----------------------------------------------------------------

const allViews = ["overview-view", "questions-view", "submissions-view"];

function showView(viewId) {
    allViews.forEach(function (id) {
        document.getElementById(id).hidden = (id !== viewId);
    });

    document.querySelectorAll(".dash-nav-item").forEach(function (btn) {
        btn.classList.toggle("active", btn.dataset.view === viewId);
    });

    // Lazily load each view's data the first time it's opened, and
    // refresh it every time it's revisited.
    if (viewId === "overview-view") loadStats();
    if (viewId === "questions-view") loadQuestions();
    if (viewId === "submissions-view") loadSubmissions();
}

document.querySelectorAll(".dash-nav-item").forEach(function (btn) {
    btn.addEventListener("click", function () {
        showView(btn.dataset.view);
    });
});

// ----------------------------------------------------------------
// Logout
// ----------------------------------------------------------------

document.getElementById("dash-logout-btn").addEventListener("click", function () {
    sessionStorage.removeItem("admin_secret");
    window.location.href = "login.html";
});

// ----------------------------------------------------------------
// Shared: populate the week dropdowns (filters + the question form)
// ----------------------------------------------------------------

let cachedWeeks = [];

async function loadWeeksIntoDropdowns() {
    try {
        const response = await fetch(`${API_BASE}/admin/weeks`, {
            headers: adminHeaders()
        });

        if (!response.ok) {
            console.log("Failed to load weeks, status:", response.status);
            return;
        }

        cachedWeeks = await response.json();

        const dropdownIds = [
            "questions-week-filter",
            "submissions-week-filter",
            "question-form-week"
        ];

        dropdownIds.forEach(function (id) {
            const select = document.getElementById(id);
            const isFormField = id === "question-form-week";

            // Keep the first placeholder option, rebuild the rest
            const placeholder = select.querySelector("option");
            select.innerHTML = "";
            select.appendChild(placeholder);

            cachedWeeks.forEach(function (week) {
                const option = document.createElement("option");
                option.value = week.id;
                option.textContent = `Week ${String(week.week_number).padStart(2, "0")}` +
                    (week.is_active ? " (active)" : "");
                select.appendChild(option);
            });
        });

    } catch (error) {
        console.log("Failed to load weeks:", error);
    }
}

// ----------------------------------------------------------------
// Overview stats
// ----------------------------------------------------------------

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/admin/stats`, {
            headers: adminHeaders()
        });

        if (!response.ok) {
            console.log("Failed to load stats, status:", response.status);
            return;
        }

        const data = await response.json();

        document.getElementById("stat-active-week").textContent =
            data.active_week != null ? `Week ${String(data.active_week).padStart(2, "0")}` : "—";
        document.getElementById("stat-total-submissions").textContent = data.total_submissions ?? "—";
        document.getElementById("stat-ungraded").textContent = data.ungraded ?? "—";
        document.getElementById("stat-flagged").textContent = data.flagged ?? "—";

    } catch (error) {
        console.log("Failed to load stats:", error);
    }
}

// ----------------------------------------------------------------
// Questions — list, add, edit, delete
// ----------------------------------------------------------------

async function loadQuestions() {
    const tbody = document.getElementById("questions-table-body");
    tbody.innerHTML = '<tr><td colspan="5" class="dash-table-empty">Loading questions…</td></tr>';

    const weekId = document.getElementById("questions-week-filter").value;
    const subject = document.getElementById("questions-subject-filter").value;

    const params = new URLSearchParams();
    if (weekId) params.append("week_id", weekId);
    if (subject) params.append("subject", subject);

    try {
        const response = await fetch(`${API_BASE}/admin/questions?${params.toString()}`, {
            headers: adminHeaders()
        });

        if (!response.ok) {
            tbody.innerHTML = '<tr><td colspan="5" class="dash-table-empty">Could not load questions.</td></tr>';
            return;
        }

        const questions = await response.json();

        if (questions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="dash-table-empty">No questions match these filters.</td></tr>';
            return;
        }

        tbody.innerHTML = "";

        questions.forEach(function (q) {
            const row = document.createElement("tr");

            row.innerHTML = `
                <td>Week ${String(q.week_number).padStart(2, "0")}</td>
                <td></td>
                <td>Class ${q.class_level ?? "—"}</td>
                <td><span class="dash-question-preview"></span></td>
                <td class="dash-row-actions">
                    <button type="button" class="dash-btn-icon" data-action="edit">Edit</button>
                    <button type="button" class="dash-btn-danger" data-action="delete">Delete</button>
                </td>
            `;

            // Use textContent for anything derived from stored data,
            // even though subject/question_text are your own content --
            // cheap habit to keep, costs nothing here.
            row.children[1].textContent = q.subject;
            row.querySelector(".dash-question-preview").textContent = q.question_text;

            row.querySelector('[data-action="edit"]').addEventListener("click", function () {
                openEditQuestionModal(q);
            });

            row.querySelector('[data-action="delete"]').addEventListener("click", function () {
                openDeleteConfirm(q.id);
            });

            tbody.appendChild(row);
        });

    } catch (error) {
        console.log("Failed to load questions:", error);
        tbody.innerHTML = '<tr><td colspan="5" class="dash-table-empty">Could not reach the server.</td></tr>';
    }
}

document.getElementById("questions-week-filter").addEventListener("change", loadQuestions);
document.getElementById("questions-subject-filter").addEventListener("change", loadQuestions);

function openEditQuestionModal(question) {
    document.getElementById("question-form-id").value = question.id;
    document.getElementById("question-form-week").value = question.week_id;
    document.getElementById("question-form-subject").value = question.subject;
    document.getElementById("question-form-class").value = question.class_level ?? "";
    document.getElementById("question-form-text").value = question.question_text;
    document.getElementById("question-modal-title").textContent = "Edit Question";

    openModal("question-modal");
}

document.getElementById("open-add-question-btn").addEventListener("click", function () {
    document.getElementById("question-form").reset();
    document.getElementById("question-form-id").value = "";
    document.getElementById("question-modal-title").textContent = "Add Question";

    openModal("question-modal");
});

document.getElementById("question-form").addEventListener("submit", async function (event) {
    event.preventDefault();

    const formData = new FormData(event.target);
    const questionId = formData.get("id");

    const payload = {
        week_id: parseInt(formData.get("week_id"), 10),
        subject: formData.get("subject"),
        class_level: formData.get("class_level"),
        question_text: formData.get("question_text")
    };

    const isEdit = Boolean(questionId);
    const url = isEdit
        ? `${API_BASE}/admin/questions/${questionId}`
        : `${API_BASE}/admin/questions`;

    try {
        const response = await fetch(url, {
            method: isEdit ? "PUT" : "POST",
            headers: adminHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (!response.ok) {
            alert(result.detail || "Could not save this question.");
            return;
        }

        closeModal("question-modal");
        loadQuestions();

    } catch (error) {
        console.log("Failed to save question:", error);
        alert("Could not reach the server. Please try again.");
    }
});

let pendingDeleteId = null;

function openDeleteConfirm(questionId) {
    pendingDeleteId = questionId;
    openModal("delete-confirm-modal");
}

document.getElementById("delete-confirm-btn").addEventListener("click", async function () {
    if (pendingDeleteId === null) return;

    try {
        const response = await fetch(`${API_BASE}/admin/questions/${pendingDeleteId}`, {
            method: "DELETE",
            headers: adminHeaders()
        });

        if (!response.ok) {
            const result = await response.json();
            alert(result.detail || "Could not delete this question.");
        } else {
            loadQuestions();
        }

    } catch (error) {
        console.log("Failed to delete question:", error);
        alert("Could not reach the server. Please try again.");
    } finally {
        pendingDeleteId = null;
        closeModal("delete-confirm-modal");
    }
});

// ----------------------------------------------------------------
// Submissions — list, filter, score, download files
// ----------------------------------------------------------------

async function loadSubmissions() {
    const tbody = document.getElementById("submissions-table-body");
    tbody.innerHTML = '<tr><td colspan="7" class="dash-table-empty">Loading submissions…</td></tr>';

    const weekId = document.getElementById("submissions-week-filter").value;
    const subject = document.getElementById("submissions-subject-filter").value;
    const flaggedOnly = document.getElementById("flagged-only-filter").checked;
    const ungradedOnly = document.getElementById("ungraded-only-filter").checked;

    const params = new URLSearchParams();
    if (weekId) params.append("week_id", weekId);
    if (subject) params.append("subject", subject);
    if (flaggedOnly) params.append("flagged", "true");
    if (ungradedOnly) params.append("ungraded", "true");

    try {
        const response = await fetch(`${API_BASE}/admin/submissions?${params.toString()}`, {
            headers: adminHeaders()
        });

        if (!response.ok) {
            tbody.innerHTML = '<tr><td colspan="7" class="dash-table-empty">Could not load submissions.</td></tr>';
            return;
        }

        const submissions = await response.json();

        if (submissions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="dash-table-empty">No submissions match these filters.</td></tr>';
            return;
        }

        tbody.innerHTML = "";

        submissions.forEach(function (s) {
            const row = document.createElement("tr");

            row.innerHTML = `
                <td></td>
                <td></td>
                <td></td>
                <td>${s.time_taken != null ? s.time_taken + "s" : "—"}</td>
                <td><span class="dash-pill ${s.flagged ? "dash-pill--flagged" : ""}"></span></td>
                <td>
                    <input type="number" class="dash-score-input" min="0" data-submission-id="${s.id}">
                </td>
                <td class="files-cell"></td>
            `;

            row.children[0].textContent = s.name;
            row.children[1].textContent = s.id_card_no;
            row.children[2].textContent = s.subject;

            const tabSwitchPill = row.querySelector(".dash-pill");
            tabSwitchPill.textContent = s.tab_switch_count;

            const scoreInput = row.querySelector(".dash-score-input");
            if (s.score != null) {
                scoreInput.value = s.score;
            }

            const filesCell = row.querySelector(".files-cell");
            (s.files || []).forEach(function (file) {
                const link = document.createElement("a");
                link.href = file.download_url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.className = "dash-file-link";
                link.textContent = file.original_filename;
                filesCell.appendChild(link);
            });

            scoreInput.addEventListener("change", function () {
                saveScore(s.id, scoreInput.value);
            });

            tbody.appendChild(row);
        });

    } catch (error) {
        console.log("Failed to load submissions:", error);
        tbody.innerHTML = '<tr><td colspan="7" class="dash-table-empty">Could not reach the server.</td></tr>';
    }
}

async function saveScore(submissionId, scoreValue) {
    try {
        const response = await fetch(`${API_BASE}/admin/submissions/${submissionId}/score`, {
            method: "PATCH",
            headers: adminHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ score: parseInt(scoreValue, 10) })
        });

        if (!response.ok) {
            const result = await response.json();
            alert(result.detail || "Could not save this score.");
            return;
        }

        showToast("Score saved");

    } catch (error) {
        console.log("Failed to save score:", error);
        alert("Could not reach the server. Please try again.");
    }
}

[
    "submissions-week-filter",
    "submissions-subject-filter",
    "flagged-only-filter",
    "ungraded-only-filter"
].forEach(function (id) {
    document.getElementById(id).addEventListener("change", loadSubmissions);
});

// ----------------------------------------------------------------
// Small toast notification (score saved, etc.)
// ----------------------------------------------------------------

function showToast(message) {
    const existing = document.querySelector(".dash-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "dash-toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(function () {
        toast.remove();
    }, 2500);
}

// ----------------------------------------------------------------
// Init
// ----------------------------------------------------------------

function init() {
    loadWeeksIntoDropdowns();
    showView("overview-view");
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}