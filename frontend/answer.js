const API_BASE = "http://127.0.0.1:8000";

const params = new URLSearchParams(window.location.search);
const subject = params.get("subject");

async function loadQuestion() {
    if (!subject) {
        document.getElementById("question-text").textContent =
            "No subject selected. Please go back and choose one.";
        document.getElementById("week-label").textContent = "No subject selected";
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE}/questions/active?subject=${encodeURIComponent(subject)}`
        );

        if (!response.ok) {
            document.getElementById("question-text").textContent =
                "Could not load a question for this subject right now.";
            document.getElementById("week-label").textContent = "No active week found";
            return;
        }

        const data = await response.json();

        document.getElementById("subject-name").textContent = data.subject;
        document.getElementById("question-ref").textContent = data.week;
        document.getElementById("question-text").textContent = data.question;

        document.getElementById("week-label").textContent = `${data.week} — Live Now`;

        document.getElementById("week-id").value = data.week_id;
        document.getElementById("subject-field").value = subject;

        // Re-render any LaTeX in the question text (MathJax only
        // scans the page once on load, so new text needs a nudge)
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

async function handleSubmit(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);

    // Map the form's field names onto what the backend expects
    const payload = new FormData();
    payload.append("name", formData.get("name"));
    payload.append("email", formData.get("email"));
    payload.append("id_card_no", formData.get("idcard"));
    payload.append("week_id", formData.get("week_id"));
    payload.append("subject", formData.get("subject"));
    payload.append("tab_switch_count", formData.get("tab_switch_count"));
    payload.append("file", formData.get("answer-file"));

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

        window.location.href =
            "success.html?name=" + encodeURIComponent(result.name);

    } catch (error) {
        console.log("Submission failed:", error);
        alert("Could not reach the server. Please try again shortly.");
    }
}

// Makes the question text harder to casually copy: blocks
// copy/cut, right-click, and click-drag selection on this
// element specifically. Note: this is a deterrent, not real
// security -- a screenshot or DevTools defeats it instantly.
function preventQuestionCopying() {
    const questionEl = document.getElementById("question-text");
    if (!questionEl) return;

    questionEl.addEventListener("copy", (event) => event.preventDefault());
    questionEl.addEventListener("cut", (event) => event.preventDefault());
    questionEl.addEventListener("contextmenu", (event) => event.preventDefault());
    questionEl.addEventListener("selectstart", (event) => event.preventDefault());
}

// Tracks how many times this tab loses focus or is switched away
// from while answering -- a signal for manual review, not a hard
// block. Counts once the question has actually started loading,
// so opening the page itself doesn't count as a "switch".
let tabSwitchCount = 0;

function trackTabSwitching() {
    const countField = document.getElementById("tab-switch-count");
    if (!countField) return;

    function registerSwitch() {
        tabSwitchCount += 1;
        countField.value = tabSwitchCount;
    }

    // Fires when the tab is minimized, switched away from, or the
    // browser itself loses focus (e.g. switching to another app)
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            registerSwitch();
        }
    });

    // Extra safety net -- covers cases visibilitychange sometimes
    // misses, like clicking into a separate window on the same screen
    window.addEventListener("blur", registerSwitch);
}

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

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}