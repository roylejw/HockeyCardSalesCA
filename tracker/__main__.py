"""Usage:
    python3 -m tracker scrape    # fetch prices from every enabled store
    python3 -m tracker build     # regenerate the site/ folder from the database
    python3 -m tracker run       # scrape + build
    python3 -m tracker serve     # view the site at http://localhost:8000
    python3 -m tracker reclassify  # re-apply classify.py rules to stored listings
"""
import html
import json
import re
import shutil
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
SITE_URL = "https://hockeycardsales.app"

# Everything that differs between the sport pages. Hockey stays at the site root so existing links work.
SPORTS = {
    "hockey": {
        "label": "Hockey", "base": "/", "hits_file": "hits.json", "brand": "Upper Deck",
        "page_title": "Hockey Card Sales – Upper Deck NHL Hobby, Blaster &amp; Tin Prices in Canada",
        "meta_desc": "Compare prices on Upper Deck NHL hobby boxes, blasters and tins at Canadian card shops. "
                     "Twice-daily price checks, sale alerts, and the top Young Guns in every box.",
        "tagline": "Upper Deck NHL hobby boxes, blasters &amp; tins at Canadian stores · prices in CAD",
        "search_hint": "Search e.g. Series 1, SP Authentic, Demidov…",
        "season_all": "All seasons", "season_word": "season",
        "rookies_label": "Popular Young Guns / rookies", "rookies_short": "Young Guns",
    },
    "baseball": {
        "label": "Baseball", "base": "/baseball/", "hits_file": "hits_baseball.json", "brand": "Topps",
        "page_title": "Baseball Card Sales – Topps &amp; Bowman Hobby, Blaster &amp; Tin Prices in Canada",
        "meta_desc": "Compare prices on Topps and Bowman baseball hobby boxes, blasters and tins at Canadian card "
                     "shops. Twice-daily price checks, sale alerts, and the top rookies and prospects in every box.",
        "tagline": "Topps &amp; Bowman MLB hobby boxes, blasters &amp; tins at Canadian stores · 2020 onward · prices in CAD",
        "search_hint": "Search e.g. Bowman Chrome, Series 1, Skenes…",
        "season_all": "All years", "season_word": "year",
        "rookies_label": "Key rookies / prospects", "rookies_short": "Top rookies",
    },
}
BOX_LABELS = {"Hobby": "Hobby Box", "Jumbo": "Hobby Jumbo Box", "Breaker's Delight": "Breaker's Delight Box",
              "Blaster": "Blaster Box", "Tin": "Tin"}
BOX_GROUPS = {"Jumbo": "Hobby", "Breaker's Delight": "Hobby"}  # these show under the "Hobby" filter


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
                lid = db.upsert_listing(conn, store["name"], item, info, ts)
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
    for l in conn.execute("SELECT id, title, product_key, sport FROM listings").fetchall():
        info = classify(l["title"])
        if not info:
            conn.execute("DELETE FROM prices WHERE listing_id = ?", (l["id"],))
            conn.execute("DELETE FROM listings WHERE id = ?", (l["id"],))
            removed += 1
        elif (info["key"], info["sport"]) != (l["product_key"], l["sport"]):
            conn.execute("UPDATE listings SET product_key = ?, sport = ? WHERE id = ?",
                         (info["key"], info["sport"], l["id"]))
            changed += 1
    conn.commit()
    print(f"Reclassified: {changed} re-keyed, {removed} removed")


def hits_for(hits, season, line):
    specific = hits["products"].get(f"{season}|{line}", {})
    return {
        "young_guns": specific.get("young_guns", []),
        "chase": specific.get("chase", []) + hits["lines"].get(line, []),
        "rookie_class": [] if specific else hits["seasons"].get(season, []),
        "note": specific.get("note"),
    }


def pct(old, new):
    return round((old - new) / old * 100, 1) if old and old > new else 0


