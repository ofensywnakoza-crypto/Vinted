"""Lokalny serwer HTTP - odbiera dane z rozszerzenia Brave i zapisuje do bazy.

Uruchom: python sync_server.py
"""
from datetime import date

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import COOKIE_SERVER_HOST, COOKIE_SERVER_PORT
from core import database

database.init_db()

app = Flask(__name__)
CORS(app, origins=["https://www.vinted.pl", "https://www.vinted.com", "chrome-extension://*"])


@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "service": "vinted-manager-sync"})


@app.route("/sync/listings", methods=["POST"])
def sync_listings():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items", [])
    source = payload.get("source", "unknown")

    saved = 0
    for item in items:
        try:
            if not item.get("title"):
                continue
            existing = None
            if item.get("external_id"):
                from core.database import get_conn
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT * FROM listings WHERE external_id = ?",
                        (item["external_id"],),
                    ).fetchone()
                    existing = dict(row) if row else None

            listing_data = {
                "external_id": item.get("external_id"),
                "title": item.get("title"),
                "brand": item.get("brand"),
                "category": item.get("category"),
                "size": item.get("size"),
                "list_price": item.get("list_price"),
                "current_views": item.get("current_views", 0),
                "current_likes": item.get("current_likes", 0),
                "status": item.get("status", "Wystawiony"),
                "vinted_url": item.get("vinted_url"),
                "photo_url": item.get("photo_url"),
                "last_synced": date.today().isoformat(),
            }
            if not existing or not existing.get("listed_date"):
                listing_data["listed_date"] = date.today().isoformat()

            listing_id = database.upsert_listing(listing_data)

            if item.get("current_views") is not None:
                database.save_snapshot(
                    listing_id,
                    int(item.get("current_views", 0)),
                    int(item.get("current_likes", 0)),
                    item.get("list_price"),
                )
            saved += 1
        except Exception as exc:
            print(f"[sync] blad pojedynczego item: {exc}")

    print(f"[sync] {source}: zapisano {saved}/{len(items)} ogloszen")
    return jsonify({"saved": saved, "total": len(items)})


@app.route("/sync/listing", methods=["POST"])
def sync_listing():
    item = request.get_json(silent=True) or {}
    if not item.get("title"):
        return jsonify({"error": "brak tytulu"}), 400

    listing_data = {
        "external_id": item.get("external_id"),
        "title": item.get("title"),
        "brand": item.get("brand"),
        "category": item.get("category"),
        "size": item.get("size"),
        "list_price": item.get("list_price"),
        "current_views": item.get("current_views", 0),
        "current_likes": item.get("current_likes", 0),
        "vinted_url": item.get("vinted_url"),
        "photo_url": item.get("photo_url"),
        "last_synced": date.today().isoformat(),
    }
    listing_id = database.upsert_listing(listing_data)
    database.save_snapshot(
        listing_id,
        int(item.get("current_views", 0)),
        int(item.get("current_likes", 0)),
        item.get("list_price"),
    )
    print(f"[sync] ogloszenie: {item.get('title')[:40]} "
          f"(V={item.get('current_views')}, L={item.get('current_likes')})")
    return jsonify({"saved": True, "id": listing_id})


if __name__ == "__main__":
    print("=" * 50)
    print("  VINTED MANAGER - Serwer synchronizacji")
    print("=" * 50)
    print(f"Nasluchuje: http://{COOKIE_SERVER_HOST}:{COOKIE_SERVER_PORT}")
    print("Rozszerzenie Brave wysyla tu dane z Vinted.")
    print("Zostaw to okno otwarte.")
    print("=" * 50)
    app.run(host=COOKIE_SERVER_HOST, port=COOKIE_SERVER_PORT, debug=False)
