const API_BASE = "http://127.0.0.1:8000";

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


loadActiveWeek();