"""
Fetch live open CFPs for major CS conferences.

Primary source: HuggingFace ai-deadlines (official curated YAML per venue).
CORE ranks: local cache (core_rankings_cache.csv) with hardcoded fallbacks.
Security venues (NDSS, CCS, IEEE S&P): PapersWithCode ai-deadlines YAML supplement.

Usage:
  python conference_live.py              # one-shot refresh (open + upcoming events)
  python conference_live.py --watch       # refresh on an interval (default 1 hour)
  python conference_live.py --watch --interval 300  # every 5 minutes while testing
  python conference_live.py --open-only   # strict: only CFPs with future deadlines
  python conference_live.py --no-pwc     # HF only (faster); skip PapersWithCode merge
"""

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT_DIR = Path(__file__).resolve().parent

CSV_PATH = ROOT_DIR / "live_open_cfps.csv"
PUBLIC_CSV_PATH = ROOT_DIR.parent / "frontend" / "public" / "live_open_cfps.csv"
META_PATH = ROOT_DIR / "live_open_cfps.meta.json"
CORE_CACHE_PATH = ROOT_DIR / "core_rankings_cache.csv"

# Avoid stale CDN/proxy caches when polling for “live” updates.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Academic CFP Bot)",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

HF_API_DIR = (
    "https://huggingface.co/api/spaces/huggingface/"
    "ai-deadlines/tree/main/src/data/conferences"
)
HF_RAW_BASE = (
    "https://huggingface.co/spaces/huggingface/"
    "ai-deadlines/raw/main/src/data/conferences/"
)
PWC_DEADLINES = (
    "https://raw.githubusercontent.com/paperswithcode/"
    "ai-deadlines/gh-pages/_data/conferences.yml"
)

TODAY = date.today()
CURRENT_YEAR = TODAY.year
# Keep current year through two years ahead (e.g. 2026–2028 in 2026).
ALLOWED_YEARS = {CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2}
DEFAULT_WATCH_INTERVAL_SEC = 3600  # hourly by default — 6h often looks “stuck”

SEARCH_DOMAINS = []  # no domain filtering; keep all fields, all topics

# PapersWithCode ai-deadlines “sub” field → coarse topic bucket
PWC_SUB_TO_DOMAIN = {
    "ML": "machine learning",
    "CV": "computer vision",
    "NLP": "natural language processing",
    "SP": "speech processing",
    "DM": "data science",
    "KR": "knowledge representation",
    "RO": "robotics",
    "AP": "machine learning",
    "FL": "machine learning",
    "IR": "data science",
    "CG": "computer vision",
}

TAG_TO_DOMAIN = {
    "machine-learning": "machine learning",
    "ml": "machine learning",
    "deep-learning": "machine learning",
    "computer-vision": "computer vision",
    "cv": "computer vision",
    "nlp": "natural language processing",
    "natural-language-processing": "natural language processing",
    "security": "cyber security",
    "privacy": "cyber security",
    "data-mining": "data science",
    "dm": "data science",
    "web": "data science",
    "information-retrieval": "data science",
    "ai": "artificial intelligence",
    "artificial-intelligence": "artificial intelligence",
}

