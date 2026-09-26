const API_BASE = "https://trivia-ehw5.onrender.com";

document.getElementById("login-form").addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("admin-username-input").value;
    const password = document.getElementById("admin-password-input").value;

    const errorBox = document.getElementById("login-error");
    const errorText = document.getElementById("login-error-text");
    errorBox.hidden = true;

    const payload = new FormData();
    payload.append("username", username);
    payload.append("password", password);

    try {
        const response = await fetch(`${API_BASE}/admin/login`, {
            method: "POST",
            body: payload
        });

        const result = await response.json();

        if (!response.ok) {
            errorText.textContent = result.detail || "Incorrect username or password.";
            errorBox.hidden = false;
            return;
        }

        // Store the admin secret for this browser tab's session only --
        // sessionStorage clears automatically when the tab is closed,
        // unlike localStorage which would persist indefinitely.
        sessionStorage.setItem("admin_secret", result.secret);

        window.location.href = "dashboard.html";

    } catch (error) {
        console.log("Login failed:", error);
        errorText.textContent = "Could not reach the server. Please try again shortly.";
        errorBox.hidden = false;
    }
});