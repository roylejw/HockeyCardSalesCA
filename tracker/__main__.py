"""Usage:
    python3 -m tracker scrape    # fetch prices from every enabled store
    python3 -m tracker build     # regenerate site/index.html from the database
    python3 -m tracker run       # scrape + build
    python3 -m tracker serve     # view the site at http://localhost:8000
    python3 -m tracker reclassify  # re-apply classify.py rules to stored listings
"""
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db
from .classify import classify
from .scrapers import ADAPTERS

ROOT = Path(__file__).resolve().parent.parent
SALE_MIN_PCT = 5          # ignore discounts smaller than this
BELOW_MARKET_PCT = 10     # flag listings this far under the median of other stores
HISTORY_DAYS = 90


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def scrape():
    stores = json.loads((ROOT / "config" / "stores.json").read_text())["stores"]
    conn = db.connect()
    ts = now()
    for store in stores:
        if not store.get("enabled", True):
            continue
        kept = 0
        try:
            for item in ADAPTERS[store["platform"]](store):
                info = classify(item["title"])
                if not info or item["price"] <= 0:  # $0 = unpriced placeholder
                    continue
                lid = db.upsert_listing(conn, store["name"], item, info["key"], ts)
                db.record_price(conn, lid, item, ts)
                kept += 1
            conn.execute("INSERT INTO runs VALUES (?, ?, 1, ?, NULL)", (ts, store["name"], kept))
            print(f"  {store['name']:<24} {kept:>3} boxes")
        except Exception as e:  # one broken store shouldn't stop the others
            conn.execute("INSERT INTO runs VALUES (?, ?, 0, ?, ?)", (ts, store["name"], kept, str(e)[:300]))
            print(f"  {store['name']:<24} FAILED: {e}")
        conn.commit()
    conn.close()


def reclassify():
    conn = db.connect()
    changed = removed = 0
    for l in conn.execute("SELECT id, title, product_key FROM listings").fetchall():
        info = classify(l["title"])
        if not info:
            conn.execute("DELETE FROM prices WHERE listing_id = ?", (l["id"],))
            conn.execute("DELETE FROM listings WHERE id = ?", (l["id"],))
            removed += 1
        elif info["key"] != l["product_key"]:
            conn.execute("UPDATE listings SET product_key = ? WHERE id = ?", (info["key"], l["id"]))
            changed += 1
    conn.commit()
    print(f"Reclassified: {changed} re-keyed, {removed} removed")


def hits_for(hits, season, line):
    specific = hits["products"].get(f"{season}|{line}", {})
    return {
        "young_guns": specific.get("young_guns", []),
        "chase": specific.get("chase", []) + hits["lines"].get(line, []),
        "rookie_class": [] if specific.get("young_guns") else hits["seasons"].get(season, []),
        "note": specific.get("note"),
    }


def pct(old, new):
    return round((old - new) / old * 100, 1) if old and old > new else 0


def build():
    conn = db.connect()
    hits = json.loads((ROOT / "data" / "hits.json").read_text())
    since = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).isoformat()

    # A listing is current only if its store's latest successful run saw it.
    last_ok = {r["store"]: r["ts"] for r in conn.execute(
        "SELECT store, MAX(ts) ts FROM runs WHERE ok = 1 GROUP BY store")}
    runs = [dict(r) for r in conn.execute(
        "SELECT store, ts, ok, listings, error FROM runs WHERE ts = (SELECT MAX(ts) FROM runs)")]

    products = {}
    for l in conn.execute("SELECT * FROM listings"):
        if l["last_seen"] != last_ok.get(l["store"]):
            continue
        hist = [dict(h) for h in conn.execute(
            "SELECT ts, price, regular, in_stock FROM prices WHERE listing_id = ? AND ts >= ? ORDER BY ts",
            (l["id"], since))]
        if not hist:
            continue
        cur = hist[-1]
        prev_prices = [h["price"] for h in hist[:-1]]
        earlier = next((p for p in reversed(prev_prices) if p != cur["price"]), None)
        listing = {
            "store": l["store"], "url": l["url"], "title": l["title"], "image": l["image"],
            "price": cur["price"], "regular": cur["regular"], "in_stock": bool(cur["in_stock"]),
            "first_seen": l["first_seen"],
            "store_sale_pct": pct(cur["regular"], cur["price"]),
            "drop_pct": pct(earlier, cur["price"]) if earlier else 0,
            "previous_price": earlier,
            "high_90d": max(h["price"] for h in hist),
            "low_90d": min(h["price"] for h in hist),
            "history": [[h["ts"][:10], h["price"]] for h in hist],
        }
        products.setdefault(l["product_key"], []).append(listing)

    out = []
    for key, listings in products.items():
        season, line, box_type = key.split("|")
        for li in listings:
            others = [o["price"] for o in listings if o is not li and o["in_stock"]]
            li["below_market_pct"] = pct(statistics.median(others), li["price"]) if len(others) >= 2 else 0
            if li["below_market_pct"] < BELOW_MARKET_PCT:
                li["below_market_pct"] = 0
            li["sale_pct"] = max(li["store_sale_pct"], li["drop_pct"], li["below_market_pct"])
            li["on_sale"] = li["in_stock"] and li["sale_pct"] >= SALE_MIN_PCT
        listings.sort(key=lambda x: (not x["in_stock"], x["price"]))
        in_stock = [x for x in listings if x["in_stock"]]
        out.append({
            "key": key, "season": season, "line": line, "box_type": box_type,
            "name": f"{season} Upper Deck {line}".replace("Upper Deck Upper Deck", "Upper Deck"),
            "listings": listings,
            "best_price": in_stock[0]["price"] if in_stock else None,
            "on_sale": any(x["on_sale"] for x in listings),
            "max_sale_pct": max((x["sale_pct"] for x in listings if x["on_sale"]), default=0),
            "hits": hits_for(hits, season, line),
        })
    out.sort(key=lambda p: (p["season"], p["line"]), reverse=True)

    data = {"generated": now(), "products": out, "runs": runs}
    site = ROOT / "site"
    site.mkdir(exist_ok=True)
    (site / "data.json").write_text(json.dumps(data))
    html = (ROOT / "web" / "template.html").read_text()
    payload = json.dumps(data).replace("</", "<\\/")
    (site / "index.html").write_text(html.replace("/*__DATA__*/null", payload))
    print(f"Built site/index.html — {len(out)} products, "
          f"{sum(p['on_sale'] for p in out)} with sales")


def serve():
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site"))
    print("Serving on http://localhost:8000  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler).serve_forever()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd in ("scrape", "run"):
        print("Scraping stores…")
        scrape()
    if cmd in ("build", "run"):
        build()
    if cmd == "serve":
        serve()
    if cmd == "reclassify":
        reclassify()
        build()
    if cmd not in ("scrape", "build", "run", "serve", "reclassify"):
        print(__doc__)
