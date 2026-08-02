const API_BASE = "https://trivia-ehw5.onrender.com";

async function loadActiveWeek() {
    const label = document.getElementById("week-label");

    try {
        const response = await fetch(`${API_BASE}/week/active`);

        if (!response.ok) {
            label.textContent = "No active week right now";
            return;
        }

        const data = await response.json();
        label.textContent = `${data.week} — Live Now`;

    } catch (error) {
        console.log("Failed to load active week:", error);
        label.textContent = "Could not load week info";
    }
}

document.querySelectorAll(".choose-link").forEach(function (link) {
    link.addEventListener("click", function (event) {
        event.preventDefault();   // stop the direct navigation

        const targetHref = link.getAttribute("href");   // e.g. "answer.html?subject=physics"
        pendingHref = targetHref;                          // remember which subject was clicked
        document.getElementById("class-modal").style.display = "flex";
    });
});

let pendingHref = null;

document.querySelectorAll(".modal-choice").forEach(function (btn) {
    btn.addEventListener("click", function () {
        const chosenClass = btn.dataset.class;
        window.location.href = pendingHref + "&class_level=" + encodeURIComponent(chosenClass);
    });
});


loadActiveWeek();
