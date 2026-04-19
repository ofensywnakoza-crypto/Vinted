from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import csv
import os
from datetime import datetime
from collections import defaultdict
from typing import Optional

app = FastAPI(
    title="Vinted Sales API",
    description="API do analizy sprzedaży produktów na Vinted",
    version="1.0.0",
)

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "products.csv")


def load_products() -> list[dict]:
    if not os.path.exists(CSV_PATH):
        raise HTTPException(status_code=500, detail=f"Plik CSV nie istnieje: {CSV_PATH}")

    products = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["cena_zakupu"] = float(row["cena_zakupu"])
                row["cena_sprzedazy"] = float(row["cena_sprzedazy"])
                row["zysk"] = row["cena_sprzedazy"] - row["cena_zakupu"]
                row["marza_procent"] = (row["zysk"] / row["cena_zakupu"]) * 100
                row["data_sprzedazy"] = row["data_sprzedazy"] or None
            except (ValueError, KeyError):
                continue
            products.append(row)
    return products


@app.get("/")
def root():
    return {"message": "Vinted Sales API działa!", "endpoints": ["/stats", "/best-brands", "/recommendations"]}


@app.get("/stats")
def get_stats():
    """Ogólne statystyki sprzedaży: liczba produktów, średnia marża, podział sprzedane/niesprzedane."""
    products = load_products()

    sold = [p for p in products if p["status"] == "sprzedane"]
    unsold = [p for p in products if p["status"] == "niesprzedane"]

    avg_margin = sum(p["marza_procent"] for p in products) / len(products) if products else 0
    avg_margin_sold = sum(p["marza_procent"] for p in sold) / len(sold) if sold else 0
    total_profit = sum(p["zysk"] for p in sold)
    total_revenue = sum(p["cena_sprzedazy"] for p in sold)
    total_cost = sum(p["cena_zakupu"] for p in sold)

    return {
        "liczba_produktow_lacznie": len(products),
        "liczba_sprzedanych": len(sold),
        "liczba_niesprzedanych": len(unsold),
        "wskaznik_sprzedazy_procent": round(len(sold) / len(products) * 100, 2) if products else 0,
        "srednia_marza_procent": round(avg_margin, 2),
        "srednia_marza_sprzedanych_procent": round(avg_margin_sold, 2),
        "laczny_zysk_pln": round(total_profit, 2),
        "laczny_przychod_pln": round(total_revenue, 2),
        "laczny_koszt_zakupu_pln": round(total_cost, 2),
    }


@app.get("/best-brands")
def get_best_brands():
    """Top 5 marek wg łącznego zysku ze sprzedanych produktów."""
    products = load_products()
    sold = [p for p in products if p["status"] == "sprzedane"]

    brand_stats: dict[str, dict] = defaultdict(lambda: {
        "laczny_zysk": 0.0,
        "liczba_sprzedanych": 0,
        "laczny_przychod": 0.0,
        "srednia_marza_procent": 0.0,
        "_marze": [],
    })

    for p in sold:
        b = p["marka"]
        brand_stats[b]["laczny_zysk"] += p["zysk"]
        brand_stats[b]["liczba_sprzedanych"] += 1
        brand_stats[b]["laczny_przychod"] += p["cena_sprzedazy"]
        brand_stats[b]["_marze"].append(p["marza_procent"])

    result = []
    for brand, stats in brand_stats.items():
        result.append({
            "marka": brand,
            "laczny_zysk_pln": round(stats["laczny_zysk"], 2),
            "liczba_sprzedanych": stats["liczba_sprzedanych"],
            "laczny_przychod_pln": round(stats["laczny_przychod"], 2),
            "srednia_marza_procent": round(sum(stats["_marze"]) / len(stats["_marze"]), 2),
        })

    top5 = sorted(result, key=lambda x: x["laczny_zysk_pln"], reverse=True)[:5]
    return {"top_5_marek": top5}


@app.get("/recommendations")
def get_recommendations():
    """Rekomendacje: co sprzedaje się najlepiej i jakie produkty warto kupować."""
    products = load_products()
    sold = [p for p in products if p["status"] == "sprzedane"]
    unsold = [p for p in products if p["status"] == "niesprzedane"]

    # Najlepsze produkty wg zysku
    top_products = sorted(sold, key=lambda x: x["zysk"], reverse=True)[:5]

    # Kategorie (marki) z najwyższą stopą sprzedaży
    brand_total: dict[str, int] = defaultdict(int)
    brand_sold: dict[str, int] = defaultdict(int)
    for p in products:
        brand_total[p["marka"]] += 1
        if p["status"] == "sprzedane":
            brand_sold[p["marka"]] += 1

    brand_sell_rate = []
    for brand, total in brand_total.items():
        rate = brand_sold[brand] / total * 100
        brand_sell_rate.append({"marka": brand, "stopa_sprzedazy_procent": round(rate, 2), "sprzedane": brand_sold[brand], "lacznie": total})
    brand_sell_rate.sort(key=lambda x: x["stopa_sprzedazy_procent"], reverse=True)

    # Średnia marża produktów sprzedanych vs niesprzedanych
    avg_margin_sold = round(sum(p["marza_procent"] for p in sold) / len(sold), 2) if sold else 0
    avg_margin_unsold = round(sum(p["marza_procent"] for p in unsold) / len(unsold), 2) if unsold else 0

    # Przedziały cenowe z najlepszą sprzedażą
    price_buckets: dict[str, dict] = defaultdict(lambda: {"sprzedane": 0, "lacznie": 0})
    for p in products:
        price = p["cena_sprzedazy"]
        if price < 50:
            bucket = "do 50 zł"
        elif price < 100:
            bucket = "50–100 zł"
        elif price < 150:
            bucket = "100–150 zł"
        else:
            bucket = "powyżej 150 zł"
        price_buckets[bucket]["lacznie"] += 1
        if p["status"] == "sprzedane":
            price_buckets[bucket]["sprzedane"] += 1

    price_analysis = []
    for bucket, data in price_buckets.items():
        rate = data["sprzedane"] / data["lacznie"] * 100 if data["lacznie"] else 0
        price_analysis.append({
            "przedzial_cenowy": bucket,
            "stopa_sprzedazy_procent": round(rate, 2),
            "sprzedane": data["sprzedane"],
            "lacznie": data["lacznie"],
        })
    price_analysis.sort(key=lambda x: x["stopa_sprzedazy_procent"], reverse=True)

    return {
        "top_5_produktow_wg_zysku": [
            {
                "nazwa": p["nazwa"],
                "marka": p["marka"],
                "zysk_pln": round(p["zysk"], 2),
                "marza_procent": round(p["marza_procent"], 2),
            }
            for p in top_products
        ],
        "marki_wg_stopy_sprzedazy": brand_sell_rate,
        "analiza_przedzialow_cenowych": price_analysis,
        "wnioski": {
            "srednia_marza_sprzedanych": f"{avg_margin_sold}%",
            "srednia_marza_niesprzedanych": f"{avg_margin_unsold}%",
            "rekomendacja": (
                "Skup się na markach o stopie sprzedaży >80%. "
                "Produkty w przedziale cenowym z najwyższą stopą sprzedaży przynoszą najlepsze wyniki."
            ),
        },
    }
