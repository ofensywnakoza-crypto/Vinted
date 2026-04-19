const VINTED_DOMAIN = "www.vinted.pl";
const COOKIE_NAME = "_vinted_fr_session";
const SERVER_URL = "http://localhost:27182/cookie-sync";
const CHECK_INTERVAL_MS = 60 * 1000; // 1 minute

let lastSentValue = null;

async function getVintedCookie() {
  return new Promise((resolve) => {
    chrome.cookies.get({ url: `https://${VINTED_DOMAIN}`, name: COOKIE_NAME }, (cookie) => {
      resolve(cookie ? cookie.value : null);
    });
  });
}

async function syncCookie() {
  const value = await getVintedCookie();
  if (!value) return;
  if (value === lastSentValue) return;

  try {
    const resp = await fetch(SERVER_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookie: value }),
    });
    if (resp.ok) {
      lastSentValue = value;
      const ts = new Date().toLocaleTimeString("pl-PL");
      chrome.storage.local.set({ lastSync: ts, lastStatus: "ok" });
      console.log(`[VintedSync] Zsynchronizowano o ${ts}`);
    } else {
      chrome.storage.local.set({ lastStatus: "error" });
    }
  } catch {
    chrome.storage.local.set({ lastStatus: "offline" });
  }
}

// Run on install and on alarm
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("syncCookie", { periodInMinutes: 1 });
  syncCookie();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "syncCookie") syncCookie();
});

// Handle manual sync from popup
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action === "syncNow") {
    syncCookie().then(() => sendResponse({ done: true }));
    return true; // keep channel open for async response
  }
});

// Also sync when user visits vinted.pl
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (
    changeInfo.status === "complete" &&
    tab.url &&
    tab.url.includes(VINTED_DOMAIN)
  ) {
    syncCookie();
  }
});
