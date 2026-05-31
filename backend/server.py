import os
import csv
import re
from datetime import datetime, date
from collections import defaultdict
from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    from transformers import pipeline
except Exception:
    pipeline = None

try:
    from optimized_smart_recommender import get_recommender
    OPTIMIZED_AVAILABLE = True
except ImportError:
    OPTIMIZED_AVAILABLE = False
    print("Optimized recommender not available, using fallback")

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

LIVE_CSV = os.path.join(PROJECT_DIR, "data", "live_open_cfps.csv")
ROLLING_CSV = os.path.join(PROJECT_DIR, "data", "rolling_journals.csv")

# =========================================================
# DOMAIN LABELS
# =========================================================

DOMAIN_LABELS = [
    "Artificial Intelligence and Machine Learning",
    "Internet of Things and Embedded Systems",
    "Cloud Computing and Edge Computing",
    "Big Data and Data Analytics",
    "Cybersecurity and Privacy",
    "Computer Networks and Communication",
    "Natural Language Processing",
    "Computer Vision and Image Processing",
    "Software Engineering",
    "Database Systems",
    "Blockchain and Web3",
    "Robotics and Automation",
    "Human Computer Interaction",
    "FinTech and Fraud Detection",
    "Health Informatics and IoMT",
    "General Computer Science",
]

DOMAIN_KEYWORDS = {
    "Artificial Intelligence and Machine Learning": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural", "classification", "prediction", "transformer", "bert",
        "llm", "reinforcement learning", "anomaly detection"
    ],
    "FinTech and Fraud Detection": [
        "fintech", "financial technology", "fraud", "fraud detection",
        "gst fraud", "tax fraud", "invoice fraud", "payment fraud",
        "financial crime", "risk analytics", "money laundering",
        "transaction fraud", "tax evasion"
    ],
    "Cybersecurity and Privacy": [
        "cybersecurity", "cyber security", "security", "privacy",
        "attack", "malware", "phishing", "intrusion detection",
        "threat", "vulnerability", "anomaly detection"
    ],
    "Big Data and Data Analytics": [
        "big data", "data analytics", "data science", "data mining",
        "spark", "hadoop", "kafka", "data engineering"
    ],
    "Cloud Computing and Edge Computing": [
        "cloud", "edge", "edge computing", "fog computing",
        "distributed computing", "serverless", "microservices"
    ],
    "Internet of Things and Embedded Systems": [
        "iot", "internet of things", "sensor", "embedded",
        "smart agriculture", "smart city", "aiot"
    ],
    "General Computer Science": [
        "computer science", "computing", "information technology",
        "algorithm", "system"
    ],
}

# =========================================================
# HARDCODED FALLBACK VENUE QUALITY
# =========================================================

Q1_VENUES = [
    "IEEE Transactions on Knowledge and Data Engineering",
    "IEEE Transactions on Information Forensics and Security",
    "IEEE Transactions on Dependable and Secure Computing",
    "IEEE Access",
    "Expert Systems with Applications",
    "Information Sciences",
    "Knowledge-Based Systems",
    "Decision Support Systems",
    "Pattern Recognition",
    "Computers & Security",
    "Future Generation Computer Systems",
    "ACM Transactions on Knowledge Discovery from Data",
    "Data Mining and Knowledge Discovery",
    "Journal of Big Data",
    "Artificial Intelligence Review",
    "Applied Soft Computing",
]

Q2_VENUES = [
    "Journal of Financial Crime",
    "Applied Artificial Intelligence",
    "SN Computer Science",
    "Data Technologies and Applications",
    "International Journal of Information Management Data Insights",
    "Journal of Information Security and Applications",
    "Information Systems Frontiers",
    "Annals of Data Science",
    "Intelligent Systems with Applications",
    "Machine Learning with Applications",
]

Q3_VENUES = [
    "International Journal of Advanced Computer Science and Applications",
    "International Journal of Computer Applications",
    "International Journal of Intelligent Systems and Applications",
    "International Journal of Computer Science and Information Security",
]

