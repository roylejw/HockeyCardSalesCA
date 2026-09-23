"""Store adapters. Each yields raw listings: {title, url, price, regular, in_stock, image}.
Prices are CAD floats; `regular` is the store's own "was" price when it shows one."""
import html
import re
import time

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) HockeyCardSalesBot/1.0 (+https://hockeycardsales.app)"}
DELAY = 1.5  # default seconds between requests to the same store; stores.json can override
MAX_PAGES = 40
# Variant options that sell part of a box, or several boxes, rather than one box (English and French).
NOT_A_BOX_VARIANT = re.compile(
    r"\b(packs?|paquets?|cases?|caisses?|inner|display|demi|half|singles?|bo[iî]tes? \d+|\d+ ?(box|boxes|bo[iî]tes))\b", re.I)


def _get(url, params):
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def shopify(store):
    base = f"https://{store['domain']}"
    seen = set()
    for coll in store.get("collections", ["all"]):
        path = "/products.json" if coll == "all" else f"/collections/{coll}/products.json"
        for page in range(1, MAX_PAGES + 1):
            products = _get(base + path, {"limit": 250, "page": page}).get("products", [])
            if not products:
                break
            for p in products:
                img = (p.get("images") or [{}])[0].get("src")
                for v in p.get("variants", []):
                    if NOT_A_BOX_VARIANT.search(v.get("title") or ""):
                        continue  # e.g. a "Pack" or "Inner Case" option on a hobby box listing
                    title = p["title"]
                    if v.get("title") and v["title"] != "Default Title":
                        title = f"{title} - {v['title']}"
                    url = f"{base}/products/{p['handle']}"
                    if len(p.get("variants", [])) > 1:
                        url += f"?variant={v['id']}"
                    if url in seen:
                        continue
                    seen.add(url)
                    price = float(v["price"])
                    cmp = float(v["compare_at_price"]) if v.get("compare_at_price") else None
                    yield {
                        "title": title, "url": url, "price": price,
                        "regular": cmp if cmp and cmp > price else None,
                        "in_stock": bool(v.get("available")), "image": img,
                    }
            time.sleep(store.get("delay", DELAY))


def woocommerce(store):
    base = f"https://{store['domain']}/wp-json/wc/store/v1/products"
    seen = set()
    for term in store.get("search", ["hockey"]):
        for page in range(1, MAX_PAGES + 1):
            products = _get(base, {"search": term, "per_page": 100, "page": page})
            if not products:
                break
            for p in products:
                if p["permalink"] in seen:
                    continue
                seen.add(p["permalink"])
                pr = p.get("prices") or {}
                scale = 10 ** int(pr.get("currency_minor_unit", 2))
                if not pr.get("price"):
                    continue
                price = int(pr["price"]) / scale
                regular = int(pr["regular_price"]) / scale if pr.get("regular_price") else None
                yield {
                    "title": html.unescape(p["name"]), "url": p["permalink"], "price": price,
                    "regular": regular if regular and regular > price else None,
                    "in_stock": bool(p.get("is_in_stock")),
                    "image": (p.get("images") or [{}])[0].get("src"),
                }
            if len(products) < 100:
                break
            time.sleep(store.get("delay", DELAY))


ADAPTERS = {"shopify": shopify, "woocommerce": woocommerce}
