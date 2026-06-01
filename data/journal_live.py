import requests
import sqlite3
import pandas as pd
import time
import csv
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT_DIR 
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = ROOT_DIR / "journal_conference_data.db"
ROLLING_CSV_PATH = PUBLIC_DIR / "rolling_journals.csv"

EMAIL = "pes2ug22cs273@pesu.pes.edu"

HEADERS = {
    "User-Agent": f"Mozilla/5.0 AcademicRollingJournalBot/3.0 mailto:{EMAIL}"
}

PER_PAGE = 200
SLEEP_BETWEEN_REQUESTS = 0.4
EXPORT_EVERY_PAGES = 2


def fill(value, default="Unknown"):
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    return value


def safe_float(value, default=0.1):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except:
        return default


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()

    cur.execute("""
        DROP TABLE IF EXISTS venues
    """)

    cur.execute("""
        CREATE TABLE venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            acronym TEXT,
            year TEXT,
            venue_type TEXT,
            source TEXT,
            source_url TEXT UNIQUE,
            official_url TEXT,
            url TEXT,
            deadline TEXT,
            open_from TEXT,
            open_until TEXT,
            open_status TEXT,
            paid_or_free TEXT,
            fee_text TEXT,
            is_oa TEXT,
            publisher TEXT,
            country TEXT,
            issn TEXT,
            topics TEXT,
            subject_area TEXT,
            primary_topic TEXT,
            works_count REAL,
            cited_by_count REAL,
            h_index REAL,
            impact_score REAL,
            sjr TEXT,
            quartile TEXT,
            overall_rank TEXT,
            quality_score REAL,
            prestige_score REAL,
            prestige_label TEXT,
            source_quality_score REAL,
            url_confidence REAL,
            data_origin TEXT,
            is_verified TEXT,
            verification_notes TEXT,
            raw_text TEXT,
            scraped_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def calculate_open_access(item):
    is_oa = item.get("is_oa", False)
    apc_usd = item.get("apc_usd")
    apc_prices = item.get("apc_prices") or []

    if apc_prices:
        fee_text = "; ".join(
            f"{fill(p.get('price'), '?')} {fill(p.get('currency'), 'USD')}"
            for p in apc_prices
        )
    elif apc_usd:
        fee_text = f"{apc_usd} USD"
    else:
        fee_text = "Fee not available"

    if is_oa and apc_usd:
        paid_or_free = "paid_oa"
    elif is_oa:
        paid_or_free = "free_oa"
    else:
        paid_or_free = "subscription_or_unknown"

    return str(is_oa), paid_or_free, fee_text


def calculate_prestige(h_index, cited_by_count, works_count, impact_score):
    h_index = safe_float(h_index)
    cited_by_count = safe_float(cited_by_count, 0)
    works_count = safe_float(works_count, 0)
    impact_score = safe_float(impact_score)

    prestige_score = round(
        min(h_index, 300) * 0.45 +
        min(cited_by_count / 1000, 300) * 0.30 +
        min(works_count / 1000, 150) * 0.10 +
        min(impact_score * 20, 200) * 0.15,
        2
    )

    if prestige_score >= 120:
        return prestige_score, "Very High", "Q1"
    elif prestige_score >= 70:
        return prestige_score, "High", "Q2"
    elif prestige_score >= 35:
        return prestige_score, "Medium", "Q3"
    else:
        return prestige_score, "Low", "Q4"


def fetch_scimago(title, issn=""):
    try:
        search_term = issn.split(",")[0].strip() if issn and issn != "Unknown" else title[:70]

        if not search_term:
            return {}

        url = "https://www.scimagojr.com/journalrank.php"

        params = {
            "search": search_term,
            "out": "xls",
            "order": "sjr",
            "ord": "desc"
        }

        res = requests.get(url, params=params, headers=HEADERS, timeout=25)
        res.raise_for_status()

        lines = res.text.strip().split("\n")

        if len(lines) < 2:
            return {}

        rows = list(csv.DictReader(lines, delimiter=";"))

        if not rows:
            return {}

        row = rows[0]

        sjr = fill(row.get("SJR"), "0.1")
        quartile = fill(row.get("SJR Best Quartile"), "Q4")
        rank = fill(row.get("Rank"), "999999")

        sjr_num = safe_float(sjr)

        if quartile == "Q1":
            prestige_label = "Very High"
            prestige_score = 95
        elif quartile == "Q2":
            prestige_label = "High"
            prestige_score = 80
        elif quartile == "Q3":
            prestige_label = "Medium"
            prestige_score = 60
        elif quartile == "Q4":
            prestige_label = "Low"
            prestige_score = 40
        elif sjr_num >= 3:
            prestige_label = "Very High"
            prestige_score = 95
        elif sjr_num >= 1.5:
            prestige_label = "High"
            prestige_score = 80
        elif sjr_num >= 0.5:
            prestige_label = "Medium"
            prestige_score = 60
        else:
            prestige_label = "Low"
            prestige_score = 40

        return {
            "sjr": sjr,
            "quartile": quartile,
            "overall_rank": rank,
            "prestige_score": prestige_score,
            "prestige_label": prestige_label,
        }

    except Exception:
        return {}


def parse_openalex_item(item):
    summary = item.get("summary_stats") or {}
    topics = item.get("topics") or []
    primary_topic_obj = item.get("primary_topic") or {}

    topic_names = [
        topic.get("display_name", "")
        for topic in topics[:8]
        if topic.get("display_name")
    ]

    primary_topic = fill(primary_topic_obj.get("display_name"), "General Research")

    field_obj = primary_topic_obj.get("field") or {}
    subject_area = fill(field_obj.get("display_name"), primary_topic)

    homepage = fill(item.get("homepage_url"), item.get("id") or "Not Available")

    works_count = safe_float(item.get("works_count"), 0)
    cited_by_count = safe_float(item.get("cited_by_count"), 0)
    h_index = safe_float(summary.get("h_index"), 1)
    impact_score = safe_float(summary.get("2yr_mean_citedness"), 0.1)

    issn = ", ".join(item.get("issn") or [])
    issn = fill(issn, "Unknown")

    publisher = fill(item.get("host_organization_name"), "Unknown Publisher")
    country = fill(item.get("country_code"), "Unknown")

    topics_string = ", ".join(topic_names) if topic_names else subject_area

    is_oa, paid_or_free, fee_text = calculate_open_access(item)

    prestige_score, prestige_label, quartile = calculate_prestige(
        h_index,
        cited_by_count,
        works_count,
        impact_score
    )

    quality_score = round(
        works_count * 0.10 +
        cited_by_count * 0.30 +
        h_index * 100 +
        impact_score * 50,
        2
    )

    estimated_sjr = round(max(prestige_score / 40, 0.1), 2)
    estimated_rank = int(max(1, 100000 - prestige_score * 500))

    return {
        "title": fill(item.get("display_name"), "Unknown Journal"),
        "acronym": fill(item.get("abbreviated_title"), "N/A"),
        "year": str(datetime.now().year),
        "venue_type": fill(item.get("type"), "journal"),

        "source": "OpenAlex Sources API",
        "source_url": fill(item.get("id"), homepage),
        "official_url": homepage,
        "url": homepage,

        "deadline": "Rolling",
        "open_from": "Continuous",
        "open_until": "Continuous",
        "open_status": "rolling_journal",

        "paid_or_free": paid_or_free,
        "fee_text": fee_text,
        "is_oa": is_oa,

        "publisher": publisher,
        "country": country,
        "issn": issn,

        "topics": topics_string,
        "subject_area": subject_area,
        "primary_topic": primary_topic,

        "works_count": works_count,
        "cited_by_count": cited_by_count,
        "h_index": h_index,
        "impact_score": impact_score,

        "sjr": str(estimated_sjr),
        "quartile": quartile,
        "overall_rank": str(estimated_rank),

        "quality_score": quality_score,
        "prestige_score": prestige_score,
        "prestige_label": prestige_label,

        "source_quality_score": 95,
        "url_confidence": 95,

        "data_origin": "OpenAlex live API",
        "is_verified": "yes",
        "verification_notes": "OpenAlex live data with automatic fallback enrichment.",
        "raw_text": f"{subject_area} journal published by {publisher}.",
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_record(record):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO venues (
            title, acronym, year, venue_type,
            source, source_url, official_url, url,
            deadline, open_from, open_until, open_status,
            paid_or_free, fee_text, is_oa,
            publisher, country, issn,
            topics, subject_area, primary_topic,
            works_count, cited_by_count, h_index, impact_score,
            sjr, quartile, overall_rank,
            quality_score, prestige_score, prestige_label,
            source_quality_score, url_confidence,
            data_origin, is_verified, verification_notes,
            raw_text, scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tuple(record.values()))

    conn.commit()
    conn.close()


def export_rolling_csv():
    conn = sqlite3.connect(DB_PATH, timeout=30)

    df = pd.read_sql_query("""
        SELECT *
        FROM venues
        WHERE open_status = 'rolling_journal'
        ORDER BY prestige_score DESC, quality_score DESC
    """, conn)

    conn.close()

    if not df.empty:
        df.drop_duplicates(subset=["title", "url"], inplace=True)
        df.fillna("Unknown", inplace=True)
        df.replace("", "Unknown", inplace=True)

    df.to_csv(ROLLING_CSV_PATH, index=False)
    print(f"CSV updated -> {ROLLING_CSV_PATH} | records={len(df)}")


def fetch_openalex_rolling_journals_forever():
    base_url = "https://api.openalex.org/sources"
    cursor = "*"
    pages = 0
    total = 0

    print("\n==============================")
    print("ROLLING JOURNAL WORKER STARTED")
    print("==============================")

    while True:
        params = {
            "filter": "type:journal",
            "sort": "works_count:desc",
            "per-page": PER_PAGE,
            "cursor": cursor,
            "mailto": EMAIL,
        }

        try:
            res = requests.get(base_url, params=params, headers=HEADERS, timeout=30)

            if res.status_code != 200:
                print("OpenAlex error:", res.status_code, res.text[:300])
                time.sleep(60)
                continue

            data = res.json()
            results = data.get("results", [])

            if not results:
                export_rolling_csv()
                cursor = "*"
                pages = 0
                time.sleep(3600)
                continue

            for item in results:
                record = parse_openalex_item(item)

                scimago_data = fetch_scimago(
                    record.get("title"),
                    record.get("issn")
                )

                if scimago_data:
                    record.update(scimago_data)

                for key in record:
                    record[key] = fill(record[key], "Unknown")

                save_record(record)
                total += 1

            pages += 1
            cursor = data.get("meta", {}).get("next_cursor")

            print(f"Fetched/updated journals: {total}")

            if pages % EXPORT_EVERY_PAGES == 0:
                export_rolling_csv()

            if not cursor:
                export_rolling_csv()
                cursor = "*"
                pages = 0
                time.sleep(3600)

            time.sleep(SLEEP_BETWEEN_REQUESTS)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)


if __name__ == "__main__":
    init_db()
    fetch_openalex_rolling_journals_forever()