GOOD_PUBLISHERS = [
    "IEEE", "ACM", "Springer", "Elsevier", "Wiley",
    "Taylor", "Francis", "SAGE", "Oxford", "Cambridge",
    "Emerald", "MDPI", "Frontiers"
]

BAD_OR_UNKNOWN_HINTS = [
    "unknown", "not available", "n/a", "na", "test", "sample"
]

# =========================================================
# MODEL
# =========================================================

print("Loading domain classification model...")
domain_model = None

if pipeline:
    try:
        domain_model = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1,
        )
        print("Domain model loaded.")
    except Exception as e:
        print("Domain model unavailable, keyword fallback only:", e)


# =========================================================
# HELPERS
# =========================================================

def safe_str(v):
    if v is None:
        return ""
    if str(v).lower() in ["nan", "none", "null"]:
        return ""
    return str(v).strip()


def safe_float(v, default=None):
    try:
        if v in [None, "", "nan", "None", "N/A", "NA", "null"]:
            return default
        nums = re.findall(r"\d+\.?\d*", str(v).replace(",", ""))
        return float(nums[0]) if nums else default
    except Exception:
        return default


def normalize_url(url):
    url = safe_str(url)
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith("http://") and not url.startswith("https://"):
        return "https://" + url
    return url


def tokenize(text):
    stop = {
        "the", "and", "for", "with", "using", "based", "from", "this",
        "that", "into", "study", "system", "approach", "analysis",
        "method", "model", "paper", "research", "novel"
    }
    return [
        w for w in re.findall(r"[a-zA-Z0-9]+", safe_str(text).lower())
        if len(w) > 2 and w not in stop
    ]


def phrase_score(text, phrases):
    text = safe_str(text).lower()
    score = 0

    for phrase in phrases:
        phrase = phrase.lower()
        if phrase in text:
            words = phrase.split()
            if len(words) >= 3:
                score += 5
            elif len(words) == 2:
                score += 3
            else:
                score += 1

    return score


def read_csv_file(path):
    if not os.path.exists(path):
        print("[WARN] Missing CSV:", path)
        return []

    rows = []

    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                clean = {}
                for k, v in row.items():
                    if k:
                        clean[safe_str(k).lower()] = safe_str(v)
                rows.append(clean)

    except Exception as e:
        print("[CSV ERROR]", path, e)

    return rows


def get_field(row, keys):
    for key in keys:
        val = safe_str(row.get(key.lower()))
        if val:
            return val
    return ""


def venue_text(row):
    return " ".join([
        get_field(row, ["title", "name", "venue", "conference", "journal"]),
        get_field(row, ["acronym"]),
        get_field(row, ["topics", "topic", "subjects", "subject_area", "keywords", "category"]),
        get_field(row, ["publisher", "source"]),
        get_field(row, ["raw_text"]),
    ]).lower()


def keyword_score(query, text):
    q = set(tokenize(query))
    v = set(tokenize(text))

    if not q or not v:
        return 0.0

    return len(q & v) / max(len(q), 1)


LIVE_ROWS = read_csv_file(LIVE_CSV)
ROLLING_ROWS = read_csv_file(ROLLING_CSV)

print("Loaded live CFPs:", len(LIVE_ROWS))
print("Loaded rolling journals:", len(ROLLING_ROWS))


# =========================================================
# FALLBACK QUARTILE + METRICS
# =========================================================

def guess_quartile(title, publisher="", topics="", venue_type="journal"):
    text = f"{title} {publisher} {topics}".lower()

    for v in Q1_VENUES:
        if v.lower() in text:
            return "Q1"

    for v in Q2_VENUES:
        if v.lower() in text:
            return "Q2"

    for v in Q3_VENUES:
        if v.lower() in text:
            return "Q3"

    if any(p.lower() in text for p in ["ieee transactions", "acm transactions", "elsevier", "springer nature"]):
        return "Q1"

    if any(p.lower() in text for p in GOOD_PUBLISHERS):
        return "Q2"

    if venue_type == "journal":
        return "Q2"

    return "Q4"