def load_products(conn):
    """Current listings with price history and sale signals, grouped into products per sport."""
    since = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).isoformat()
    # A listing is current only if its store's latest successful run saw it.
    last_ok = {r["store"]: r["ts"] for r in conn.execute(
        "SELECT store, MAX(ts) ts FROM runs WHERE ok = 1 GROUP BY store")}

    grouped = {}
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
        grouped.setdefault((l["sport"], l["product_key"]), []).append({
            "store": l["store"], "url": l["url"], "title": l["title"], "image": l["image"],
            "price": cur["price"], "regular": cur["regular"], "in_stock": bool(cur["in_stock"]),
            "first_seen": l["first_seen"],
            "store_sale_pct": pct(cur["regular"], cur["price"]),
            "drop_pct": pct(earlier, cur["price"]) if earlier else 0,
            "previous_price": earlier,
            "high_90d": max(h["price"] for h in hist),
            "low_90d": min(h["price"] for h in hist),
            "history": [[h["ts"][:10], h["price"]] for h in hist],
        })

    hits = {s: json.loads((ROOT / "data" / cfg["hits_file"]).read_text()) for s, cfg in SPORTS.items()}
    products = {s: [] for s in SPORTS}
    for (sport, key), listings in grouped.items():
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
        name = (f"{season} Upper Deck {line}".replace("Upper Deck Upper Deck", "Upper Deck")
                if sport == "hockey" else f"{season} {line}")
        box_label = BOX_LABELS[box_type]
        slug = slugify(f"{name} {box_label}")
        products[sport].append({
            "sport": sport, "key": key, "season": season, "line": line, "box_type": box_type,
            "box_label": box_label, "box_group": BOX_GROUPS.get(box_type, box_type), "name": name,
            "listings": listings,
            "best_price": in_stock[0]["price"] if in_stock else None,
            "on_sale": any(x["on_sale"] for x in listings),
            "max_sale_pct": max((x["sale_pct"] for x in listings if x["on_sale"]), default=0),
            "hits": hits_for(hits[sport], season, line),
            "slug": slug, "path": f'{SPORTS[sport]["base"]}boxes/{slug}/',
        })
    for ps in products.values():
        ps.sort(key=lambda p: (p["season"], p["line"]), reverse=True)
    return products


def build():
    conn = db.connect()
    runs = [dict(r) for r in conn.execute(
        "SELECT store, ts, ok, listings, error FROM runs WHERE ts = (SELECT MAX(ts) FROM runs)")]
    checked = runs[0]["ts"] if runs else now()  # when prices were last scraped, not when the page was built
    products = load_products(conn)

    site = ROOT / "site"
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    shutil.copy(ROOT / "web" / "style.css", site / "style.css")
    template = (ROOT / "web" / "template.html").read_text()

    for sport, cfg in SPORTS.items():
        out = products[sport]
        per_store = {}
        for p in out:
            for l in p["listings"]:
                per_store[l["store"]] = per_store.get(l["store"], 0) + 1
        store_status = [{"store": r["store"], "ok": r["ok"], "error": r["error"], "listings": per_store.get(r["store"], 0)}
                        for r in runs if not r["ok"] or per_store.get(r["store"])]
        data = {"generated": now(), "checked": checked, "sport": sport, "products": out, "runs": store_status,
                "labels": {"season_all": cfg["season_all"], "rookies": cfg["rookies_label"],
                           "rookies_short": cfg["rookies_short"]}}
        folder = site / cfg["base"].strip("/") if cfg["base"] != "/" else site
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "data.json").write_text(json.dumps(data))
        fill = {
            "PAGE_TITLE": cfg["page_title"], "META_DESC": cfg["meta_desc"], "TAGLINE": cfg["tagline"],
            "CANONICAL": SITE_URL + cfg["base"], "SEARCH_HINT": cfg["search_hint"], "NAV": nav_html(sport),
            "BROWSE": browse_html(out),
        }
        page = template
        for k, v in fill.items():
            page = page.replace("{{" + k + "}}", v)
        page = page.replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
        (folder / "index.html").write_text(page)
        write_product_pages(site, out, checked, cfg)
        print(f"Built {cfg['label']:<8} — {len(out)} products, {sum(p['on_sale'] for p in out)} with sales")

    write_sitemap(site, [p for ps in products.values() for p in ps], checked)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", "and").replace("'", "")).strip("-")


def money(n):
    return f"${n:,.2f}" if n is not None else "—"


def nav_html(active):
    current = ' aria-current="page"'
    return "".join(f'<a href="{cfg["base"]}"{current if s == active else ""}>{cfg["label"]}</a>'
                   for s, cfg in SPORTS.items())


def browse_html(products):
    """Plain links to every product page, grouped by season, so search engines can crawl them."""
    by_season = {}
    for p in products:
        by_season.setdefault(p["season"], []).append(p)
    parts = []
    for season in sorted(by_season, reverse=True):
        items = "".join(
            f'<li><a href="{p["path"]}">{html.escape(p["name"])} {html.escape(p["box_label"])}</a></li>'
            for p in sorted(by_season[season], key=lambda p: (p["line"], p["box_type"])))
        parts.append(f"<details><summary>{season} ({len(by_season[season])})</summary><ul>{items}</ul></details>")
    return "".join(parts)


