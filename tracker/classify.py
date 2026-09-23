"""Decide whether a store listing is a tracked sealed box, and normalise it to a product key so the
same box can be compared across stores:
  hockey   — Upper Deck NHL hobby / blaster boxes and tins, keyed like "2025-26|Series 1|Hobby"
  baseball — Topps / Bowman MLB boxes and tins from 2020 on, keyed like "2024|Bowman Chrome|Hobby"
"""
import html
import re

# Product lines Upper Deck publishes under the NHL licence. Order matters: more specific first.
LINES = [
    (r"o[\s-]?ph?ee[\s-]?chee platinum|\bopc platinum", "O-Pee-Chee Platinum"),
    (r"o[\s-]?ph?ee[\s-]?chee|\bopc\b", "O-Pee-Chee"),
    (r"parkhurst champions", "Parkhurst Champions"),
    (r"parkhurst", "Parkhurst"),
    (r"series (1|one|i)\b", "Series 1"),
    (r"series (2|two|ii)\b", "Series 2"),
    (r"extended", "Extended Series"),
    (r"sp authentic", "SP Authentic"),
    (r"sp game used", "SP Game Used"),
    (r"\bspx\b", "SPx"),
    (r"artifacts", "Artifacts"),
    (r"black diamond", "Black Diamond"),
    (r"\bthe cup\b", "The Cup"),
    (r"trilogy", "Trilogy"),
    (r"ultimate collection", "Ultimate Collection"),
    (r"\bpremier\b", "Premier"),
    (r"\bmvp\b", "MVP"),
    (r"synergy", "Synergy"),
    (r"allure", "Allure"),
    (r"credentials", "Credentials"),
    (r"chronology", "Chronology"),
    (r"clear cut", "Clear Cut"),
    (r"engrained", "Engrained"),
    (r"stature", "Stature"),
    (r"tim hortons", "Tim Hortons"),
    (r"metal universe", "SkyBox Metal Universe"),
    (r"fleer ultra|\bultra\b", "Fleer Ultra"),
    (r"\bice\b", "Ice"),
    (r"bruins centennial", "Boston Bruins Centennial"),
    (r"e-?x\s?2000", "E-X 2000"),
    (r"sp signature edition legends", "SP Signature Edition Legends"),
    (r"\bsp\b", "SP"),
]
UD_BRAND = re.compile(r"upper deck|\bud\b|" + "|".join(p for p, _ in LINES[:4]))

# Non-NHL leagues / international products the user doesn't want.
EXCLUDE_LEAGUE = re.compile(
    r"\b(ahl|pwhl|chl|ohl|whl|qmjhl|ncaa|collegiate|team canada|hockey canada|juniors?|"
    r"world juniors?|women'?s|olympics?|4 nations|memorial cup)\b"
)
# Things that mention a box but aren't a single sealed hobby box, blaster or tin.
EXCLUDE_FORMAT = re.compile(
    r"\bcase\b|\b\d+\s*-?\s*box(es)?\b|\bbreak\b|\bspot\b|random (team|player)|"
    r"acrylic|holder|display|protector|storage|binder|sleeve|toploader|empty|\bsingle\b|"
    r"\bhobby packs?\b|\bblaster pack\b|\bpack only\b|\blot of\b|\bbooster\b|gravity feed|"
    r"\bmega\b(?!\s+tins?\b)|\bhanger\b|\bvalue\b|\bstarter\b|\bmini tin\b"
)
SEASON_FULL = re.compile(r"\b(20\d\d)\s*[-/]\s*(20)?(\d\d)\b")
SEASON_SHORT = re.compile(r"\b(\d\d)\s*[-/]\s*(\d\d)\b")
YEAR = re.compile(r"\b(20[2-3]\d)\b")


def normalise(text):
    text = html.unescape(text)  # WooCommerce sends names like "Allen &#038; Ginter"
    return re.sub(r"[‐-―]", "-", text.lower()).replace("’", "'")