def get_actual_metrics(row, venue_type):
    """Get actual metrics from CSV data instead of hardcoded values"""
    title = get_field(row, ["title", "name", "venue", "conference", "journal"])
    publisher = get_field(row, ["publisher", "source", "host"])
    topics = get_field(row, ["topics", "topic", "subject_area", "subjects", "keywords"])

    # Get actual values from CSV
    h_index = safe_float(row.get("h_index"))
    h5_index = safe_float(row.get("h5_index"))
    sjr = safe_float(row.get("sjr"))
    impact = safe_float(row.get("impact_factor") or row.get("impact_score"))
    prestige = safe_float(row.get("prestige_score") or row.get("quality_score"))
    
    # Get quartile from CSV or guess if not available
    existing_q = get_field(row, ["q_rank", "quartile"]).upper()
    quartile = existing_q
    for label in ("Q1", "Q2", "Q3", "Q4"):
        if label in quartile:
            quartile = label
            break
    else:
        quartile = quartile if quartile in ["Q1", "Q2", "Q3", "Q4"] else guess_quartile(
            title=title,
            publisher=publisher,
            topics=topics,
            venue_type=venue_type,
        )

    prestige = safe_float(prestige, 0) or 0

    # Determine prestige label based on actual data
    if prestige >= 80:
        label = "High prestige"
    elif prestige >= 60:
        label = "Good indexed venue"
    elif prestige >= 40:
        label = "Medium indexed venue"
    else:
        label = "Emerging venue"
    
    # Check if venue is verified (has official URL, etc.)
    is_verified = bool(
        get_field(row, ["official_url", "url"]) and 
        get_field(row, ["publisher", "source"]) and
        prestige > 0
    )
    
    return {
        "h_index": h_index,
        "h5_index": h5_index,
        "sjr": sjr,
        "impact_factor": impact,
        "prestige_score": prestige,
        "prestige_label": label,
        "is_verified": is_verified,
        "quartile": quartile,
        "q_rank": quartile,
    }


def prestige_score(row, venue_type="journal"):
    m = get_actual_metrics(row, venue_type)

    score = 0.0
    score += min((m["h_index"] or 0) / 150, 1.0) * 25
    score += min((m["impact_factor"] or 0) / 10, 1.0) * 20
    score += min((m["sjr"] or 0) / 3, 1.0) * 15

    q = m["quartile"]

    if q == "Q1":
        score += 25
    elif q == "Q2":
        score += 18
    elif q == "Q3":
        score += 10
    elif q == "Q4":
        score += 4

    score += min((m["prestige_score"] or 0) / 100, 1.0) * 15

    return min(score, 100)


def _parse_deadline_date(value):
    """Parse a deadline / open_until style field into a date or None."""
    try:
        if value is None:
            return None

        s = safe_str(value)
        if not s:
            return None

        lowered = s.lower()
        if lowered in {"rolling", "not specified", "tba", "na", "n/a", "unknown"}:
            return None

        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.date()
    except Exception:
        return None


def deadline_urgency(row):
    """
    Map upcoming deadlines to [0, 1].

    - 0 when deadline is missing / clearly non-date / already past
    - 1 when due in <= 90 days
    - linearly scaled in between
    """
    dl = row.get("deadline") or row.get("open_until")
    d = _parse_deadline_date(dl)

    if not d:
        return 0.0

    today = date.today()
    days_left = (d - today).days

    if days_left <= 0:
        return 0.0

    return min(1.0, days_left / 90.0)


# =========================================================
# DOMAIN DETECTION
# =========================================================