def listing_badges(l):
    if not l["in_stock"]:
        return "Out of stock"
    b = []
    if l["store_sale_pct"] >= SALE_MIN_PCT:
        b.append(f'−{round(l["store_sale_pct"])}% store sale')
    if l["drop_pct"] >= SALE_MIN_PCT:
        b.append(f'↓ {round(l["drop_pct"])}% price drop')
    if l["below_market_pct"]:
        b.append(f'{round(l["below_market_pct"])}% under other stores')
    return " · ".join(b)


def write_product_pages(site, products, checked, cfg):
    template = (ROOT / "web" / "product.html").read_text()
    esc = html.escape
    by_season = {}
    for p in products:
        by_season.setdefault(p["season"], []).append(p)
    for p in products:
        title = f'{p["name"]} {cfg["label"]} {p["box_label"]}'
        url = SITE_URL + p["path"]
        listings = p["listings"]
        in_stock = [l for l in listings if l["in_stock"]]
        best = in_stock[0] if in_stock else None
        h = p["hits"]
        names = [n.split(" (")[0] for n in (h["young_guns"] or h["rookie_class"])][:3]

        desc = f"Compare {title} prices at {len(listings)} Canadian store{'s' if len(listings) != 1 else ''}."
        if best:
            desc += f" Lowest in-stock price {money(best['price'])} CAD at {best['store']}."
        if names:
            desc += f" Top rookies: {', '.join(names)}."

        rows = "".join(
            f'<tr class="{"" if l["in_stock"] else "oos"}"><td><a href="{esc(l["url"])}" rel="nofollow noopener" target="_blank">'
            f'{esc(l["store"])}</a><br><span class="badge {"sale" if l["on_sale"] else "oos"}">{esc(listing_badges(l))}</span></td>'
            f'<td class="pr">{"<s>" + money(l["regular"]) + "</s>" if l["regular"] else ""}{money(l["price"])}</td></tr>'
            for l in listings)

        def section(label, items):
            return f"<h3>{label}</h3><ul>{''.join(f'<li>{esc(i)}</li>' for i in items)}</ul>" if items else ""
        hits_html = (section(cfg["rookies_label"], h["young_guns"]) +
                     section("Rookie class to chase", h["rookie_class"]) +
                     section("Top hits in this product", h["chase"]) +
                     (f'<p class="sub"><em>{esc(h["note"])}</em></p>' if h["note"] else "")) or \
            '<p class="sub">No hit information for this product yet.</p>'

        related = "".join(f'<a href="{o["path"]}">{esc(o["line"])} {esc(o["box_type"])}</a>'
                          for o in by_season[p["season"]] if o is not p)

        prices = [l["price"] for l in listings]
        schema = {
            "@context": "https://schema.org", "@type": "Product", "name": title,
            "brand": {"@type": "Brand", "name": cfg["brand"]}, "category": "Sports trading cards",
            "description": desc, "url": url,
            "offers": {"@type": "AggregateOffer", "priceCurrency": "CAD", "offerCount": len(listings),
                       "lowPrice": min(prices), "highPrice": max(prices),
                       "availability": "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock"},
        }
        image = next((l["image"] for l in listings if l["image"]), None)
        if image:
            schema["image"] = image
        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": f'{cfg["label"]} boxes', "item": SITE_URL + cfg["base"]},
            {"@type": "ListItem", "position": 2, "name": title, "item": url}]}

        fill = {
            "TITLE": esc(title), "DESC": esc(desc), "URL": url, "IMAGE": esc(image or ""),
            "IMG_TAG": f'<img src="{esc(image)}" alt="{esc(title)}">' if image else "",
            "BEST": money(best["price"]) if best else "Out of stock",
            "BEST_NOTE": f'lowest in-stock price · {esc(best["store"])}' if best else "no store has it in stock right now",
            "SALE": '<span class="badge sale">On sale</span>' if p["on_sale"] else "",
            "BOX_TYPE": esc(p["box_label"]), "SEASON": p["season"], "SEASON_WORD": cfg["season_word"],
            "ROWS": rows, "HITS": hits_html, "RELATED": related, "UPDATED": checked[:10],
            "NAV": nav_html(p["sport"]), "SPORT": cfg["label"], "SPORT_BASE": cfg["base"],
            "TAGLINE": cfg["tagline"],
            "SCHEMA": json.dumps(schema).replace("</", "<\\/"), "CRUMBS": json.dumps(crumbs),
        }
        out = template
        for k, v in fill.items():
            out = out.replace("{{" + k + "}}", str(v))
        d = site / p["path"].strip("/")
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(out)


def write_sitemap(site, products, checked):
    day = checked[:10]
    urls = [SITE_URL + cfg["base"] for cfg in SPORTS.values()] + [SITE_URL + p["path"] for p in products]
    body = "".join(f"<url><loc>{u}</loc><lastmod>{day}</lastmod></url>" for u in urls)
    (site / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>')
    (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")


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