def box_type_of(t, sport):
    """Tin / Blaster / Hobby, plus baseball's Jumbo and Breaker's Delight hobby variants, which
    sell at very different prices and so must not be compared with a regular hobby box."""
    if re.search(r"\btins?\b", t):
        return "Tin"
    if "blaster" in t:
        return "Blaster"
    if sport == "baseball":
        if re.search(r"breaker'?s delight", t):
            return "Breaker's Delight"
        if "jumbo" in t:
            return "Jumbo"
    if "hobby" in t and not ("box" not in t and re.search(r"\bpack\b", t)):
        return "Hobby"
    return None


def season_of(t, line=None):
    m = SEASON_FULL.search(t)
    if m:
        return f"{m.group(1)}-{m.group(3)}"
    m = SEASON_SHORT.search(t)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return f"20{m.group(1)}-{m.group(2)}"
    # Some stores name flagship sets by release year ("2026 Series 2"). Series 1 comes out in the
    # autumn at the start of a season; Series 2 and Extended come out in the year it ends.
    m = YEAR.search(t)
    if m and line in ("Series 1", "Series 2", "Extended Series"):
        y = int(m.group(1))
        start = y if line == "Series 1" else y - 1
        return f"{start}-{(start + 1) % 100:02d}"
    return None


def line_from_title(t):
    """Fallback for lines not in LINES: the words between "upper deck" and "hockey"."""
    m = re.search(r"upper deck\s+(.+?)\s+(nhl\s+)?hockey", t)
    words = (m.group(1) if m else "").replace("'", "").replace("skybox", "").replace("nhl", "").split()
    words = [w for w in words if not SEASON_FULL.fullmatch(w) and not YEAR.fullmatch(w)]
    if not words:
        return "Upper Deck"
    keep_upper = {"sp", "spx", "e-x", "ud"}
    return " ".join(w.upper() if w in keep_upper else w.capitalize() for w in words)


def classify_hockey(t):
    if "hockey" not in t and "nhl" not in t:
        return None
    if not UD_BRAND.search(t):
        return None
    if EXCLUDE_LEAGUE.search(t) or EXCLUDE_FORMAT.search(t):
        return None
    box_type = box_type_of(t, "hockey")
    if not box_type:
        return None
    line = next((name for pat, name in LINES if re.search(pat, t)), None) or line_from_title(t)
    season = season_of(t, line)
    if not season:
        return None  # other single-year titles are almost always Team Canada / event products
    return {
        "sport": "hockey", "season": season, "line": line, "box_type": box_type,
        "key": f"{season}|{line}|{box_type}",
        "name": f"{season} Upper Deck {line}" if line != "Upper Deck" else f"{season} Upper Deck",
    }


# ---------------------------------------------------------------- baseball

BASEBALL_FIRST_YEAR = 2020