def detect_domains(title, abstract=""):
    text = f"{safe_str(title)}. {safe_str(abstract)}".lower().strip()
    scores = defaultdict(float)

    if not text:
        return {
            "primary": "General Computer Science",
            "labels": ["General Computer Science"],
            "detected_domains": [{"domain": "General Computer Science", "score": 1}],
            "expanded_query": "computer science information technology"
        }

    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] += phrase_score(text, keywords)

    if any(x in text for x in ["gst", "tax fraud", "invoice fraud", "financial fraud", "fraud detection"]):
        scores["FinTech and Fraud Detection"] += 30
        scores["Artificial Intelligence and Machine Learning"] += 8
        scores["Cybersecurity and Privacy"] += 6
        scores["Big Data and Data Analytics"] += 4

    if "anomaly detection" in text:
        scores["Artificial Intelligence and Machine Learning"] += 10
        scores["Cybersecurity and Privacy"] += 6
        scores["FinTech and Fraud Detection"] += 6

    if domain_model:
        try:
            result = domain_model(text, DOMAIN_LABELS, multi_label=True)
            for label, zscore in zip(result.get("labels", []), result.get("scores", [])):
                scores[label] += float(zscore) * 4
        except Exception as e:
            print("[DOMAIN MODEL ERROR]", e)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ranked = [(d, s) for d, s in ranked if s > 1]

    if not ranked:
        ranked = [("General Computer Science", 1)]

    top = ranked[:4]
    labels = [d for d, _ in top]

    expanded_parts = [text]
    for label in labels:
        expanded_parts.extend(DOMAIN_KEYWORDS.get(label, []))

    return {
        "primary": labels[0],
        "labels": labels,
        "detected_domains": [
            {"domain": d, "score": round(float(s), 2)}
            for d, s in top
        ],
        "expanded_query": " ".join(expanded_parts)
    }


def domain_match_bonus(labels, text):
    text = safe_str(text).lower()
    bonus = 0

    for idx, label in enumerate(labels):
        keywords = DOMAIN_KEYWORDS.get(label, [])
        hits = phrase_score(text, keywords)

        weight = max(0.45, 1.0 - idx * 0.18)

        if hits >= 8:
            bonus += 35 * weight
        elif hits >= 4:
            bonus += 25 * weight
        elif hits >= 2:
            bonus += 16 * weight
        elif hits >= 1:
            bonus += 8 * weight

    return min(bonus, 45)


# =========================================================
# NORMALIZE RESULT
# =========================================================

def normalize_result(row, venue_type, score, kscore, domain_bonus, qscore, domain_info, idx):
    title = get_field(row, ["title", "name", "venue", "conference", "journal"]) or "Unknown Venue"

    official = normalize_url(get_field(row, ["official_url", "url", "homepage", "website"]))
    page_url = normalize_url(get_field(row, ["page_url", "source_url", "cfp_url", "url"]))
    submission = normalize_url(get_field(row, ["submission_url", "submit_url", "deadline_url", "url"]))

    metrics = get_actual_metrics(row, venue_type)

    return {
        "id": f"{venue_type}-{idx}",
        "title": title,
        "type": venue_type,
        "venue_type": venue_type,

        "publisher": get_field(row, ["publisher", "source", "host"]) or "Not available",
        "source": get_field(row, ["source"]) or "CSV",
        "topics": get_field(row, ["topics", "topic", "subject_area", "subjects", "keywords"]),

        "url": official or page_url or submission,
        "official_url": official or page_url or submission,
        "page_url": page_url or official,
        "submission_url": submission or official,

        "deadline": get_field(row, ["deadline", "open_until", "submission_deadline"]) or "Rolling",
        "open_until": get_field(row, ["open_until", "deadline", "submission_deadline"]) or "Rolling",

        "h_index": metrics["h_index"],
        "h5_index": metrics["h5_index"],
        "sjr": metrics["sjr"],
        "impact_factor": metrics["impact_factor"],
        "impact_score": metrics["impact_factor"],

        "quartile": metrics["quartile"],
        "q_rank": metrics["q_rank"],

        "core_rank": get_field(row, ["core_rank", "core"]) or "Not available",
        "acceptance_rate": safe_float(row.get("acceptance_rate")),

        "paid": get_field(row, ["paid", "paid_or_free", "apc", "fee_text"]) or "Not specified",
        "paid_or_free": get_field(row, ["paid", "paid_or_free", "apc", "fee_text"]) or "Not specified",

        "presentation_type": get_field(row, ["presentation_type", "mode", "format"]) or "Not specified",
        "indexed": get_field(row, ["indexed", "indexing"]) or "Likely indexed / needs verification",

        "prestige_score": metrics["prestige_score"],
        "prestige_label": metrics["prestige_label"],
        "is_verified": metrics["is_verified"],

        "recommendation_score": round(min(score, 100), 2),
        "match_score": round(min(score, 100), 2),
        "keyword_score": round(kscore * 100, 2),
        "domain_score": round(domain_bonus, 2),
        "graph_score": round(domain_bonus, 2),
        "quality_score": round(qscore, 2),

        "detected_domains": domain_info.get("detected_domains", []),

        "match_reason": (
            f"Detected domain labels: {', '.join(domain_info.get('labels', []))}. "
            f"Recommended because its title/topics/publisher matched the expanded research profile. "
            f"Temporary fallback metrics were applied when CSV quality fields were missing."
        ),

        "verification_notes": (
            "Fallback prestige used. Replace later with real Scopus/SJR/CORE/OpenAlex enrichment."
        )
    }


