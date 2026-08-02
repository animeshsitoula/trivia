const API_BASE = "https://trivia-ehw5.onrender.com";

const params = new URLSearchParams(window.location.search);
const subject = params.get("subject");
const classLevel = params.get("class_level");

let selectedFiles = [];

function renderFileList() {
    const listEl = document.getElementById("file-list");
    listEl.innerHTML = "";

    selectedFiles.forEach((file, index) => {
        const chip = document.createElement("div");
        chip.className = "file-chip";
        chip.innerHTML = `<span></span><span class="remove-file">×</span>`;
        chip.querySelector("span").textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;

        chip.querySelector(".remove-file").addEventListener("click", () => {
            selectedFiles.splice(index, 1);
            renderFileList();
        });

        listEl.appendChild(chip);
    });
}

document.getElementById("file-upload").addEventListener("change", function () {
    for (const file of this.files) {
        selectedFiles.push(file);
    }
    renderFileList();
    this.value = "";
});

async function loadQuestion() {
    if (!subject || !classLevel) {
        document.getElementById("question-text").textContent =
            "No subject or class selected. Please go back and choose again.";
        document.getElementById("week-label").textContent = "No subject selected";
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE}/questions/active?subject=${encodeURIComponent(subject)}&class_level=${encodeURIComponent(classLevel)}`
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
        document.getElementById("question-id").value = data.question_id;
        document.getElementById("start-time").value = data.start_time;

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

    if (selectedFiles.length === 0) {
        alert("Please attach at least one file.");
        return;
    }

    const form = event.target;
    const formData = new FormData(form);

    const payload = new FormData();
    payload.append("name", formData.get("name"));
    payload.append("email", formData.get("email"));
    payload.append("id_card_no", formData.get("idcard"));
    payload.append("week_id", formData.get("week_id"));
    payload.append("subject", formData.get("subject"));
    payload.append("question_id", formData.get("question_id"));
    payload.append("start_time", formData.get("start_time"));
    payload.append("tab_switch_count", formData.get("tab_switch_count"));

    selectedFiles.forEach(file => {
        payload.append("files", file);
    });

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

        window.location.href = "success.html?name=" + encodeURIComponent(result.name);

    } catch (error) {
        console.log("Submission failed:", error);
        alert("Could not reach the server. Please try again shortly.");
    }
}

function preventQuestionCopying() {
    const questionEl = document.getElementById("question-text");
    if (!questionEl) return;

    questionEl.addEventListener("copy", (event) => event.preventDefault());
    questionEl.addEventListener("cut", (event) => event.preventDefault());
    questionEl.addEventListener("contextmenu", (event) => event.preventDefault());
    questionEl.addEventListener("selectstart", (event) => event.preventDefault());
}

let tabSwitchCount = 0;

function trackTabSwitching() {
    const countField = document.getElementById("tab-switch-count");
    if (!countField) return;

    function registerSwitch() {
        tabSwitchCount += 1;
        countField.value = tabSwitchCount;
    }

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            registerSwitch();
        }
    });

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
