const statusEl = document.getElementById("status");

fetch("http://127.0.0.1:8765/ping")
  .then(r => r.ok ? r.json() : Promise.reject())
  .then(() => {
    statusEl.className = "status ok";
    statusEl.textContent = "✅ Polaczono z aplikacja Vinted Manager";
  })
  .catch(() => {
    statusEl.className = "status err";
    statusEl.textContent = "❌ Aplikacja nie jest uruchomiona. Odpal cookie_server.py";
  });

document.getElementById("open-app").addEventListener("click", () => {
  chrome.tabs.create({ url: "http://localhost:8501" });
});
