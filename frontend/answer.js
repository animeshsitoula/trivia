const API_BASE = "http://127.0.0.1:8000";

const params = new URLSearchParams(window.location.search);
const subject = params.get("subject");

async function loadQuestion() {
    if (!subject) {
        document.getElementById("question-text").textContent =
            "No subject selected. Please go back and choose one.";
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE}/questions/active?subject=${encodeURIComponent(subject)}`
        );

        if (!response.ok) {
            document.getElementById("question-text").textContent =
                "Could not load a question for this subject right now.";
            return;
        }

        const data = await response.json();

        document.getElementById("subject-name").textContent = data.subject;
        document.getElementById("question-ref").textContent = data.week;
        document.getElementById("question-text").textContent = data.question;

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

document.querySelector(".answer-form").addEventListener("submit", handleSubmit);

loadQuestion();