# Topps (incl. Bowman) baseball lines. Order matters: most specific first.
BASEBALL_LINES = [
    (r"bowman chrome sapphire", "Bowman Chrome Sapphire"),
    (r"bowman draft sapphire", "Bowman Draft Sapphire"),
    (r"bowman draft", "Bowman Draft"),
    (r"bowman'?s best", "Bowman's Best"),
    (r"bowman sterling", "Bowman Sterling"),
    (r"bowman platinum", "Bowman Platinum"),
    (r"bowman inception", "Bowman Inception"),
    (r"bowman chrome", "Bowman Chrome"),
    (r"bowman", "Bowman"),
    (r"stadium club chrome", "Topps Stadium Club Chrome"),
    (r"stadium club", "Topps Stadium Club"),
    (r"allen (&|and) ginter chrome", "Topps Allen & Ginter Chrome"),
    (r"allen (&|and) ginter|\ba ?& ?g\b", "Topps Allen & Ginter"),
    (r"gypsy queen", "Topps Gypsy Queen"),
    (r"heritage high number", "Topps Heritage High Number"),
    (r"heritage", "Topps Heritage"),
    (r"chrome update", "Topps Chrome Update"),
    (r"chrome sapphire", "Topps Chrome Sapphire"),
    (r"chrome black", "Topps Chrome Black"),
    (r"cosmic chrome", "Topps Cosmic Chrome"),
    (r"chrome platinum", "Topps Chrome Platinum Anniversary"),
    (r"chrome.*logofractor|logofractor", "Topps Chrome Logofractor"),
    (r"chrome.*ben baller|ben baller", "Topps Chrome Ben Baller"),
    (r"chrome.*sonic|sonic", "Topps Chrome Sonic"),
    (r"chrome", "Topps Chrome"),
    (r"series (2|two|ii)\b", "Topps Series 2"),
    (r"series (1|one|i)\b", "Topps Series 1"),
    (r"update", "Topps Update"),
    (r"finest", "Topps Finest"),
    (r"inception", "Topps Inception"),
    (r"museum", "Topps Museum Collection"),
    (r"tribute", "Topps Tribute"),
    (r"tier one", "Topps Tier One"),
    (r"dynasty", "Topps Dynasty"),
    (r"sterling", "Topps Sterling"),
    (r"transcendent", "Topps Transcendent"),
    (r"big league", "Topps Big League"),
    (r"archives? signature", "Topps Archives Signature Series"),
    (r"archives?\b", "Topps Archives"),
    (r"opening day", "Topps Opening Day"),
    (r"\bfire\b", "Topps Fire"),
    (r"gilded", "Topps Gilded Collection"),
    (r"pristine", "Topps Pristine"),
    (r"definitive", "Topps Definitive"),
    (r"triple threads", "Topps Triple Threads"),
    (r"five star", "Topps Five Star"),
    (r"clearly authentic", "Topps Clearly Authentic"),
    (r"pro debut", "Topps Pro Debut"),
    (r"holiday", "Topps Holiday"),
    (r"\bjapan\b", "Topps Japan Edition"),
]
# Lines that only exist for baseball, so a title without the word "baseball" is still safe.
BASEBALL_ONLY = {"Topps Series 1", "Topps Series 2", "Topps Update", "Topps Heritage", "Topps Heritage High Number",
                 "Topps Allen & Ginter", "Topps Gypsy Queen", "Bowman", "Bowman Chrome", "Bowman Draft",
                 "Topps Stadium Club", "Topps Archives"}
OTHER_SPORTS = re.compile(
    r"\b(football|nfl|basketball|nba|wnba|soccer|uefa|mls|premier league|f1|formula|ufc|wwe|hockey|nhl|"
    r"college|university|ncaa|bowman u|star wars|disney|marvel|pokemon|garbage pail|golf|tennis|racing|"
    r"nascar|wrestling)\b"
)
EXCLUDE_BASEBALL = re.compile(r"topps now|living set|complete set|factory set|team set|\bsticker|promotion")


def line_from_baseball_title(t, year):
    """Fallback: the words between the year and "baseball" (or the box type)."""
    m = re.search(rf"{year}\s+(.+?)\s+(mlb\s+)?(baseball|hobby|blaster|jumbo|tin|box)\b", t)
    words = (m.group(1) if m else "").replace("'", "").split()
    if not words:
        return None
    name = " ".join(w.capitalize() for w in words)
    return name if name.startswith(("Topps", "Bowman")) else f"Topps {name}"


def classify_baseball(t):
    if not re.search(r"\btopps\b|\bbowman", t):
        return None
    if OTHER_SPORTS.search(t) or EXCLUDE_BASEBALL.search(t) or EXCLUDE_FORMAT.search(t):
        return None
    m = YEAR.search(t)
    if not m or int(m.group(1)) < BASEBALL_FIRST_YEAR:
        return None
    year = m.group(1)
    box_type = box_type_of(t, "baseball")
    if not box_type:
        return None
    line = next((name for pat, name in BASEBALL_LINES if re.search(pat, t)), None)
    if not line:
        line = line_from_baseball_title(t, year)
        if not line:
            return None
    if not re.search(r"\bbaseball\b|\bmlb\b", t) and line not in BASEBALL_ONLY:
        return None  # e.g. "Topps Chrome Hobby Box" could be any sport
    return {
        "sport": "baseball", "season": year, "line": line, "box_type": box_type,
        "key": f"{year}|{line}|{box_type}", "name": f"{year} {line}",
    }


def classify(title):
    """Return {sport, season, line, box_type, key, name} or None if the listing isn't tracked."""
    t = normalise(title)
    return classify_hockey(t) or classify_baseball(t)