# Curated seed list: major CS conferences NOT covered by HuggingFace AI Deadlines.
# Tuple: (acronym, full_title, year, deadline_str, ev_start, ev_end, location, topics, url, publisher, core_rank)
STATIC_SEEDS = [
    # ── Security / Privacy ──
    ("IEEE S&P",  "IEEE Symposium on Security and Privacy",                2027, "2026-08-15", "2027-05-24", "2027-05-28", "San Francisco, USA",   "cyber security",          "https://sp2027.ieee-security.org/",                        "IEEE",          "A*"),
    ("USENIX Security", "USENIX Security Symposium",                        2026, "2026-02-07", "2026-08-10", "2026-08-14", "Seattle, USA",         "cyber security",          "https://www.usenix.org/conference/usenixsecurity26",       "USENIX",        "A*"),
    ("CCS",       "ACM Conference on Computer and Communications Security", 2026, "2026-05-08", "2026-10-19", "2026-10-23", "Salt Lake City, USA",  "cyber security",          "https://www.sigsac.org/ccs/CCS2026/",                     "ACM",           "A*"),
    ("NDSS",      "Network and Distributed System Security Symposium",      2027, "2026-08-01", "2027-02-22", "2027-02-26", "San Diego, USA",       "cyber security",          "https://www.ndss-symposium.org/",                         "Internet Society","A*"),
    # ── Databases ──
    ("VLDB",      "Very Large Data Bases",                                  2026, "2026-04-01", "2026-09-01", "2026-09-05", "Singapore",            "data science",            "https://vldb.org/2026/",                                   "VLDB Endowment","A*"),
    ("SIGMOD",    "ACM SIGMOD International Conference on Management of Data",2026,"2025-11-01","2026-06-22","2026-06-27", "Toronto, Canada",      "data science",            "https://2026.sigmod.org/",                                 "ACM",           "A*"),
    ("ICDE",      "IEEE International Conference on Data Engineering",       2027, "2026-10-01", "2027-05-17", "2027-05-20", "TBD",                  "data science",            "https://icde2027.github.io/",                              "IEEE",          "A*"),
    # ── Software Engineering ──
    ("ICSE",      "International Conference on Software Engineering",        2027, "2026-09-15", "2027-04-27", "2027-05-01", "TBD",                  "software engineering",    "https://conf.researchr.org/home/icse-2027",               "IEEE/ACM",      "A*"),
    ("FSE",       "ACM International Conference on Foundations of Software Engineering",2026,"2026-03-27","2026-11-09","2026-11-13","Trondheim, Norway","software engineering","https://conf.researchr.org/home/fse-2026",               "ACM",           "A*"),
    ("ASE",       "IEEE/ACM International Conference on Automated Software Engineering",2026,"2026-04-10","2026-10-12","2026-10-15","TBD",         "software engineering",    "https://conf.researchr.org/home/ase-2026",                "IEEE/ACM",      "A*"),
    ("ISSTA",     "International Symposium on Software Testing and Analysis",2026, "2026-01-16", "2026-07-21", "2026-07-25", "TBD",                  "software engineering",    "https://conf.researchr.org/home/issta-2026",              "ACM",           "A"),
    ("PLDI",      "ACM SIGPLAN Conference on Programming Language Design and Implementation",2026,"2025-11-14","2026-06-13","2026-06-17","Seoul, South Korea","programming languages","https://pldi26.sigplan.org/",                         "ACM",           "A*"),
    ("POPL",      "ACM SIGPLAN Symposium on Principles of Programming Languages",2027,"2026-07-10","2027-01-17","2027-01-22","TBD",                "programming languages",   "https://popl27.sigplan.org/",                             "ACM",           "A*"),
    # ── Systems / OS ──
    ("OSDI",      "USENIX Symposium on Operating Systems Design and Implementation",2026,"2026-01-14","2026-11-04","2026-11-06","Santa Clara, USA","systems",                "https://www.usenix.org/conference/osdi26",                "USENIX",        "A*"),
    ("ATC",       "USENIX Annual Technical Conference",                       2026, "2026-01-07", "2026-07-14", "2026-07-16", "Boston, USA",          "systems",                 "https://www.usenix.org/conference/atc26",                 "USENIX",        "A"),
    ("SOSP",      "ACM Symposium on Operating Systems Principles",            2026, "2026-05-01", "2026-10-20", "2026-10-23", "TBD",                  "systems",                 "https://sosp2026.org/",                                   "ACM",           "A*"),
    ("EuroSys",   "European Conference on Computer Systems",                 2027, "2026-10-01", "2027-04-20", "2027-04-23", "TBD",                  "systems",                 "https://eurosys2027.github.io/",                          "ACM",           "A"),
    ("ASPLOS",    "ACM International Conference on Architectural Support for Programming Languages and Operating Systems",2027,"2026-08-05","2027-03-28","2027-04-02","TBD","computer architecture","https://asplos-conference.org/",                        "ACM",           "A*"),
    # ── Networking ──
    ("SIGCOMM",   "ACM SIGCOMM Conference",                                  2026, "2026-01-31", "2026-09-22", "2026-09-26", "TBD",                  "networking",              "https://sigcomm.org/",                                    "ACM",           "A*"),
    ("MobiCom",   "ACM International Conference on Mobile Computing and Networking",2026,"2026-03-13","2026-10-25","2026-10-29","TBD",               "networking",              "https://sigmobile.org/mobicom/2026/",                     "ACM",           "A*"),
    ("NSDI",      "USENIX Symposium on Networked Systems Design and Implementation",2027,"2026-09-05","2027-04-01","2027-04-03","TBD",               "networking",              "https://www.usenix.org/conference/nsdi27",                "USENIX",        "A*"),
    # ── Theory / Algorithms ──
    ("STOC",      "ACM Symposium on Theory of Computing",                    2026, "2025-11-05", "2026-06-09", "2026-06-12", "TBD",                  "algorithms and theory",   "https://stoc.sigact.org/",                                "ACM",           "A*"),
    ("FOCS",      "IEEE Symposium on Foundations of Computer Science",       2026, "2026-04-03", "2026-10-20", "2026-10-22", "TBD",                  "algorithms and theory",   "https://focs.computer.org/",                              "IEEE",          "A*"),
    ("SODA",      "ACM-SIAM Symposium on Discrete Algorithms",               2027, "2026-07-15", "2027-01-11", "2027-01-14", "TBD",                  "algorithms and theory",   "https://www.siam.org/conferences/cm/conference/soda27",  "ACM/SIAM",     "A"),
    # ── Computer Architecture ──
    ("ISCA",      "International Symposium on Computer Architecture",        2026, "2025-11-17", "2026-06-20", "2026-06-24", "TBD",                  "computer architecture",   "https://iscaconf.org/isca2026/",                          "IEEE/ACM",      "A*"),
    ("MICRO",     "IEEE/ACM International Symposium on Microarchitecture",    2026, "2026-04-17", "2026-10-31", "2026-11-04", "TBD",                  "computer architecture",   "https://microarch.org/micro59/",                          "IEEE/ACM",      "A*"),
    # ── HCI ──
    ("UIST",      "ACM Symposium on User Interface Software and Technology",  2026, "2026-04-01", "2026-10-18", "2026-10-22", "TBD",                  "human computer interaction","https://uist.acm.org/2026/",                             "ACM",           "A"),
    ("CSCW",      "ACM Conference on Computer-Supported Cooperative Work",    2026, "2025-10-16", "2026-11-01", "2026-11-04", "TBD",                  "human computer interaction","https://cscw.acm.org/2026/",                             "ACM",           "A"),
    # ── Vision ──
    ("ICCV",      "IEEE/CVF International Conference on Computer Vision",    2027, "2027-03-01", "2027-10-01", "2027-10-05", "TBD",                  "computer vision",         "https://iccv2027.thecvf.com/",                            "IEEE",          "A*"),
    # ── ML / AI (not in HF) ──
    ("ICLR",      "International Conference on Learning Representations",    2027, "2026-10-01", "2027-04-27", "2027-05-01", "TBD",                  "machine learning",        "https://iclr.cc/",                                        "ICLR Foundation","A*"),
    ("AISTATS",   "International Conference on Artificial Intelligence and Statistics",2026,"2025-10-11","2026-05-06","2026-05-08","TBD",            "machine learning",        "https://aistats.org/aistats2026/",                        "PMLR",          "A"),
    ("UAI",       "Conference on Uncertainty in Artificial Intelligence",    2026, "2026-02-07", "2026-07-27", "2026-07-29", "TBD",                  "machine learning",        "https://auai.org/uai2026/",                               "AUAI",          "A"),
    # ── Formal Methods ──
    ("CAV",       "International Conference on Computer Aided Verification",  2026, "2026-01-22", "2026-07-19", "2026-07-24", "TBD",                  "formal methods",          "https://i-cav.org/2026/",                                 "Springer",      "A*"),
    ("LICS",      "IEEE Symposium on Logic in Computer Science",             2026, "2026-01-13", "2026-07-06", "2026-07-09", "TBD",                  "formal methods",          "https://lics.siglog.org/lics26/",                         "IEEE",          "A*"),
]

