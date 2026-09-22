"""Decide whether a store listing is an Upper Deck NHL blaster/hobby box, and normalise it
to a product key like "2025-26|Series 1|Hobby" so the same box can be compared across stores."""
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
# Things that mention "hobby box" but aren't a single sealed box.
EXCLUDE_FORMAT = re.compile(
    r"\bcase\b|\b\d+\s*-?\s*box(es)?\b|\bbreak\b|\bspot\b|random (team|player)|"
    r"acrylic|holder|display|protector|storage|binder|sleeve|toploader|empty|\bsingle\b|"
    r"\bhobby packs?\b|\bblaster pack\b|\bpack only\b|\blot of\b|\btin\b|\bbooster\b"
)
SEASON_FULL = re.compile(r"\b(20\d\d)\s*[-/]\s*(20)?(\d\d)\b")
SEASON_SHORT = re.compile(r"\b(\d\d)\s*[-/]\s*(\d\d)\b")


def normalise(text):
    return re.sub(r"[‐-―]", "-", text.lower())


def season_of(t):
    m = SEASON_FULL.search(t)
    if m:
        return f"{m.group(1)}-{m.group(3)}"
    m = SEASON_SHORT.search(t)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return f"20{m.group(1)}-{m.group(2)}"
    return None


def line_from_title(t):
    """Fallback for lines not in LINES: the words between "upper deck" and "hockey"."""
    m = re.search(r"upper deck\s+(.+?)\s+(nhl\s+)?hockey", t)
    words = (m.group(1) if m else "").replace("'", "").replace("skybox", "").replace("nhl", "").split()
    if not words:
        return "Upper Deck"
    keep_upper = {"sp", "spx", "e-x", "ud"}
    return " ".join(w.upper() if w in keep_upper else w.capitalize() for w in words)


def classify(title):
    """Return {season, line, box_type, key, name} or None if the listing isn't tracked."""
    t = normalise(title)
    if "hockey" not in t and "nhl" not in t:
        return None
    if not UD_BRAND.search(t):
        return None
    if EXCLUDE_LEAGUE.search(t) or EXCLUDE_FORMAT.search(t):
        return None
    if "blaster" in t:
        box_type = "Blaster"
    elif "hobby" in t and not ("box" not in t and re.search(r"\bpack\b", t)):
        box_type = "Hobby"
    else:
        return None
    season = season_of(t)
    if not season:
        return None  # single-year titles are almost always Team Canada / event products
    line = next((name for pat, name in LINES if re.search(pat, t)), None) or line_from_title(t)
    return {
        "season": season,
        "line": line,
        "box_type": box_type,
        "key": f"{season}|{line}|{box_type}",
        "name": f"{season} Upper Deck {line}" if line not in ("Upper Deck",) else f"{season} Upper Deck",
    }