# =========================================================
# RECOMMENDER
# =========================================================

def recommend_venues(
    title,
    abstract="",
    venue_type="all",
    top_k=10,
    min_h_index=0,
    quartile="all",
    location="all",
    paid_or_free="all",
    open_status="all",
    core_rank="all"
):
    domain_info = detect_domains(title, abstract)
    query = domain_info["expanded_query"]

    results = []
    idx = 0

    venue_type = safe_str(venue_type).lower()
    quartile = safe_str(quartile).upper()
    location = safe_str(location).lower()

    if venue_type in ["all", "conference", "conferences"]:
        for row in LIVE_ROWS:
            text = venue_text(row)

            k = keyword_score(query, text)
            d_bonus = domain_match_bonus(domain_info["labels"], text)
            q = prestige_score(row, "conference")
            urgency = deadline_urgency(row)

            # Include deadline urgency as an explicit part of the score
            final = (k * 30) + d_bonus + (q * 0.22) + (urgency * 20) + 15

            result = normalize_result(
                row=row,
                venue_type="conference",
                score=final,
                kscore=k,
                domain_bonus=d_bonus,
                qscore=q,
                domain_info=domain_info,
                idx=idx,
            )

            # Attach a more detailed scoring explanation
            result["deadline_urgency"] = round(urgency * 100, 2)
            result["scoring_breakdown"] = {
                "keyword_match": round(k * 100, 2),
                "domain_bonus": round(d_bonus, 2),
                "prestige_score": round(q, 2),
                "deadline_urgency": round(urgency * 100, 2),
            }

            if apply_filters(result, min_h_index, quartile, location,
                             paid_or_free, open_status, core_rank):
                results.append(result)

            idx += 1

    if venue_type in ["all", "journal", "journals"]:
        for row in ROLLING_ROWS:
            text = venue_text(row)

            k = keyword_score(query, text)
            d_bonus = domain_match_bonus(domain_info["labels"], text)
            q = prestige_score(row, "journal")
            urgency = deadline_urgency(row)

            # Journals often have more flexible timelines, but we still reward fresher calls
            final = (k * 32) + d_bonus + (q * 0.26) + (urgency * 15) + 18

            result = normalize_result(
                row=row,
                venue_type="journal",
                score=final,
                kscore=k,
                domain_bonus=d_bonus,
                qscore=q,
                domain_info=domain_info,
                idx=idx,
            )

            result["deadline_urgency"] = round(urgency * 100, 2)
            result["scoring_breakdown"] = {
                "keyword_match": round(k * 100, 2),
                "domain_bonus": round(d_bonus, 2),
                "prestige_score": round(q, 2),
                "deadline_urgency": round(urgency * 100, 2),
            }

            if apply_filters(result, min_h_index, quartile, location,
                             paid_or_free, open_status, core_rank):
                results.append(result)

            idx += 1

    results = sorted(results, key=lambda x: x["recommendation_score"], reverse=True)
    results = results[:top_k]

    return {
        "status": "success",
        "domain": domain_info["primary"],
        "detected_domain": domain_info["primary"],
        "detected_labels": domain_info["labels"],
        "detected_domains": domain_info["detected_domains"],
        "sources": [
            "live_open_cfps.csv",
            "rolling_journals.csv",
            "keyword domain detection",
            "zero-shot domain refinement if available",
            "temporary hardcoded quartile fallback",
            "fallback prestige scoring",
            "deadline urgency heuristic",
            "per-venue scoring breakdown (keyword/domain/prestige/deadline)"
        ],
        "recommendations": results,
        "total": len(results),
    }


