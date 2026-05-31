import os
import re
import json
import math
import numpy as np
import pandas as pd
from collections import defaultdict, Counter

from sentence_transformers import SentenceTransformer
import faiss

try:
    from transformers import pipeline
except Exception:
    pipeline = None


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_CSV = os.path.join(BASE, "data", "live_open_cfps.csv")
ROLLING_CSV = os.path.join(BASE, "data", "rolling_journals.csv")
FAISS_DIR = os.path.join(BASE, "faiss_openalex_papers")

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ZERO_SHOT_MODEL = "facebook/bart-large-mnli"


DOMAIN_LABELS = [
    "Artificial Intelligence and Machine Learning",
    "Internet of Things and Embedded Systems",
    "Big Data and Data Analytics",
    "Cybersecurity and Privacy",
    "Cloud Computing and Edge Computing",
    "Computer Networks and Communication",
    "Blockchain and Web3",
    "Natural Language Processing",
    "Computer Vision and Image Processing",
    "Software Engineering",
    "Database Systems",
    "Human Computer Interaction",
    "Robotics and Automation",
    "AR VR and Metaverse",
    "Quantum Computing",
    "High Performance Computing",
    "Bioinformatics and Health Informatics",
    "FinTech and Fraud Detection",
    "General Computer Science"
]


DOMAIN_KEYWORDS = {
    "Artificial Intelligence and Machine Learning": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "neural network", "neural networks", "transformer", "llm", "bert",
        "classification", "prediction", "regression", "clustering",
        "supervised learning", "unsupervised learning", "reinforcement learning",
        "generative ai", "gan", "cnn", "rnn", "lstm", "xgboost", "random forest"
    ],

    "Internet of Things and Embedded Systems": [
        "iot", "internet of things", "aiot", "artificial intelligence of things",
        "sensor", "sensors", "smart sensor", "wireless sensor network",
        "wsn", "embedded", "embedded system", "microcontroller",
        "arduino", "raspberry pi", "actuator", "actuators",
        "mqtt", "lora", "lorawan", "zigbee", "nb-iot",
        "smart agriculture", "smart farming", "precision agriculture",
        "smart home", "smart city", "wearable", "wearables",
        "connected devices", "cyber physical system", "cps",
        "remote monitoring", "real time monitoring", "environment monitoring",
        "industrial iot", "iiot", "edge device", "edge devices"
    ],

    "Big Data and Data Analytics": [
        "big data", "data analytics", "data science", "data mining",
        "hadoop", "spark", "apache spark", "apache hadoop",
        "kafka", "flink", "hive", "pig", "mapreduce",
        "data lake", "data warehouse", "data engineering",
        "etl", "elt", "data pipeline", "data pipelines",
        "stream processing", "batch processing", "real time analytics",
        "large scale data", "distributed analytics",
        "business intelligence", "predictive analytics",
        "recommendation system", "recommender system",
        "analytics platform", "nosql analytics"
    ],

    "Cybersecurity and Privacy": [
        "cybersecurity", "cyber security", "security", "privacy",
        "attack", "attacks", "malware", "phishing", "ransomware",
        "intrusion detection", "ids", "threat", "vulnerability",
        "authentication", "authorization", "encryption",
        "network security", "iot security", "cloud security",
        "zero trust", "access control", "digital forensics",
        "anomaly detection", "fraud detection", "secure"
    ],

    "Cloud Computing and Edge Computing": [
        "cloud", "cloud computing", "edge", "edge computing",
        "fog", "fog computing", "serverless", "microservices",
        "virtualization", "container", "containers", "docker",
        "kubernetes", "distributed system", "distributed computing",
        "cloud native", "edge ai", "mobile edge computing",
        "multi cloud", "hybrid cloud"
    ],

    "Computer Networks and Communication": [
        "network", "networks", "computer network", "routing",
        "wireless", "5g", "6g", "sdn", "software defined networking",
        "network protocol", "communication", "mobile network",
        "vehicular network", "vanet", "manet", "delay tolerant network",
        "optical network", "internet protocol", "tcp", "udp"
    ],

    "Blockchain and Web3": [
        "blockchain", "web3", "smart contract", "ethereum",
        "bitcoin", "cryptocurrency", "distributed ledger",
        "decentralized", "defi", "nft", "consensus",
        "proof of work", "proof of stake", "hyperledger"
    ],

    "Natural Language Processing": [
        "nlp", "natural language processing", "text mining",
        "sentiment analysis", "language model", "large language model",
        "llm", "bert", "gpt", "translation", "summarization",
        "question answering", "chatbot", "text classification",
        "named entity recognition", "ner", "speech recognition"
    ],

    "Computer Vision and Image Processing": [
        "computer vision", "image processing", "image classification",
        "object detection", "segmentation", "face recognition",
        "ocr", "video analytics", "medical imaging",
        "cnn", "yolo", "image recognition", "visual recognition"
    ],

    "Software Engineering": [
        "software engineering", "software testing", "testing",
        "debugging", "requirements engineering", "software maintenance",
        "code analysis", "program analysis", "agile", "devops",
        "software architecture", "api", "backend", "frontend",
        "web application", "software quality"
    ],

    "Database Systems": [
        "database", "dbms", "sql", "nosql", "query processing",
        "transaction", "indexing", "data warehouse", "mongodb",
        "postgresql", "mysql", "graph database", "knowledge graph",
        "rdf", "sparql"
    ],

    "Human Computer Interaction": [
        "hci", "human computer interaction", "user experience",
        "ux", "ui", "usability", "interaction design",
        "user interface", "accessibility", "user study"
    ],

    "Robotics and Automation": [
        "robot", "robotics", "automation", "autonomous",
        "drone", "uav", "path planning", "slam",
        "robot control", "humanoid", "manipulator"
    ],

    "AR VR and Metaverse": [
        "augmented reality", "virtual reality", "mixed reality",
        "extended reality", "ar", "vr", "xr", "metaverse",
        "3d interaction", "immersive"
    ],

    "Quantum Computing": [
        "quantum", "quantum computing", "quantum algorithm",
        "qubit", "quantum cryptography", "quantum machine learning"
    ],

    "High Performance Computing": [
        "hpc", "high performance computing", "parallel computing",
        "gpu computing", "cuda", "supercomputing",
        "parallel processing", "distributed processing"
    ],

    "Bioinformatics and Health Informatics": [
        "bioinformatics", "health informatics", "medical informatics",
        "healthcare", "disease prediction", "clinical",
        "genomics", "biomedical", "iot healthcare", "iomt",
        "internet of medical things"
    ],

    "FinTech and Fraud Detection": [
        "fintech", "financial technology", "fraud", "fraud detection",
        "gst fraud", "tax fraud", "invoice fraud", "credit card fraud",
        "anti money laundering", "aml", "financial crime",
        "risk scoring", "payment fraud"
    ],

    "General Computer Science": [
        "algorithm", "computer science", "computing", "information technology",
        "informatics", "system", "application"
    ]
}