CORE_RANK_FALLBACK = {
    "NEURIPS": "A*", "NIPS": "A*", "ICLR": "A*", "ICML": "A*",
    "CVPR": "A*", "ICCV": "A*", "ECCV": "A*",
    "ACL": "A*", "EMNLP": "A*", "NAACL": "A",
    "IEEE S&P": "A*", "NDSS": "A*", "CCS": "A*",
    "KDD": "A*", "ICDM": "A", "WWW": "A*",
}

COLUMNS = [
    "title", "acronym", "year", "venue_type", "source", "source_url",
    "official_url", "deadline", "event_start", "event_end", "open_status",
    "paid_or_free", "access_model", "fee_text", "location", "topics",
    "publisher", "core_rank", "quartile", "prestige_score",
    "prestige_label", "verification_notes",
]


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def fill(v):
    v = clean(v)
    return v if v else "Not specified"


def parse_date(value):
    if not value:
        return None
    try:
        d = date_parser.parse(str(value), fuzzy=True).date()
        if d.year >= CURRENT_YEAR - 1:
            return d
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def event_is_future(item_or_conf):
    """True if the conference event (start or end) is today or later."""
    ev_end = parse_date(
        item_or_conf.get("event_end") if isinstance(item_or_conf, dict) else None
    )
    ev_start = parse_date(
        item_or_conf.get("event_start") if isinstance(item_or_conf, dict) else None
    )
    if ev_end and ev_end >= TODAY:
        return True
    if ev_start and ev_start >= TODAY:
        return True
    return False


