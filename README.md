# Hockey Card Sales — Upper Deck NHL box price tracker (Canada)

Live at https://hockeycardsales.app

Tracks hobby and blaster box prices for Upper Deck NHL products at Canadian retailers,
flags sales, and shows the top hits / popular Young Guns for each product.

**Excluded:** AHL, PWHL, CHL/junior leagues, NCAA, Team Canada / Hockey Canada, Olympic
and other international products, and cases, packs, tins, breaks and accessories.

## Use it

```bash
python3 -m tracker run      # scrape every store, then build the site
python3 -m tracker serve    # open http://localhost:8000
```

Other commands: `scrape`, `build`, `reclassify` (re-apply filter rules to saved listings).
Run `python3 -m unittest tests.test_classify` after changing the filter rules.

Price history builds up over time, so run it daily (`scripts/daily.sh` has a cron example).
Price drops and the sparklines only appear after a few runs.

## How sales are detected

A listing counts as **on sale** (in stock, ≥5% off) when any of these is true:

| Badge | Meaning |
|---|---|
| **store sale** | The store shows a crossed-out regular price (Shopify `compare_at_price` / Woo `regular_price`) |
| **price drop** | The price is lower than the last different price we recorded |
| **under other stores** | ≥10% below the median in-stock price at 2+ other stores |
| **90-day low** | Cheapest this listing has been in 90 days |

## Files

| Path | What it is |
|---|---|
| `config/stores.json` | Stores to scrape. Add any Canadian **Shopify** or **WooCommerce** shop here — no code needed |
| `data/hits.json` | Curated top hits / Young Guns per product. Edit it to add new sets |
| `tracker/classify.py` | Rules for which listings count and how they're grouped |
| `tracker/scrapers.py` | Shopify + WooCommerce adapters (public product APIs) |
| `data/prices.db` | SQLite price history |
| `web/template.html` | The site; `site/index.html` is generated from it |

### Adding a store
Shopify: find a hockey collection URL like `https://shop.ca/collections/hockey-boxes` and add
`"collections": ["hockey-boxes"]` (or `["all"]` for small shops). WooCommerce: add
`"search": ["hockey"]`. Check it works with `python3 -m tracker run`.

### Not covered
Walmart.ca, Amazon.ca, Costco and Best Buy block automated requests. CloutsnChara (API
disabled) and Grizzly Sports Cards (custom platform) would each need a custom HTML scraper.
