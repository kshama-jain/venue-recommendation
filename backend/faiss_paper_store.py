"""
Load OpenAlex papers from FAISS + metadata for semantic search.

Supports the seeder layout:
  faiss_openalex_papers/papers.faiss
  faiss_openalex_papers/metadata_part_*.parquet

Also supports legacy layout:
  papers.index + metadata.json
"""

from __future__ import annotations

import glob
import json
import os
import pickle
import time
from typing import Any

import faiss
import numpy as np
import pandas as pd

DEFAULT_FAISS_DIR = os.environ.get(
    "FAISS_PAPERS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "faiss_openalex_papers"),
)
DEFAULT_CACHE_DIR = os.environ.get(
    "FAISS_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache"),
)

INDEX_CANDIDATES = ("papers.faiss", "papers.index", "index.faiss")
META_JSON_CANDIDATES = ("metadata.json", "papers_metadata.json")
META_CACHE_FILE = "faiss_paper_metadata.pkl"


def _pick(row: Any, names: tuple[str, ...]) -> str:
    for name in names:
        if name in row.index if hasattr(row, "index") else name in row:
            val = row[name] if hasattr(row, "__getitem__") else getattr(row, name, None)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                if pd.isna(val):
                    continue
                return str(val).strip()
    return ""


def parquet_row_to_meta(row: pd.Series) -> dict[str, Any]:
    """Normalize a parquet/CSV row for recommender + search consumers."""
    title = _pick(row, ("title", "paper_title", "display_name"))
    abstract = _pick(row, ("abstract", "abstract_text"))
    venue = _pick(
        row,
        (
            "venue_name",
            "venue",
            "host_venue",
            "source",
            "source_display_name",
            "journal",
            "journal_name",
            "conference",
            "container_title",
        ),
    )
    year = _pick(row, ("publication_year", "year"))
    concepts = _pick(row, ("concepts", "topics", "concept_ids"))

    return {
        "id": _pick(row, ("id", "openalex_id", "work_id")),
        "doi": _pick(row, ("doi",)),
        "title": title,
        "abstract": abstract,
        "venue": venue,
        "venue_name": venue,
        "year": year,
        "publication_year": year,
        "concepts": concepts,
        "topics": concepts,
    }


def _find_index_path(faiss_dir: str) -> str | None:
    for name in INDEX_CANDIDATES:
        path = os.path.join(faiss_dir, name)
        if os.path.exists(path):
            return path
    return None


def _find_meta_json_path(faiss_dir: str) -> str | None:
    for name in META_JSON_CANDIDATES:
        path = os.path.join(faiss_dir, name)
        if os.path.exists(path):
            return path
    return None


def load_metadata_from_parquet(faiss_dir: str) -> list[dict[str, Any]]:
    parts = sorted(glob.glob(os.path.join(faiss_dir, "metadata_part_*.parquet")))
    if not parts:
        return []

    meta: list[dict[str, Any]] = []
    for path in parts:
        df = pd.read_parquet(path)
        for _, row in df.iterrows():
            meta.append(parquet_row_to_meta(row))
    return meta


def load_metadata(
    faiss_dir: str,
    cache_dir: str | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
    max_cache_age_sec: int = 7 * 86400,
) -> list[dict[str, Any]]:
    json_path = _find_meta_json_path(faiss_dir)
    if json_path:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    parts = sorted(glob.glob(os.path.join(faiss_dir, "metadata_part_*.parquet")))
    if not parts:
        return []

    if cache_dir and use_cache:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, META_CACHE_FILE)
        newest_part = max(os.path.getmtime(p) for p in parts)
        if os.path.exists(cache_path):
            cache_age = time.time() - os.path.getmtime(cache_path)
            if cache_age < max_cache_age_sec and os.path.getmtime(cache_path) >= newest_part:
                with open(cache_path, "rb") as f:
                    cached = pickle.load(f)
                if isinstance(cached, list) and cached:
                    return cached

    meta = load_metadata_from_parquet(faiss_dir)

    if cache_dir and use_cache and meta:
        cache_path = os.path.join(cache_dir, META_CACHE_FILE)
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(meta, f, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError:
            pass

    return meta


def load_faiss_bundle(
    faiss_dir: str | None = None,
    cache_dir: str | None = DEFAULT_CACHE_DIR,
    use_cache: bool = True,
) -> tuple[Any | None, list[dict[str, Any]]]:
    """
    Returns (faiss_index, metadata_list) aligned by vector id.
    metadata_list[i] corresponds to FAISS id i.
    """
    faiss_dir = faiss_dir or DEFAULT_FAISS_DIR
    index_path = _find_index_path(faiss_dir)
    if not index_path:
        return None, []

    index = faiss.read_index(index_path)
    meta = load_metadata(faiss_dir, cache_dir=cache_dir, use_cache=use_cache)

    if index.ntotal != len(meta):
        raise ValueError(
            f"FAISS/metadata mismatch: index has {index.ntotal} vectors "
            f"but metadata has {len(meta)} rows in {faiss_dir}"
        )

    return index, meta


class FaissPaperStore:
    """Semantic search over indexed papers."""

    def __init__(
        self,
        faiss_dir: str | None = None,
        cache_dir: str | None = DEFAULT_CACHE_DIR,
        embed_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        from sentence_transformers import SentenceTransformer

        self.faiss_dir = faiss_dir or DEFAULT_FAISS_DIR
        self.index, self.meta = load_faiss_bundle(
            self.faiss_dir, cache_dir=cache_dir, use_cache=True
        )
        self.model = SentenceTransformer(embed_model_name)
        if hasattr(self.model, "get_embedding_dimension"):
            self.dim = self.model.get_embedding_dimension()
        else:
            self.dim = self.model.get_sentence_embedding_dimension()

    @property
    def ready(self) -> bool:
        return self.index is not None and bool(self.meta)

    @property
    def size(self) -> int:
        return 0 if self.index is None else int(self.index.ntotal)

    def encode_query(self, text: str) -> np.ndarray:
        emb = self.model.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(emb, dtype="float32")

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        if not self.ready:
            return []

        top_k = min(top_k, self.size)
        emb = self.encode_query(query)
        scores, ids = self.index.search(emb, top_k)

        hits: list[dict[str, Any]] = []
        for sim, idx in zip(scores[0], ids[0]):
            if idx < 0 or idx >= len(self.meta):
                continue
            row = dict(self.meta[idx])
            row["similarity"] = round(float(sim), 4)
            row["faiss_id"] = int(idx)
            hits.append(row)
        return hits