def classify_open_status(conf):
    """
    open     — CFP deadline in the future, or rolling with a future event
    upcoming — event still ahead but primary CFP deadline has passed
    closed   — event over and no open CFP
    """
    deadline_raw = conf.get("deadline") or ""

    if conf.get("is_open"):
        return "open"

    if not deadline_raw:
        return "open" if event_is_future(conf) else "closed"

    deadline = parse_date(deadline_raw)
    if deadline and deadline >= TODAY:
        return "open"

    if event_is_future(conf):
        return "upcoming"

    return "closed"


def extract_deadlines(item):
    """Return (primary_deadline, is_open) using paper > abstract > any future deadline."""
    found = []
    for entry in item.get("deadlines") or []:
        if not isinstance(entry, dict):
            continue
        d = parse_date(entry.get("date"))
        if d:
            found.append((entry.get("type", ""), d))

    for preferred in ("paper", "abstract", "submission"):
        for dtype, d in found:
            if dtype == preferred:
                return d, d >= TODAY

    future = [d for _, d in found if d >= TODAY]
    if future:
        return min(future), True

    paper_dates = [d for t, d in found if t == "paper"]
    if paper_dates:
        best = max(paper_dates)
        return best, best >= TODAY

    if found:
        best = max(d for _, d in found)
        return best, best >= TODAY

    for key in ("deadline", "abstract_deadline"):
        d = parse_date(item.get(key))
        if d:
            return d, d >= TODAY

    return None, False


def location_from_item(item):
    city = clean(item.get("city"))
    country = clean(item.get("country"))
    place = clean(item.get("place"))
    if city and country:
        return f"{city}, {country}"
    return place or city or country or ""


def tags_to_domain(tags):
    if not tags:
        return "Not specified"
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        key = str(tag).lower().strip()
        if key in TAG_TO_DOMAIN:
            return TAG_TO_DOMAIN[key]
    return "Not specified"


def extract_acronym(title, hf_stem=""):
    title = clean(title)
    if hf_stem:
        return hf_stem.upper() if len(hf_stem) <= 6 else hf_stem.replace("_", " ").title()

    known = {
        "NEURIPS": "NeurIPS", "NIPS": "NeurIPS",
        "SYMPOSIUM ON SECURITY AND PRIVACY": "IEEE S&P",
    }
    upper = title.upper()
    for needle, ac in known.items():
        if needle in upper:
            return ac

    m = re.search(
        r"\b(ICLR|ICML|CVPR|ICCV|ECCV|ACL|EMNLP|NAACL|NDSS|KDD|ICDM|WWW|CCS)\b",
        title, re.I,
    )
    if m:
        return m.group(1).upper()

    m = re.match(r"^([A-Z][A-Za-z0-9&\-]{1,15})\b", title)
    if m:
        return m.group(1)

    return title.split()[0] if title else "N/A"