def apply_filters(result, min_h_index=0, quartile="all", location="all",
                    paid_or_free="all", open_status="all", core_rank="all"):
    try:
        min_h_index = int(min_h_index or 0)
    except Exception:
        min_h_index = 0

    if min_h_index > 0 and float(result.get("h_index") or 0) < min_h_index:
        return False

    q = safe_str(result.get("quartile") or result.get("q_rank")).upper()
    quartile = safe_str(quartile).upper()

    if quartile not in ["", "ALL"] and quartile not in q:
        return False

    if location not in ["", "all"]:
        loc_text = " ".join([
            safe_str(result.get("location")),
            safe_str(result.get("raw_text")),
            safe_str(result.get("title")),
        ]).lower()

        if location not in loc_text:
            return False

    # Paid / Free filter
    pof = safe_str(paid_or_free).lower()
    if pof not in ["", "all"]:
        rec_pof = safe_str(result.get("paid_or_free") or result.get("paid")).lower()
        if pof == "free" and "free" not in rec_pof and "no" not in rec_pof:
            return False
        if pof == "paid" and "paid" not in rec_pof and "subscription" not in rec_pof and "fee" not in rec_pof:
            return False

    # Open / Closed filter
    os_ = safe_str(open_status).lower()
    if os_ not in ["", "all"]:
        rec_os = safe_str(result.get("open_status")).lower()
        _open_vals = ["open", "upcoming", "yes", "true", "rolling_journal", "deadline_open", "open_deadline_unknown"]
        if os_ == "open" and rec_os not in _open_vals:
            return False
        if os_ == "closed" and rec_os in _open_vals:
            return False

    # CORE rank filter (for conferences)
    cr = safe_str(core_rank).upper()
    if cr not in ["", "ALL", "UNRANKED"]:
        rec_cr = safe_str(result.get("core_rank")).upper()
        if cr == "A*" and "A*" not in rec_cr:
            return False
        if cr == "A" and "A" not in rec_cr:
            return False
        if cr == "B" and "B" not in rec_cr:
            return False
        if cr == "C" and "C" not in rec_cr:
            return False
    if cr == "UNRANKED":
        rec_cr = safe_str(result.get("core_rank")).upper()
        if rec_cr and rec_cr not in ["NOT AVAILABLE", "N/A", "NA", "UNRANKED", ""]:
            return False

    return True


# =========================================================
# ROUTES
# =========================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "running",
        "message": "Academic Venue Backend Running",
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "live_csv_exists": os.path.exists(LIVE_CSV),
        "rolling_csv_exists": os.path.exists(ROLLING_CSV),
        "live_rows": len(LIVE_ROWS),
        "rolling_rows": len(ROLLING_ROWS),
    })


