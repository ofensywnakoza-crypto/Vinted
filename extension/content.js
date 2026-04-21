// Vinted Manager - content script
// Uruchamia sie na kazdej stronie Vinted i czyta dane.

const LOCAL_SERVER = "http://127.0.0.1:8765";

async function sendToLocal(endpoint, payload) {
  try {
    await fetch(`${LOCAL_SERVER}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    console.log("[Vinted Manager] lokalny serwer wylaczony - uruchom cookie_server.py");
  }
}

function getUserIdFromPage() {
  const match = location.pathname.match(/\/member\/(\d+)/);
  if (match) return match[1];
  const meta = document.querySelector('meta[name="user-id"]');
  return meta ? meta.content : null;
}

async function fetchUserItems(userId) {
  const url = `/api/v2/users/${userId}/items?page=1&per_page=100`;
  try {
    const resp = await fetch(url, { credentials: "include" });
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) {
    return null;
  }
}

async function fetchItemDetails(itemId) {
  try {
    const resp = await fetch(`/api/v2/items/${itemId}/details`, { credentials: "include" });
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) {
    return null;
  }
}

function extractListingFromCard(card) {
  try {
    const titleEl = card.querySelector('[data-testid*="description-title"]');
    const priceEl = card.querySelector('[data-testid*="price-text"]');
    const linkEl = card.querySelector('a[href*="/items/"]');
    const imgEl = card.querySelector('img');
    if (!titleEl || !linkEl) return null;

    const href = linkEl.getAttribute("href");
    const idMatch = href.match(/\/items\/(\d+)/);
    const externalId = idMatch ? idMatch[1] : href;

    const priceText = priceEl ? priceEl.textContent.replace(",", ".") : "";
    const priceMatch = priceText.match(/(\d+\.?\d*)/);
    const price = priceMatch ? parseFloat(priceMatch[1]) : null;

    return {
      external_id: externalId,
      title: titleEl.textContent.trim(),
      list_price: price,
      photo_url: imgEl ? imgEl.src : null,
      vinted_url: `https://www.vinted.pl${href}`,
    };
  } catch (e) {
    return null;
  }
}

async function scanClosetPage() {
  const cards = document.querySelectorAll('[data-testid^="product-item-id-"]');
  const items = [];
  cards.forEach(card => {
    const data = extractListingFromCard(card);
    if (data) items.push(data);
  });
  if (items.length > 0) {
    await sendToLocal("/sync/listings", { items, source: "closet_page" });
    console.log(`[Vinted Manager] Zsynchronizowano ${items.length} ogloszen`);
    showToast(`✓ Zsynchronizowano ${items.length} ogloszen`);
  }
}

async function scanItemPage() {
  const match = location.pathname.match(/\/items\/(\d+)/);
  if (!match) return;
  const itemId = match[1];
  const details = await fetchItemDetails(itemId);
  if (!details || !details.item) return;

  const item = details.item;
  const payload = {
    external_id: String(item.id),
    title: item.title,
    brand: item.brand,
    category: item.catalog_id ? String(item.catalog_id) : null,
    size: item.size_title,
    list_price: item.price ? parseFloat(item.price.amount) : null,
    current_views: item.view_count || 0,
    current_likes: item.favourite_count || 0,
    vinted_url: location.href,
    photo_url: item.photos && item.photos[0] ? item.photos[0].url : null,
  };
  await sendToLocal("/sync/listing", payload);
  console.log(`[Vinted Manager] Ogloszenie #${itemId}: ${item.view_count} wyswietlen, ${item.favourite_count} polubien`);
}

async function scanMyItems() {
  const userId = getUserIdFromPage();
  if (!userId) return;
  const data = await fetchUserItems(userId);
  if (!data || !data.items) return;

  const items = data.items.map(item => ({
    external_id: String(item.id),
    title: item.title,
    brand: item.brand_title,
    size: item.size_title,
    list_price: item.price ? parseFloat(item.price.amount) : null,
    current_views: item.view_count || 0,
    current_likes: item.favourite_count || 0,
    photo_url: item.photo ? item.photo.url : null,
    vinted_url: item.url,
    status: item.is_closed ? "Sprzedany" : "Wystawiony",
  }));
  await sendToLocal("/sync/listings", { items, source: "member_api" });
  showToast(`✓ Zsynchronizowano ${items.length} ogloszen`);
}

function showToast(text) {
  const existing = document.getElementById("vinted-manager-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.id = "vinted-manager-toast";
  toast.style.cssText = `
    position: fixed; bottom: 20px; right: 20px; z-index: 999999;
    background: #09B1BA; color: white; padding: 12px 20px;
    border-radius: 8px; font-family: sans-serif; font-size: 14px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-weight: 600;
  `;
  toast.textContent = text;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

async function main() {
  const path = location.pathname;
  if (/\/member\/\d+/.test(path)) {
    await scanMyItems();
  } else if (/\/items\/\d+/.test(path)) {
    await scanItemPage();
  } else if (path.startsWith("/wardrobe") || path === "/" || path.startsWith("/catalog")) {
    await scanClosetPage();
  }
}

setTimeout(main, 1500);

let lastPath = location.pathname;
setInterval(() => {
  if (location.pathname !== lastPath) {
    lastPath = location.pathname;
    setTimeout(main, 1500);
  }
}, 2000);
