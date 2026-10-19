"""Policy-clause retrieval for citation only — never a decision input.

Two backends over the same chunks:
- "qdrant": bge-small-en-v1.5 (384-dim, fastembed, in-process) into Qdrant
  local mode. Re-embedded on startup rather than relying on persisted state.
- "keyword": token-overlap scoring, no model download. Used in CI.
"""
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_FILE = ROOT / "policy_docs" / "fp57_guidance.md"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
COLLECTION = "fp57_policy"
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "of", "to", "and", "or", "is", "for", "in", "on", "at", "be", "it", "this", "that", "with",
    "was", "how", "what", "which", "when", "do", "does", "did", "i", "my", "me", "you", "your", "can", "could",
    "have", "has", "had", "will", "would", "there", "are", "get", "if", "any", "after", "this", "we", "our",
}


@dataclass(frozen=True)
class Chunk:
    chunk_id: int
    heading: str
    text: str


def load_chunks(path: Path = POLICY_FILE) -> list[Chunk]:
    """One chunk per '## ' section; the HTML provenance comment is dropped."""
    body = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    chunks = []
    for i, section in enumerate(s for s in body.split("\n## ") if s.strip()):
        heading, _, text = section.lstrip("# ").partition("\n")
        chunks.append(Chunk(i, heading.strip(), " ".join(text.split())))
    return chunks


def _stem(t: str) -> str:
    """Crude suffix stripping so "claiming"/"claims"/"claimed" all match "claim"."""
    for suffix in ("ing", "ed", "es", "s"):
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            return t[: -len(suffix)]
    return t


def _tokens(s: str) -> set[str]:
    return {_stem(t) for t in _TOKEN.findall(s.lower()) if t not in _STOP}


class KeywordRetriever:
    backend = "keyword"

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._index = [(c, _tokens(c.heading + " " + c.text)) for c in chunks]
        # IDF so terms in every chunk ("fp57", "refund") count for little and
        # distinctive ones ("limit", "long") decide the match.
        n = len(chunks)
        df: dict[str, int] = {}
        for _, toks in self._index:
            for t in toks:
                df[t] = df.get(t, 0) + 1
        self._idf = {t: math.log((n + 1) / (d + 0.5)) for t, d in df.items()}
        self._unseen_idf = math.log((n + 1) / 0.5)

    def search(self, query: str, k: int = 1) -> list[tuple[Chunk, float]]:
        q = _tokens(query)
        total = sum(self._idf.get(t, self._unseen_idf) for t in q) or 1.0
        scored = [(c, sum(self._idf[t] for t in q & toks) / total) for c, toks in self._index]
        scored.sort(key=lambda x: (-x[1], x[0].chunk_id))
        return scored[:k]


class QdrantRetriever:
    """Hybrid: bge-small dense similarity from Qdrant plus a small lexical-overlap
    term. On a corpus this small the dense scores sit within ~0.02 of each other,
    and the lexical term breaks those near-ties toward the clause that actually
    uses the query's words."""
    backend = "qdrant/bge-small-en-v1.5+lexical"
    LEXICAL_WEIGHT = 0.3

    def __init__(self, chunks: list[Chunk]):
        from fastembed import TextEmbedding
        from qdrant_client import QdrantClient, models

        self.chunks = {c.chunk_id: c for c in chunks}
        self._lexical = KeywordRetriever(chunks)
        self._embedder = TextEmbedding(EMBED_MODEL)
        self._client = QdrantClient(location=":memory:")
        self._client.create_collection(
            COLLECTION, vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )
        vectors = list(self._embedder.embed([f"{c.heading}. {c.text}" for c in chunks]))
        self._client.upsert(
            COLLECTION,
            points=[
                models.PointStruct(id=c.chunk_id, vector=v.tolist(), payload={"heading": c.heading})
                for c, v in zip(chunks, vectors)
            ],
        )

    def search(self, query: str, k: int = 1) -> list[tuple[Chunk, float]]:
        # bge models expect this instruction prefix on queries (not passages).
        qv = next(iter(self._embedder.embed([f"Represent this sentence for searching relevant passages: {query}"])))
        hits = self._client.query_points(COLLECTION, query=qv.tolist(), limit=len(self.chunks)).points
        lexical = {c.chunk_id: score for c, score in self._lexical.search(query, k=len(self.chunks))}
        scored = [(self.chunks[h.id], float(h.score) + self.LEXICAL_WEIGHT * lexical[h.id]) for h in hits]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]


@lru_cache
def get_retriever(backend: str = "qdrant"):
    chunks = load_chunks()
    if backend == "keyword":
        return KeywordRetriever(chunks)
    return QdrantRetriever(chunks)