def rank_to_prestige(rank):
    if rank == "A*":
        return "Q1", 98, "Very High"
    if rank == "A":
        return "Q2", 85, "High"
    if rank == "B":
        return "Q3", 65, "Medium"
    if rank == "C":
        return "Q4", 45, "Low"
    return "Unranked", 0, "Unknown"


def classify_fee(title, publisher, url=""):
    text = f"{title} {publisher} {url}".lower()
    if any(x in text for x in ["ieee", "acm", "springer", "elsevier", "usenix"]):
        return (
            "paid_registration_likely",
            "open_cfp_paid_registration_likely",
            "Registration typically required after acceptance",
        )
    return (
        "not_specified",
        "open_cfp_fee_not_specified",
        "Fee information unavailable",
    )


def load_core_map():
    rank_map = {}
    if CORE_CACHE_PATH.exists():
        df = pd.read_csv(CORE_CACHE_PATH)
        for _, row in df.iterrows():
            ac = clean(row.get("acronym", "")).upper()
            title = clean(row.get("title", "")).upper()
            rank = clean(row.get("rank", ""))
            if not rank:
                continue
            if ac and ac != "N/A":
                rank_map[ac] = rank
            if title:
                rank_map[title] = rank
        print(f"Loaded {len(rank_map)} CORE entries from cache")
    return rank_map


def lookup_core_rank(acronym, title, core_map):
    for key in (acronym.upper(), title.upper()):
        if key in core_map:
            return core_map[key]
    for key, rank in CORE_RANK_FALLBACK.items():
        if key in acronym.upper() or key in title.upper():
            return rank
    return "Unranked"


def http_get(url, timeout=25, params=None):
    try:
        req_params = dict(params or {})
        # Add a cache-busting param for raw endpoints to avoid stale CDN/proxy responses.
        req_params.setdefault("_", int(time.time()))
        r = requests.get(url, headers=HEADERS, timeout=timeout, params=req_params)
        if r.status_code == 200:
            return r
        print(f"HTTP {r.status_code}: {url}")
    except Exception as e:
        print(f"Request error: {url} | {e}")
    return None


def hf_item_to_conf(item, hf_stem, source_label):
    if not isinstance(item, dict):
        return None

    year = int(item.get("year") or 0)
    if year not in ALLOWED_YEARS:
        return None

    deadline, is_open = extract_deadlines(item)
    ev_start = parse_date(item.get("start"))
    ev_end = parse_date(item.get("end"))
    event_future = (ev_end and ev_end >= TODAY) or (ev_start and ev_start >= TODAY)
    if ev_end and ev_end < TODAY and not is_open and not event_future:
        return None

    title_base = clean(item.get("title") or hf_stem.upper())
    title = f"{title_base} {year}"
    acronym = extract_acronym(title_base, hf_stem)
    link = clean(item.get("link") or item.get("url") or "")
    tags = item.get("tags") or []
    domain = tags_to_domain(tags)
    location = location_from_item(item)
    publisher = clean(item.get("publisher") or "Conference Organizer")

    event_start = str(item.get("start", ""))[:10]
    event_end = str(item.get("end", ""))[:10]
    still_relevant = event_future or is_open

    return {
        "title": title,
        "acronym": acronym,
        "year": str(year),
        "deadline": str(deadline) if deadline else "",
        "is_open": is_open or (not deadline and still_relevant),
        "event_start": event_start,
        "event_end": event_end,
        "location": location,
        "official_url": link,
        "source_url": f"{HF_RAW_BASE}{hf_stem}.yml",
        "topics": domain,
        "publisher": publisher or "HuggingFace AI Deadlines",
        "source": source_label,
        "hf_stem": hf_stem,
    }


def fetch_hf_deadlines():
    print("\n--- HuggingFace AI Deadlines ---")
    records = []
    seen = set()

    r = http_get(HF_API_DIR)
    if not r:
        return records

    files = r.json()
    if not isinstance(files, list):
        return records

    for f in files:
        path = f.get("path") or f.get("name") or ""
        name = path.split("/")[-1]
        if not name.endswith((".yml", ".yaml")):
            continue

        stem = name.replace(".yml", "").replace(".yaml", "")

        raw_url = HF_RAW_BASE + name
        y = http_get(raw_url)
        if not y:
            continue

        try:
            data = yaml.safe_load(y.text)
        except yaml.YAMLError as e:
            print(f"YAML parse error {name}: {e}")
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            conf = hf_item_to_conf(item, stem, "huggingface_ai_deadlines")
            if not conf:
                continue
            key = (conf["title"], conf.get("official_url", ""))
            if key in seen:
                continue
            seen.add(key)
            records.append(conf)

        time.sleep(0.1)

    print(f"HF records (open/future): {len(records)}")
    return records