DOMAIN_ALIASES = {
    "Internet of Things and Embedded Systems": [
        "iot", "aiot", "smart agriculture", "smart farming", "sensor",
        "edge device", "embedded", "mqtt", "lora"
    ],
    "Big Data and Data Analytics": [
        "big data", "spark", "hadoop", "kafka", "data analytics",
        "data engineering", "data lake", "stream processing"
    ],
    "Cloud Computing and Edge Computing": [
        "edge computing", "fog computing", "cloud", "serverless",
        "kubernetes", "distributed"
    ],
    "Cybersecurity and Privacy": [
        "cybersecurity", "security", "privacy", "attack",
        "intrusion", "malware", "threat"
    ],
    "Artificial Intelligence and Machine Learning": [
        "ai", "ml", "machine learning", "deep learning", "neural"
    ]
}


def clean(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def norm_title(x):
    return re.sub(r"[^a-z0-9]+", " ", clean(x).lower()).strip()


def tokens(x):
    stop = {
        "the", "and", "for", "with", "using", "based", "from", "this", "that",
        "into", "study", "approach", "system", "method", "model", "paper",
        "new", "novel", "towards", "via", "through", "over", "under"
    }
    return [
        w for w in re.findall(r"[a-zA-Z0-9]+", clean(x).lower())
        if len(w) > 2 and w not in stop
    ]


def safe_float(x):
    try:
        if pd.isna(x):
            return 0.0
        x = str(x).replace(",", "").strip()
        if x == "":
            return 0.0
        nums = re.findall(r"\d+\.?\d*", x)
        return float(nums[0]) if nums else 0.0
    except Exception:
        return 0.0


def phrase_count(text, phrases):
    text = clean(text).lower()
    score = 0.0

    for phrase in phrases:
        phrase = phrase.lower().strip()

        if not phrase:
            continue

        if phrase in text:
            words = phrase.split()

            if len(words) >= 3:
                score += 4.0
            elif len(words) == 2:
                score += 2.5
            else:
                score += 1.0

    return score


class SmartVenueRecommender:
    def __init__(self):
        print("Loading embedding model...")
        self.model = SentenceTransformer(EMBED_MODEL)

        print("Loading zero-shot classifier...")
        self.zero_shot = None

        if pipeline:
            try:
                self.zero_shot = pipeline(
                    "zero-shot-classification",
                    model=ZERO_SHOT_MODEL
                )
            except Exception as e:
                print("Zero-shot model unavailable, using keyword fallback:", e)

        self.live_df = self.load_csv(LIVE_CSV, "conference")
        self.rolling_df = self.load_csv(ROLLING_CSV, "journal")
        self.venues_df = pd.concat([self.live_df, self.rolling_df], ignore_index=True)

        self.index, self.paper_meta = self.load_faiss()

        print("Building relational graph...")
        self.graph = self.build_relational_graph()

    def load_csv(self, path, default_type):
        if not os.path.exists(path):
            print("Missing CSV:", path)
            return pd.DataFrame()

        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]

        if "venue_type" in df.columns and "type" not in df.columns:
            df["type"] = df["venue_type"]

        if "type" not in df.columns:
            df["type"] = default_type

        required_cols = [
            "title", "publisher", "source", "topics", "url", "official_url",
            "page_url", "submission_url", "deadline", "open_until",
            "h_index", "h5_index", "sjr", "impact_factor", "quartile",
            "q_rank", "core_rank", "acceptance_rate", "paid",
            "presentation_type", "indexed", "subject_area"
        ]

        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        df["title"] = df["title"].apply(clean)
        df["title_norm"] = df["title"].apply(norm_title)

        df["search_text"] = (
            df["title"].fillna("").astype(str) + " " +
            df["topics"].fillna("").astype(str) + " " +
            df["subject_area"].fillna("").astype(str) + " " +
            df["publisher"].fillna("").astype(str) + " " +
            df["source"].fillna("").astype(str) + " " +
            df["indexed"].fillna("").astype(str)
        ).str.lower()

        df = df[df["title_norm"] != ""]
        df = df.drop_duplicates(subset=["title_norm", "type"], keep="first")

        return df.reset_index(drop=True)

    def load_faiss(self):
        try:
            from backend.faiss_paper_store import load_faiss_bundle
        except ImportError:
            from faiss_paper_store import load_faiss_bundle

        try:
            index, meta = load_faiss_bundle(FAISS_DIR, cache_dir=os.path.join(BASE, "cache"))
        except Exception as e:
            print("FAISS load failed:", e)
            return None, []

        if index is None or not meta:
            print("FAISS index or metadata not found.")
            return None, []

        print("FAISS loaded:", len(meta), "papers")
        return index, meta

    def detect_domains(self, title, abstract=""):
        text = f"{title}. {abstract}".lower().strip()
        scores = defaultdict(float)

        for domain, kws in DOMAIN_KEYWORDS.items():
            scores[domain] += phrase_count(text, kws)

        for domain, aliases in DOMAIN_ALIASES.items():
            scores[domain] += phrase_count(text, aliases) * 1.5

        # Special interdisciplinary fixes
        if "artificial intelligence of things" in text or "aiot" in text:
            scores["Internet of Things and Embedded Systems"] += 8
            scores["Artificial Intelligence and Machine Learning"] += 4

        if "smart agriculture" in text or "smart farming" in text or "precision agriculture" in text:
            scores["Internet of Things and Embedded Systems"] += 6
            scores["Bioinformatics and Health Informatics"] += 1

        if "edge computing" in text or "edge ai" in text:
            scores["Cloud Computing and Edge Computing"] += 6
            scores["Internet of Things and Embedded Systems"] += 3

        if "big data" in text:
            scores["Big Data and Data Analytics"] += 8

        if "fraud detection" in text or "gst fraud" in text:
            scores["FinTech and Fraud Detection"] += 7
            scores["Cybersecurity and Privacy"] += 3
            scores["Artificial Intelligence and Machine Learning"] += 2

        if self.zero_shot:
            try:
                result = self.zero_shot(
                    text,
                    DOMAIN_LABELS,
                    multi_label=True
                )

                for label, zscore in zip(result["labels"], result["scores"]):
                    scores[label] += float(zscore) * 4.0

            except Exception as e:
                print("Zero-shot failed, using keyword scoring only:", e)

        sorted_domains = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        top_domains = [
            {"domain": d, "score": round(float(s), 3)}
            for d, s in sorted_domains
            if s > 1.0
        ]

        if not top_domains:
            top_domains = [{"domain": "General Computer Science", "score": 1.0}]

        return top_domains[:4]

    def build_relational_graph(self):
        graph = defaultdict(lambda: defaultdict(float))

        if self.venues_df.empty:
            return graph

        for _, row in self.venues_df.iterrows():
            venue = "venue:" + row["title_norm"]
            venue_type = "type:" + norm_title(row.get("type"))
            publisher = "publisher:" + norm_title(row.get("publisher") or row.get("source"))

            graph[venue][venue_type] += 1.0
            graph[venue_type][venue] += 1.0

            if publisher != "publisher:":
                graph[venue][publisher] += 0.7
                graph[publisher][venue] += 0.7

            topic_text = clean(row.get("topics")) + " " + clean(row.get("search_text"))
            topic_tokens = Counter(tokens(topic_text))

            for t, freq in topic_tokens.most_common(35):
                topic = "topic:" + t
                weight = min(1.0, 0.2 + freq * 0.1)
                graph[venue][topic] += weight
                graph[topic][venue] += weight

        return graph

    def expand_query_topics(self, title, abstract, detected_domains):
        query_tokens = tokens(title + " " + abstract)
        domain_tokens = []

        for item in detected_domains:
            domain = item["domain"]
            for kw in DOMAIN_KEYWORDS.get(domain, []):
                domain_tokens.extend(tokens(kw))

        combined = Counter(query_tokens + domain_tokens)
        return [t for t, _ in combined.most_common(35)]

    def keyword_score(self, query, venue_text):
        q = set(tokens(query))
        v = set(tokens(venue_text))

        if not q or not v:
            return 0.0

        overlap = len(q & v) / max(1, len(q))

        q_text = clean(query).lower()
        v_text = clean(venue_text).lower()

        phrase_bonus = 0.0

        for domain, kws in DOMAIN_KEYWORDS.items():
            for kw in kws:
                if kw in q_text and kw in v_text:
                    phrase_bonus += 0.08

        return min(1.0, overlap + min(0.35, phrase_bonus))

    def domain_venue_score(self, venue_text, detected_domains):
        venue_text = clean(venue_text).lower()

        score = 0.0

        for rank, item in enumerate(detected_domains):
            domain = item["domain"]
            weight = max(0.35, 1.0 - rank * 0.20)

            hits = phrase_count(venue_text, DOMAIN_KEYWORDS.get(domain, []))
            alias_hits = phrase_count(venue_text, DOMAIN_ALIASES.get(domain, []))

            domain_score = min((hits + alias_hits * 1.5) / 10.0, 1.0)
            score += domain_score * weight

        return min(score, 1.0)

    def quality_score(self, row):
        score = 0.0

        h = max(safe_float(row.get("h_index")), safe_float(row.get("h5_index")))
        score += min(h / 120, 1.0) * 0.30

        sjr = safe_float(row.get("sjr"))
        score += min(sjr / 3, 1.0) * 0.20

        impact = safe_float(row.get("impact_factor"))
        score += min(impact / 10, 1.0) * 0.20

        q = clean(row.get("q_rank") or row.get("quartile")).upper()

        if "Q1" in q:
            score += 0.20
        elif "Q2" in q:
            score += 0.14
        elif "Q3" in q:
            score += 0.08
        elif "Q4" in q:
            score += 0.04

        core = clean(row.get("core_rank")).upper().replace(" ", "")

        if core == "A*":
            score += 0.20
        elif core == "A":
            score += 0.16
        elif core == "B":
            score += 0.10
        elif core == "C":
            score += 0.05

        return min(score, 1.0)

    def faiss_venue_scores(self, title, abstract="", top_n=100):
        if self.index is None or not self.paper_meta:
            return {}, []

        query = f"{title}. {abstract}"
        emb = self.model.encode([query], normalize_embeddings=True).astype("float32")
        scores, ids = self.index.search(emb, top_n)

        venue_counter = defaultdict(float)
        similar_papers = []

        for sim, idx in zip(scores[0], ids[0]):
            if idx < 0 or idx >= len(self.paper_meta):
                continue

            m = self.paper_meta[idx]

            venue = (
                m.get("venue")
                or m.get("host_venue")
                or m.get("source")
                or m.get("journal")
                or m.get("conference")
                or ""
            )

            paper_title = clean(m.get("title") or m.get("paper_title") or "")
            paper_topics = clean(m.get("topics") or m.get("concepts") or "")

            venue_n = norm_title(venue)

            if venue_n:
                venue_counter[venue_n] += float(sim)

            similar_papers.append({
                "title": paper_title,
                "venue": clean(venue),
                "topics": paper_topics,
                "similarity": round(float(sim), 4)
            })

        if not venue_counter:
            return {}, similar_papers[:10]

        max_score = max(venue_counter.values())
        normalized = {k: v / max_score for k, v in venue_counter.items()}

        return normalized, similar_papers[:10]

    def pagr_score(self, row, detected_domains, query_topics, faiss_scores):
        venue_norm = row["title_norm"]
        venue_node = "venue:" + venue_norm

        if venue_node not in self.graph:
            return 0.0

        score = 0.0
        venue_text = clean(row.get("search_text")).lower()

        score += self.domain_venue_score(venue_text, detected_domains) * 0.35

        topic_score = 0.0

        for topic in query_topics:
            topic_node = "topic:" + topic

            if topic_node in self.graph and venue_node in self.graph[topic_node]:
                topic_score += self.graph[topic_node][venue_node]

        score += min(topic_score / 7, 1.0) * 0.30

        if venue_norm in faiss_scores:
            score += 0.25 * faiss_scores[venue_norm]

        for fv, fs in faiss_scores.items():
            if venue_norm and (venue_norm in fv or fv in venue_norm):
                score += 0.15 * fs

        publisher = norm_title(row.get("publisher") or row.get("source"))

        if publisher:
            publisher_node = "publisher:" + publisher

            if publisher_node in self.graph and venue_node in self.graph[publisher_node]:
                score += 0.05

        return min(score, 1.0)

    def deadline_score(self, row):
        deadline = clean(row.get("deadline") or row.get("open_until"))

        if deadline:
            return 1.0

        if clean(row.get("type")).lower() == "journal":
            return 0.5

        return 0.2

    def recommendation_boost(self, row, detected_domains):
        text = clean(row.get("search_text")).lower()
        boost = 0.0
        domain_names = [d["domain"] for d in detected_domains]

        if "Internet of Things and Embedded Systems" in domain_names:
            if any(x in text for x in ["iot", "internet of things", "sensor", "smart", "embedded", "edge"]):
                boost += 0.08

        if "Big Data and Data Analytics" in domain_names:
            if any(x in text for x in ["big data", "analytics", "data mining", "spark", "hadoop", "data"]):
                boost += 0.07

        if "Cybersecurity and Privacy" in domain_names:
            if any(x in text for x in ["security", "cyber", "privacy", "attack", "intrusion"]):
                boost += 0.07

        if "Cloud Computing and Edge Computing" in domain_names:
            if any(x in text for x in ["cloud", "edge", "fog", "distributed"]):
                boost += 0.06

        return min(boost, 0.15)

    def recommend(self, title, abstract="", top_k=10, venue_type="all"):
        detected_domains = self.detect_domains(title, abstract)
        domain_names = [d["domain"] for d in detected_domains]

        query = f"{title} {abstract} {' '.join(domain_names)}"
        query_topics = self.expand_query_topics(title, abstract, detected_domains)

        faiss_scores, similar_papers = self.faiss_venue_scores(title, abstract)

        df = self.venues_df.copy()

        if df.empty:
            return {
                "domain": domain_names[0],
                "detected_domain": domain_names[0],
                "detected_domains": detected_domains,
                "recommendations": [],
                "status": "no_data"
            }

        if venue_type and venue_type.lower() != "all":
            df = df[df["type"].astype(str).str.lower() == venue_type.lower()]

        recs = []

        for _, row in df.iterrows():
            kscore = self.keyword_score(query, row["search_text"])
            dmscore = self.domain_venue_score(row["search_text"], detected_domains)
            graph_score = self.pagr_score(row, detected_domains, query_topics, faiss_scores)
            qscore = self.quality_score(row)
            dscore = self.deadline_score(row)
            boost = self.recommendation_boost(row, detected_domains)

            final = (
                0.25 * kscore +
                0.25 * dmscore +
                0.25 * graph_score +
                0.15 * qscore +
                0.10 * dscore +
                boost
            )

            if final <= 0.04:
                continue

            recs.append({
                "id": str(abs(hash(clean(row.get("title")))) % 10000000),
                "title": clean(row.get("title")),
                "type": clean(row.get("type")),
                "publisher": clean(row.get("publisher") or row.get("source")),
                "source": clean(row.get("source")),
                "topics": clean(row.get("topics")),
                "subject_area": clean(row.get("subject_area")),

                "url": clean(row.get("url")),
                "official_url": clean(row.get("official_url") or row.get("url")),
                "page_url": clean(row.get("page_url") or row.get("url")),
                "submission_url": clean(row.get("submission_url") or row.get("url")),
                "deadline": clean(row.get("deadline") or row.get("open_until")),
                "open_until": clean(row.get("open_until") or row.get("deadline")),

                "h_index": clean(row.get("h_index")),
                "h5_index": clean(row.get("h5_index")),
                "sjr": clean(row.get("sjr")),
                "impact_factor": clean(row.get("impact_factor")),
                "q_rank": clean(row.get("q_rank") or row.get("quartile")),
                "core_rank": clean(row.get("core_rank")),
                "acceptance_rate": clean(row.get("acceptance_rate")),
                "paid": clean(row.get("paid")),
                "presentation_type": clean(row.get("presentation_type")),
                "indexed": clean(row.get("indexed")),

                "recommendation_score": round(final * 100, 2),
                "keyword_score": round(kscore * 100, 2),
                "domain_score": round(dmscore * 100, 2),
                "graph_score": round(graph_score * 100, 2),
                "pagr_score": round(graph_score * 100, 2),
                "quality_score": round(qscore * 100, 2),
                "deadline_score": round(dscore * 100, 2),
                "boost_score": round(boost * 100, 2),

                "detected_domains": domain_names,

                "match_reason": (
                    f"Detected domains: {', '.join(domain_names)}. "
                    f"Recommended using multi-domain detection, keyword overlap, "
                    f"FAISS semantic retrieval, PAGR relational graph ranking, "
                    f"venue quality metrics, and deadline availability."
                )
            })

        recs = sorted(recs, key=lambda x: x["recommendation_score"], reverse=True)

        return {
            "domain": domain_names[0],
            "detected_domain": domain_names[0],
            "detected_domains": detected_domains,
            "query_topics": query_topics[:15],
            "recommendations": recs[:top_k],
            "total": min(len(recs), top_k),
            "similar_papers_used": similar_papers,
            "sources": [
                "live_open_cfps.csv",
                "rolling_journals.csv",
                "FAISS OpenAlex papers",
                "multi-domain classifier",
                "relational graph ranking",
                "prestige metadata"
            ],
            "ranking_formula": {
                "keyword_score": "25%",
                "domain_score": "25%",
                "pagr_graph_score": "25%",
                "quality_score": "15%",
                "deadline_score": "10%",
                "domain_boost": "up to 15%"
            },
            "status": "success"
        }


if __name__ == "__main__":
    rec = SmartVenueRecommender()

    result = rec.recommend(
        title="Artificial intelligence of things for smart agriculture with edge computing",
        abstract="IoT sensors, edge computing and AI are used for smart agriculture monitoring.",
        top_k=10
    )

    print(json.dumps(result, indent=2))