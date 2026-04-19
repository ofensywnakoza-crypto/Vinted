const dot  = document.getElementById("statusDot");
const text = document.getElementById("statusText");
const ts   = document.getElementById("lastSync");
const btn  = document.getElementById("syncBtn");

function applyStatus(status, lastSync) {
  dot.className = "dot " + (status || "unknown");
  if (status === "ok") {
    text.textContent = "Zsynchronizowano";
  } else if (status === "error") {
    text.textContent = "Blad serwera";
  } else if (status === "offline") {
    text.textContent = "Serwer offline";
  } else {
    text.textContent = "Brak danych";
  }
  ts.textContent = lastSync ? `Ostatnia sync: ${lastSync}` : "";
}

chrome.storage.local.get(["lastStatus", "lastSync"], (data) => {
  applyStatus(data.lastStatus, data.lastSync);
});

btn.addEventListener("click", () => {
  text.textContent = "Synchronizuje...";
  dot.className = "dot unknown";
  // Trigger background sync via message
  chrome.runtime.sendMessage({ action: "syncNow" }, () => {
    // Re-read status after a short delay
    setTimeout(() => {
      chrome.storage.local.get(["lastStatus", "lastSync"], (data) => {
        applyStatus(data.lastStatus, data.lastSync);
      });
    }, 2000);
  });
});