def _map_pwc_sub_to_domain(sub):
    if isinstance(sub, list):
        for v in sub:
            key = str(v).strip().upper()
            if key in PWC_SUB_TO_DOMAIN:
                return PWC_SUB_TO_DOMAIN[key]
    elif sub:
        key = str(sub).strip().upper()
        if key in PWC_SUB_TO_DOMAIN:
            return PWC_SUB_TO_DOMAIN[key]
    return "Not specified"


def pwc_item_to_conf(item):
    if not isinstance(item, dict):
        return None

    title_raw = clean(item.get("title") or item.get("full_name") or "")
    if not title_raw:
        return None

    year = int(item.get("year") or 0)
    if year not in ALLOWED_YEARS:
        return None

    # PWC often uses top-level deadline/abstract_deadline (no "deadlines" list).
    deadline, is_open = extract_deadlines(item)
    ev_end = parse_date(item.get("end"))
    ev_start = parse_date(item.get("start"))
    event_future = (ev_end and ev_end >= TODAY) or (ev_start and ev_start >= TODAY)
    if ev_end and ev_end < TODAY and not is_open and not event_future:
        return None

    acronym = clean(item.get("acronym") or item.get("id") or extract_acronym(title_raw))
    if acronym and re.search(r"\d{2,4}$", acronym):
        acronym = re.sub(r"\d{2,4}$", "", acronym).strip("-_ ")
    acronym = acronym.upper() if acronym else extract_acronym(title_raw)

    link = clean(item.get("link") or item.get("url") or "")
    location = location_from_item(item) or clean(item.get("place", ""))
    topic = _map_pwc_sub_to_domain(item.get("sub"))

    return {
        "title": f"{title_raw} {year}",
        "acronym": acronym,
        "year": str(year),
        "deadline": str(deadline) if deadline else "",
        "is_open": is_open or (not deadline and event_future),
        "event_start": str(item.get("start", ""))[:10],
        "event_end": str(item.get("end", ""))[:10],
        "location": location,
        "official_url": link,
        "source_url": PWC_DEADLINES,
        "topics": topic,
        "publisher": "PapersWithCode AI Deadlines",
        "source": "paperswithcode_ai_deadlines",
        "hf_stem": "",
    }


def fetch_pwc_deadlines():
    """Pull full PapersWithCode ai-deadlines as a live supplement to HF."""
    print("\n--- PapersWithCode supplement (all) ---")
    records = []
    r = http_get(PWC_DEADLINES)
    if not r:
        return records

    try:
        data = yaml.safe_load(r.text)
    except yaml.YAMLError:
        return records

    if not isinstance(data, list):
        return records

    for item in data:
        conf = pwc_item_to_conf(item)
        if conf:
            records.append(conf)

    print(f"PWC supplemental records (open/future): {len(records)}")
    return records


def refresh_core_cache():
    """Optional live CORE scrape; skipped if cache exists and is non-empty."""
    if CORE_CACHE_PATH.exists() and CORE_CACHE_PATH.stat().st_size > 500:
        return
    print("CORE cache missing/small — scraping portal...")
    rank_rows = []
    for page_no in range(1, 4):
        url = (
            "https://portal.core.edu.au/conf-ranks/"
            f"?by=all&page={page_no}&search=&sort=atitle&source=CORE2023"
        )
        html = http_get(url)
        if not html:
            continue
        soup = BeautifulSoup(html.text, "html.parser")
        for row in soup.find_all("tr"):
            cells = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            rank_match = re.search(r"\b(A\*|A|B|C)\b", " | ".join(cells))
            if not rank_match:
                continue
            rank = rank_match.group(1)
            acronym = "N/A"
            for c in cells:
                if re.fullmatch(r"[A-Z0-9\-&]{2,20}", c):
                    acronym = c
                    break
            long_cells = [c for c in cells if len(c) > 10 and c not in ("A*", "A", "B", "C")]
            title = max(long_cells, key=len) if long_cells else "Unknown"
            rank_rows.append({"title": title, "acronym": acronym, "rank": rank})
        time.sleep(1)
    if rank_rows:
        pd.DataFrame(rank_rows).drop_duplicates().to_csv(CORE_CACHE_PATH, index=False)


