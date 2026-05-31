import os
import re
import json
import math
import numpy as np
import pandas as pd
from collections import defaultdict, Counter
import pickle
import hashlib
from functools import lru_cache
import time

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
CACHE_DIR = os.path.join(BASE, "cache")

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ZERO_SHOT_MODEL = "facebook/bart-large-mnli"

# Create cache directory
os.makedirs(CACHE_DIR, exist_ok=True)

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
    "FinTech and Fraud Detection": [
        "fintech", "fraud", "gst", "tax", "invoice", "payment",
        "transaction", "banking", "financial", "credit", "debit",
        "money laundering", "anti-money laundering", "aml", "kyc",
        "know your customer", "identity verification", "biometric",
        "authentication", "cybersecurity", "risk assessment"
    ],
    "Big Data and Data Analytics": [
        "big data", "spark", "hadoop", "kafka", "data analytics",
        "data engineering", "data lake", "stream processing", "real-time"
    ],
    "Artificial Intelligence and Machine Learning": [
        "ai", "ml", "machine learning", "deep learning", "neural",
        "transformer", "bert", "gpt", "llm", "classification",
        "regression", "clustering", "anomaly detection"
    ],
    "Cybersecurity and Privacy": [
        "cybersecurity", "security", "privacy", "attack",
        "intrusion", "malware", "threat", "vulnerability",
        "encryption", "authentication", "authorization"
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


def get_cache_key(title, abstract, **kwargs):
    """Generate cache key for recommendations"""
    content = f"{title}|{abstract}|{sorted(kwargs.items())}"
    return hashlib.md5(content.encode()).hexdigest()


class OptimizedSmartVenueRecommender:
    _instance = None
    _model = None
    _zero_shot = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'initialized'):
            return
            
        print("Initializing Optimized Smart Venue Recommender...")
        start_time = time.time()
        
        # Lazy load models
        self.model = None
        self.zero_shot = None
        
        # Load data
        print("Loading venue data...")
        self.live_df = self._load_csv_optimized(LIVE_CSV, "conference")
        self.rolling_df = self._load_csv_optimized(ROLLING_CSV, "journal")
        self.venues_df = pd.concat([self.live_df, self.rolling_df], ignore_index=True)
        
        # FAISS is optional and loaded lazily (500k vectors — slow on startup)
        self.faiss_index = None
        self.faiss_meta = []

        # Pre-compute graph
        print("Building optimized graph...")
        self.graph = self._build_relational_graph_optimized()
        
        # Recommendation cache
        self.recommendation_cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        self.initialized = True
        load_time = time.time() - start_time
        print(f"Optimized recommender ready in {load_time:.2f} seconds")
    
    def _get_model(self):
        """Lazy load sentence transformer model"""
        if self.model is None:
            print("Loading embedding model...")
            self.model = SentenceTransformer(EMBED_MODEL)
        return self.model
    
    def _get_zero_shot(self):
        """Lazy load zero-shot classifier"""
        if self.zero_shot is None and pipeline:
            try:
                print("Loading zero-shot classifier...")
                self.zero_shot = pipeline(
                    "zero-shot-classification",
                    model=ZERO_SHOT_MODEL
                )
            except Exception as e:
                print("Zero-shot model unavailable:", e)
        return self.zero_shot
    
    def _load_csv_optimized(self, path, default_type):
        """Optimized CSV loading with minimal processing"""
        if not os.path.exists(path):
            print(f"Missing CSV: {path}")
            return pd.DataFrame()

        # Determine available columns first, then load only what exists
        desired_cols = [
            'title', 'acronym', 'venue_type', 'source', 'publisher',
            'topics', 'subject_area', 'h_index', 'impact_score', 'sjr',
            'quartile', 'core_rank', 'prestige_score', 'deadline',
            'open_status', 'paid_or_free', 'location', 'official_url',
            'open_until', 'event_start', 'event_end',
        ]
        try:
            header_df = pd.read_csv(path, nrows=0, low_memory=False)
            available = [c.strip().lower() for c in header_df.columns]
            load_cols = [c for c in desired_cols if c in available]
            if not load_cols:
                load_cols = None  # load everything
        except Exception:
            load_cols = None

        try:
            df = pd.read_csv(path, usecols=load_cols, low_memory=False)
        except Exception:
            df = pd.read_csv(path, low_memory=False)

        df.columns = [c.strip().lower() for c in df.columns]

        # Set default type
        if "venue_type" not in df.columns:
            df["venue_type"] = default_type
        if "type" not in df.columns:
            df["type"] = df["venue_type"] if "venue_type" in df.columns else default_type

        # Ensure required text columns exist
        for col in ("title", "topics", "publisher"):
            if col not in df.columns:
                df[col] = ""

        # Clean essential fields
        df["title"] = df["title"].fillna("").astype(str)
        df["title_norm"] = df["title"].apply(norm_title)

        # Create search text
        df["search_text"] = (
            df["title"].fillna("").astype(str) + " " +
            df["topics"].fillna("").astype(str) + " " +
            df["publisher"].fillna("").astype(str)
        ).str.lower()

        # Filter and dedupe — use copy() only on deduplicated, consolidated frame
        df = df[df["title_norm"] != ""].drop_duplicates(subset=["title_norm", "type"], keep="first")
        df = df.reset_index(drop=True)
        # Convert object columns to avoid mixed-type fragmentation
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].astype(str)

        return df
    
    def _load_faiss_optimized(self):
        """Optimized FAISS loading with caching"""
        cache_file = os.path.join(CACHE_DIR, "faiss_cache.pkl")
        
        # Check cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    cached = pickle.load(f)
                    # Check if cache is fresh (within 24 hours)
                    if time.time() - cached['timestamp'] < 86400:
                        print("Using cached FAISS data")
                        return cached['index'], cached['meta']
            except:
                pass
        
        # Load fresh data (papers.faiss + parquet metadata parts)
        try:
            from backend.faiss_paper_store import load_faiss_bundle
        except ImportError:
            from faiss_paper_store import load_faiss_bundle

        try:
            index, meta = load_faiss_bundle(FAISS_DIR, cache_dir=CACHE_DIR)
        except Exception as e:
            print("FAISS load failed:", e)
            return None, []

        if index is None or not meta:
            print("FAISS index not found")
            return None, []
        
        # Cache the results
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'index': index,
                    'meta': meta,
                    'timestamp': time.time()
                }, f)
        except:
            pass
        
        print(f"FAISS loaded: {len(meta)} papers")
        return index, meta
    
    @lru_cache(maxsize=1000)
    def _detect_domain_cached(self, title, abstract):
        """Cached domain detection"""
        text = f"{title}. {abstract}".strip()
        
        zero_shot = self._get_zero_shot()
        if zero_shot:
            try:
                result = zero_shot(text, DOMAIN_LABELS)
                return result["labels"][0]
            except:
                pass
        
        # Keyword fallback
        low = text.lower()
        scores = {}
        
        for domain, kws in DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in kws if kw.lower() in low)
        
        best = max(scores.items(), key=lambda x: x[1])
        return best[0] if best[1] > 0 else "General Computer Science"
    
    def _build_relational_graph_optimized(self):
        """Optimized graph building with limited complexity"""
        graph = defaultdict(lambda: defaultdict(float))
        
        if self.venues_df.empty:
            return graph
        
        # Process in batches for memory efficiency
        batch_size = 1000
        for i in range(0, len(self.venues_df), batch_size):
            batch = self.venues_df.iloc[i:i+batch_size]
            
            for _, row in batch.iterrows():
                venue = "venue:" + row["title_norm"]
                venue_type = "type:" + norm_title(row.get("venue_type", row.get("type", "")))
                publisher = "publisher:" + norm_title(row.get("publisher", ""))
                
                # Add essential edges only
                graph[venue][venue_type] = 1.0
                graph[venue_type][venue] = 1.0
                
                if publisher and publisher != "publisher:":
                    graph[venue][publisher] = 0.7
                    graph[publisher][venue] = 0.7
        
        return graph
    
    @lru_cache(maxsize=500)
    def _keyword_score_cached(self, query, venue_text):
        """Cached keyword scoring"""
        q = set(tokens(query))
        v = set(tokens(venue_text))
        
        if not q or not v:
            return 0.0
        
        overlap = len(q & v) / max(1, len(q))
        return min(1.0, overlap)

    def _domain_keyword_score(self, domain, venue_text):
        venue_text = clean(venue_text).lower()
        keywords = DOMAIN_KEYWORDS.get(domain, [])
        if not venue_text or not keywords:
            return 0.0

        hits = 0
        for kw in keywords:
            if kw.lower() in venue_text:
                hits += 1

        return min(1.0, hits / max(1, min(len(keywords), 8)))
    
    def _parse_deadline_date(self, x):
        """Parse deadline-like fields; return date or None."""
        try:
            if pd.isna(x):
                return None
            s = str(x).strip()
            if not s:
                return None
            lower = s.lower()
            if lower in {"rolling", "not specified", "tba", "na", "n/a", "unknown"}:
                return None
            dt = pd.to_datetime(s, errors="coerce")
            if pd.isna(dt):
                return None
            return dt.date()
        except Exception:
            return None

    def _deadline_urgency(self, row):
        """
        Map upcoming deadlines to [0,1].
        - 0 when closed/old or missing
        - 1 when due in <= 90 days
        """
        # Respect open_status if present in the dataset.
        open_status = str(row.get("open_status", "")).strip().lower()
        if open_status and open_status not in {"open", "upcoming", "yes", "true"}:
            return 0.0

        dl = row.get("deadline") or row.get("open_until")
        d = self._parse_deadline_date(dl)
        if not d:
            return 0.0

        today = pd.Timestamp.now(tz=None).date()
        days_left = (d - today).days
        if days_left < 0:
            return 0.0
        return float(min(1.0, days_left / 90.0))

    def recommend(self, title, abstract="", top_k=10, venue_type="all"):
        """Optimized recommendation with caching"""
        # Check cache first
        cache_key = get_cache_key(title, abstract, top_k=top_k, venue_type=venue_type)
        
        if cache_key in self.recommendation_cache:
            cached = self.recommendation_cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                print("Using cached recommendations")
                return cached['result']
        
        # Generate recommendations
        start_time = time.time()
        
        # Domain detection
        domain = self._detect_domain_cached(title, abstract)
        
        # Filter venues (avoid full copy — just build a boolean mask)
        if venue_type and venue_type.lower() != "all":
            mask = self.venues_df["venue_type"].astype(str).str.lower() == venue_type.lower()
            df = self.venues_df[mask]
        else:
            df = self.venues_df
        
        if df.empty:
            return {
                "status": "success",
                "domain": domain,
                "detected_domain": domain,
                "recommendations": [],
                "total": 0,
            }
        
        # Simple keyword-based scoring (fast)
        query_text = f"{title} {abstract} {domain}".strip()

        # Stage 1: score every venue (no hard threshold) so results always come back
        candidates = []
        for _, row in df.iterrows():
            venue_text = row.get("search_text", "")
            if not venue_text:
                continue

            kscore = self._keyword_score_cached(query_text, venue_text)
            domain_score = self._domain_keyword_score(domain, venue_text)
            effective_keyword = max(kscore, domain_score * 0.8)

            prestige = min(safe_float(row.get("prestige_score", 0)) / 100, 1.0)
            urgency = self._deadline_urgency(row)

            # Preliminary score used only for ranking / choosing who gets semantic scoring
            preliminary = 0.55 * effective_keyword + 0.25 * prestige + 0.20 * urgency

            candidates.append({
                "row": row,
                "kscore": kscore,
                "domain_score": domain_score,
                "effective_keyword": effective_keyword,
                "prestige": prestige,
                "urgency": urgency,
                "preliminary": preliminary,
            })

        # Rank and pick top 200 for the slower semantic step
        candidates.sort(key=lambda x: x["preliminary"], reverse=True)
        sem_candidates = candidates[: min(200, len(candidates))]

        # Stage 2 (slower): semantic similarity using sentence embeddings.
        semantic_scores = {}
        model = None
        try:
            model = self._get_model()
        except Exception:
            model = None

        if model:
            query_emb = None
            try:
                texts = [query_text] + [c["row"]["search_text"] for c in sem_candidates]
                try:
                    embs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                except TypeError:
                    embs = model.encode(texts, convert_to_numpy=True)
                    embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-12)
                query_emb = embs[0]
                cand_embs = embs[1:]
                # cosine similarity in [-1,1]; map to [0,1]
                sims = cand_embs @ query_emb
                for c, sim in zip(sem_candidates, sims):
                    semantic_scores[id(c["row"])] = float((sim + 1.0) / 2.0)
            except Exception:
                semantic_scores = {}

        # Build final ranked recommendations.
        recs = []
        for c in sem_candidates:
            row = c["row"]
            q = clean(row.get("quartile", row.get("q_rank")))

            semantic = semantic_scores.get(id(row), 0.5)  # neutral fallback
            kscore = c["kscore"]
            domain_score = c.get("domain_score", 0.0)
            effective_keyword = c.get("effective_keyword", kscore)
            prestige = c["prestige"]
            urgency = c["urgency"]

            # Final score in [0,100]
            final_unit = 0.40 * effective_keyword + 0.30 * semantic + 0.20 * prestige + 0.10 * urgency
            final_score = max(0.0, min(1.0, float(final_unit)))

            recs.append({
                "id": str(abs(hash(clean(row.get("title")))) % 10000000),
                "title": clean(row.get("title")),
                "type": clean(row.get("venue_type", row.get("type"))),
                "publisher": clean(row.get("publisher")),
                "source": clean(row.get("source")),
                "topics": clean(row.get("topics")),
                "url": clean(row.get("official_url", row.get("page_url"))),
                "official_url": clean(row.get("official_url", row.get("page_url"))),
                "page_url": clean(row.get("page_url")),
                "submission_url": clean(row.get("submission_url")),
                "deadline": clean(row.get("deadline", row.get("open_until"))),
                "open_until": clean(row.get("open_until", row.get("deadline"))),
                "open_status": clean(row.get("open_status")),
                "event_start": clean(row.get("event_start")),
                "event_end": clean(row.get("event_end")),
                "location": clean(row.get("location")),
                "h_index": safe_float(row.get("h_index")),
                "h5_index": safe_float(row.get("h5_index")),
                "sjr": safe_float(row.get("sjr")),
                "impact_factor": safe_float(row.get("impact_factor", row.get("impact_score"))),
                "quartile": q,
                "q_rank": q,
                "core_rank": clean(row.get("core_rank")),
                "paid": clean(row.get("paid", row.get("paid_or_free"))),
                "paid_or_free": clean(row.get("paid_or_free")),
                "access_model": clean(row.get("access_model")),
                "fee_text": clean(row.get("fee_text")),
                "indexed": clean(row.get("indexed")),
                "prestige_score": safe_float(row.get("prestige_score")),
                "recommendation_score": round(final_score * 100, 2),
                "keyword_score": round(kscore * 100, 2),
                "domain_score": round(domain_score * 100, 2),
                "semantic_score": round(semantic * 100, 2),
                "deadline_urgency": round(urgency * 100, 2),
                "match_reason": (
                    f"Matched by keywords (x{round(kscore*100,1)}), "
                    f"domain relevance (x{round(domain_score*100,1)}), "
                    f"semantic similarity (x{round(semantic*100,1)}), "
                    f"prestige (x{round(prestige*100,1)}), "
                    f"and deadline urgency (x{round(urgency*100,1)})."
                ),
            })

        # Sort and limit
        recs = sorted(recs, key=lambda x: x["recommendation_score"], reverse=True)[:top_k]
        
        result = {
            "status": "success",
            "domain": domain,
            "detected_domain": domain,
            "detected_labels": [domain],
            "sources": [
                "live_open_cfps.csv",
                "rolling_journals.csv",
                "keyword domain detection",
            ],
            "recommendations": recs,
            "total": len(recs),
            "processing_time": round(time.time() - start_time, 3),
        }
        
        # Cache the result
        self.recommendation_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }
        
        # Clean old cache entries
        current_time = time.time()
        self.recommendation_cache = {
            k: v for k, v in self.recommendation_cache.items()
            if current_time - v['timestamp'] < self.cache_ttl
        }
        
        return result


# Singleton instance
_recommender_instance = None

def get_recommender():
    """Get singleton recommender instance"""
    global _recommender_instance
    if _recommender_instance is None:
        _recommender_instance = OptimizedSmartVenueRecommender()
    return _recommender_instance