@app.route("/api/smart-recommendations", methods=["POST", "OPTIONS"])
def smart_recommendations():
    if request.method == "OPTIONS":
        return jsonify({"ok": True}), 200

    data = request.get_json() or {}
    title = data.get("title", "").strip()
    abstract = data.get("abstract", "").strip()
    venue_type = data.get("venue_type", "all")
    top_k = int(data.get("top_k", 10))
    min_h_index = data.get("min_h_index", "")
    quartile = data.get("quartile", "")
    location = data.get("location", "")
    paid_or_free = data.get("paid_or_free", "all")
    open_status = data.get("open_status", "all")
    core_rank = data.get("core_rank", "all")

    if not title:
        return jsonify({
            "status": "error",
            "message": "Missing title",
            "recommendations": [],
        }), 400

    # Use optimized recommender if available
    if OPTIMIZED_AVAILABLE:
        try:
            recommender = get_recommender()
            result = recommender.recommend(
                title=title,
                abstract=abstract,
                venue_type=venue_type,
                top_k=top_k
            )
            
            # Apply additional filters if needed
            def _passes(rec):
                # h-index
                if min_h_index:
                    try:
                        h_idx = safe_float(rec.get("h_index", 0))
                        if h_idx < int(min_h_index):
                            return False
                    except:
                        pass
                # quartile
                if quartile and quartile.lower() not in ("all", ""):
                    rec_quartile = safe_str(
                        rec.get("quartile") or rec.get("q_rank")
                    ).upper()
                    if quartile.upper() not in rec_quartile:
                        return False
                # location
                if location and safe_str(location).lower() not in ("all", "all locations", ""):
                    rec_location = rec.get("location", "").lower()
                    if location.lower() not in rec_location:
                        return False
                # paid / free
                if paid_or_free and paid_or_free.lower() not in ("all", ""):
                    rec_pof = safe_str(rec.get("paid_or_free") or rec.get("paid")).lower()
                    if paid_or_free.lower() == "free" and "free" not in rec_pof and "no" not in rec_pof:
                        return False
                    if paid_or_free.lower() == "paid" and "paid" not in rec_pof and "subscription" not in rec_pof and "fee" not in rec_pof:
                        return False
                # open / closed
                if open_status and open_status.lower() not in ("all", ""):
                    rec_os = safe_str(rec.get("open_status")).lower()
                    _open_vals = ["open", "upcoming", "yes", "true", "rolling_journal", "deadline_open", "open_deadline_unknown"]
                    if open_status.lower() == "open" and rec_os not in _open_vals:
                        return False
                    if open_status.lower() == "closed" and rec_os in _open_vals:
                        return False
                # core rank
                if core_rank and core_rank.upper() not in ("ALL", ""):
                    rec_cr = safe_str(rec.get("core_rank")).upper()
                    if core_rank.upper() == "A*" and "A*" not in rec_cr:
                        return False
                    if core_rank.upper() == "A" and "A" not in rec_cr:
                        return False
                    if core_rank.upper() == "B" and "B" not in rec_cr:
                        return False
                    if core_rank.upper() == "C" and "C" not in rec_cr:
                        return False
                    if core_rank.upper() == "UNRANKED" and rec_cr and rec_cr not in ["NOT AVAILABLE", "N/A", "NA", "UNRANKED", ""]:
                        return False
                return True

            filtered_recs = [rec for rec in result.get("recommendations", []) if _passes(rec)]
            result["recommendations"] = filtered_recs[:top_k]
            result["total"] = len(filtered_recs)
            
            return jsonify(result)
            
        except Exception as e:
            print(f"Optimized recommender error: {e}")
            
    result = recommend_venues(
        title=title,
        abstract=abstract,
        venue_type=venue_type,
        top_k=top_k,
        min_h_index=min_h_index,
        quartile=quartile,
        location=location,
        paid_or_free=paid_or_free,
        open_status=open_status,
        core_rank=core_rank,
    )

    return jsonify(result), 200


@app.route("/api/venues", methods=["GET"])
def get_venues():
    all_venues = []

    domain_info = {
        "labels": [],
        "detected_domains": []
    }

    for i, row in enumerate(LIVE_ROWS):
        qscore = prestige_score(row, "conference")
        all_venues.append(normalize_result(
            row=row,
            venue_type="conference",
            score=qscore,
            kscore=0,
            domain_bonus=0,
            qscore=qscore,
            domain_info=domain_info,
            idx=i
        ))

    for i, row in enumerate(ROLLING_ROWS):
        qscore = prestige_score(row, "journal")
        all_venues.append(normalize_result(
            row=row,
            venue_type="journal",
            score=qscore,
            kscore=0,
            domain_bonus=0,
            qscore=qscore,
            domain_info=domain_info,
            idx=i
        ))

    return jsonify({
        "data": all_venues,
        "total": len(all_venues),
        "status": "success"
    })


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    print("\n==============================")
    print("ACADEMIC VENUE BACKEND STARTED")
    print("==============================")
    print("Backend: http://127.0.0.1:5000")
    print("Live CSV:", LIVE_CSV)
    print("Rolling CSV:", ROLLING_CSV)
    print("Live rows:", len(LIVE_ROWS))
    print("Rolling rows:", len(ROLLING_ROWS))
    print("==============================\n")

    app.run(host="0.0.0.0", port=5000, debug=True)