def fetch_static_seeds():
    """Return curated conf dicts for major CS venues not in HF AI Deadlines."""
    records = []
    today = date.today()
    for (acronym, base_title, year, dl_str, ev_start, ev_end, location, topics, url, publisher, core_rank) in STATIC_SEEDS:
        if year not in ALLOWED_YEARS:
            continue
        ev_end_d = parse_date(ev_end)
        ev_start_d = parse_date(ev_start)
        if ev_end_d and ev_end_d < today and not (ev_start_d and ev_start_d >= today):
            continue  # event is over
        deadline = parse_date(dl_str)
        is_open = bool(deadline and deadline >= today)
        records.append({
            "title": f"{base_title} {year}",
            "acronym": acronym.upper() if len(acronym) <= 8 else acronym,
            "year": str(year),
            "deadline": dl_str or "",
            "is_open": is_open,
            "event_start": ev_start or "",
            "event_end": ev_end or "",
            "location": location,
            "topics": topics,
            "official_url": url,
            "source_url": "https://core.edu.au/conference-portal",
            "source": "static_seed",
            "publisher": publisher,
            "core_rank": core_rank,  # preset — skips CORE lookup in build_csv_row
        })
    print(f"Static seeds (open/future): {len(records)}")
    return records


def build_csv_row(conf, core_map):
    title = conf["title"]
    acronym = fill(conf.get("acronym") or extract_acronym(title))
    # Use pre-set core_rank (e.g. from static seeds) instead of doing a lookup
    core_rank = conf.get("core_rank") or lookup_core_rank(acronym, title, core_map)
    quartile, prestige_score, prestige_label = rank_to_prestige(core_rank)

    paid_or_free, access_model, fee_text = classify_fee(
        title, conf.get("publisher", ""), conf.get("official_url", ""),
    )

    deadline = conf.get("deadline") or ""
    open_status = classify_open_status(conf)

    return {
        "title": fill(title),
        "acronym": acronym,
        "year": fill(conf.get("year")),
        "venue_type": "conference",
        "source": fill(conf.get("source")),
        "source_url": fill(conf.get("source_url")),
        "official_url": fill(conf.get("official_url")),
        "deadline": fill(deadline) if deadline else "Rolling",
        "event_start": fill(conf.get("event_start")),
        "event_end": fill(conf.get("event_end")),
        "open_status": open_status,
        "paid_or_free": paid_or_free,
        "access_model": access_model,
        "fee_text": fill(fee_text),
        "location": fill(conf.get("location")),
        "topics": fill(conf.get("topics")),
        "publisher": fill(conf.get("publisher")),
        "core_rank": core_rank,
        "quartile": quartile,
        "prestige_score": prestige_score,
        "prestige_label": prestige_label,
        "verification_notes": (
            f"Live data from {conf.get('source')}; "
            f"deadline/venue from ai-deadlines curated feed"
        ),
    }


def merge_sources(hf_records, pwc_records):
    """Prefer HF over PWC for same acronym+year."""
    merged = {}
    for conf in pwc_records + hf_records:
        key = (conf.get("acronym", "").upper(), conf.get("year", ""))
        if key not in merged or conf.get("source") == "huggingface_ai_deadlines":
            merged[key] = conf
    return list(merged.values())


def save_records(records):
    if not records:
        print("NO RECORDS")
        return 0

    df = pd.DataFrame(records)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = "Not specified"

    df = df[COLUMNS].fillna("Not specified")
    df.drop_duplicates(subset=["title", "official_url"], inplace=True)
    df.to_csv(CSV_PATH, index=False)
    print(f"\nCSV SAVED -> {CSV_PATH}")
    # Also copy to frontend/public so the dev server serves fresh data
    try:
        if PUBLIC_CSV_PATH.parent.exists():
            import shutil
            shutil.copy2(CSV_PATH, PUBLIC_CSV_PATH)
            print(f"Copied to frontend/public -> {PUBLIC_CSV_PATH}")
    except Exception as e:
        print(f"Could not copy to frontend/public: {e}")
    print(f"TOTAL RECORDS: {len(df)}")
    return len(df)


def run_fetch(*, open_only: bool = False, include_pwc: bool = True):
    """Fetch live CFPs once and write CSV. Returns number of rows saved."""
    print("\n==============================")
    print(f"LIVE CONFERENCE FETCH @ {datetime.now().isoformat(timespec='seconds')}")
    print("==============================")

    refresh_core_cache()
    core_map = load_core_map()

    hf_records = fetch_hf_deadlines()
    pwc_records = fetch_pwc_deadlines() if include_pwc else []
    seed_records = fetch_static_seeds()
    # Merge: HF > static seeds > PWC for same acronym+year
    merged = merge_sources(hf_records + seed_records, pwc_records)
    print(f"Merged unique venues: {len(merged)}")

    rows = [build_csv_row(c, core_map) for c in merged]
    open_rows = [r for r in rows if r.get("open_status") == "open"]
    upcoming_rows = [r for r in rows if r.get("open_status") == "upcoming"]

    if open_only:
        kept = open_rows
    else:
        # Default: keep open CFPs + future events (deadline passed but conference ahead)
        kept = [r for r in rows if r.get("open_status") in ("open", "upcoming")]

    print(
        f"Status breakdown: open={len(open_rows)}, "
        f"upcoming={len(upcoming_rows)}, "
        f"closed={len(rows) - len(open_rows) - len(upcoming_rows)}, "
        f"saved={len(kept)}"
    )

    kept.sort(
        key=lambda r: (
            0 if r.get("open_status") == "open" else 1,
            r.get("deadline") if r.get("deadline") not in ("Rolling", "Not specified") else "9999",
        ),
    )

    saved_count = save_records(kept)
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": TODAY.isoformat(),
        "allowed_years": sorted(list(ALLOWED_YEARS)),
        "include_pwc": include_pwc,
        "counts": {
            "hf_records": len(hf_records),
            "pwc_records": len(pwc_records),
            "merged": len(merged),
            "open": len(open_rows),
            "upcoming": len(upcoming_rows),
            "saved": saved_count,
        },
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"METADATA SAVED -> {META_PATH}")
    return saved_count


def watch_loop(interval_sec: int, *, open_only: bool = False, include_pwc: bool = True):
    """Refresh live_open_cfps.csv forever until interrupted (Ctrl+C)."""
    print(f"Watch mode: refreshing every {interval_sec}s ({interval_sec / 3600:.1f}h)")
    print("Press Ctrl+C to stop.\n")
    cycle = 0
    while True:
        cycle += 1
        print(f"\n--- cycle {cycle} ---")
        try:
            run_fetch(open_only=open_only, include_pwc=include_pwc)
        except Exception as e:
            print(f"Fetch failed (will retry): {e}")
        next_run = datetime.now() + timedelta(seconds=interval_sec)
        print(f"Sleeping {interval_sec}s until next refresh @ {next_run.isoformat(timespec='seconds')}...")
        time.sleep(interval_sec)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch live conference CFPs into live_open_cfps.csv",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run forever: refresh CSV on an interval (default 1 hour)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_WATCH_INTERVAL_SEC,
        help=f"Seconds between refreshes in watch mode (default {DEFAULT_WATCH_INTERVAL_SEC})",
    )
    parser.add_argument(
        "--open-only",
        action="store_true",
        help="Save only open CFPs (strict; usually fewer rows)",
    )
    parser.add_argument(
        "--no-pwc",
        action="store_true",
        help="Skip PapersWithCode supplement (HF-only mode)",
    )
    args = parser.parse_args()

    if args.watch:
        watch_loop(max(60, args.interval), open_only=args.open_only, include_pwc=not args.no_pwc)
    else:
        run_fetch(open_only=args.open_only, include_pwc=not args.no_pwc)
        print("\nDONE")


if __name__ == "__main__":
    main()
