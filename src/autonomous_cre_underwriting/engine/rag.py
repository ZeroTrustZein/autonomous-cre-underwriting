"""Hybrid dense vector and lexical RAG search engine over offering memorandums."""

import hashlib
import math
import re
from typing import Dict, List, Optional, Set

from autonomous_cre_underwriting.types.ingestion import (
    DocumentChunk,
    IngestionSourceType,
    OfferingMemorandum,
)

# Dimension for local dense semantic embeddings
EMBEDDING_DIM = 64


def tokenize(text: str) -> List[str]:
    """Lowercase word tokenizer stripping punctuation."""
    return re.findall(r"\b[a-zA-Z0-9_\-\.\%]+\b", text.lower())


def compute_dense_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Produce deterministic unit-normalized semantic hash-projection dense vector."""
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for token in tokens:
        # MD5 hash token to deterministic float bucket
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        vec[idx] += sign

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 1e-12:
        vec = [round(x / norm, 6) for x in vec]
    return vec


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two unit-normalized dense vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return float(max(-1.0, min(1.0, dot)))


def chunk_text(
    text: str,
    document_id: str,
    source_type: IngestionSourceType = IngestionSourceType.OFFERING_MEMORANDUM,
    chunk_size_words: int = 80,
    overlap_words: int = 20,
) -> List[DocumentChunk]:
    """Sliding-window text chunker with overlap and page tracking."""
    words = text.split()
    if not words:
        return []

    chunks: List[DocumentChunk] = []
    step = max(1, chunk_size_words - overlap_words)
    chunk_idx = 0
    words_per_page = 300  # standard ~300 words per printed page

    for start in range(0, len(words), step):
        end = min(start + chunk_size_words, len(words))
        chunk_words = words[start:end]
        chunk_text_content = " ".join(chunk_words)

        page_no = max(1, (start // words_per_page) + 1)
        embedding = compute_dense_embedding(chunk_text_content)

        chunk = DocumentChunk(
            document_id=document_id,
            source_type=source_type,
            chunk_index=chunk_idx,
            page_number=page_no,
            text_content=chunk_text_content,
            token_count=len(chunk_words),
            embedding=embedding,
        )
        chunks.append(chunk)
        chunk_idx += 1

        if end >= len(words):
            break

    return chunks


class HybridRAGEngine:
    """Hybrid vector & lexical search engine implementing RAGEngineProtocol."""

    def __init__(self, alpha: float = 0.6) -> None:
        """Initialize RAG engine with dense/lexical weight alpha."""
        self.alpha = alpha  # alpha * dense + (1 - alpha) * lexical
        # deal_id -> list of DocumentChunk
        self.chunks_by_deal: Dict[str, List[DocumentChunk]] = {}
        # Inverted index: deal_id -> term -> list of chunk_indexes
        self.inverted_index: Dict[str, Dict[str, Set[int]]] = {}

    def index_document(self, memorandum: OfferingMemorandum) -> int:
        """Chunk, embed, and store an offering memorandum, returning indexed chunk count."""
        deal_id = memorandum.deal_id
        if deal_id not in self.chunks_by_deal:
            self.chunks_by_deal[deal_id] = []
            self.inverted_index[deal_id] = {}

        # If chunks are already attached to the memorandum, use and ensure embeddings exist
        chunks_to_index: List[DocumentChunk] = []
        if memorandum.chunks:
            for c in memorandum.chunks:
                if not c.embedding:
                    c.embedding = compute_dense_embedding(c.text_content)
                chunks_to_index.append(c)
        elif memorandum.executive_summary:
            # Chunk the executive summary if no chunks provided
            chunks_to_index = chunk_text(
                memorandum.executive_summary,
                document_id=memorandum.id,
                source_type=IngestionSourceType.OFFERING_MEMORANDUM,
            )

        start_offset = len(self.chunks_by_deal[deal_id])
        for idx, chunk in enumerate(chunks_to_index):
            assigned_idx = start_offset + idx
            chunk.chunk_index = assigned_idx
            self.chunks_by_deal[deal_id].append(chunk)

            # Build inverted lexical index
            tokens = set(tokenize(chunk.text_content))
            for tok in tokens:
                self.inverted_index[deal_id].setdefault(tok, set()).add(assigned_idx)

        # Update memorandum with stored chunks
        memorandum.chunks = list(self.chunks_by_deal[deal_id])
        return len(chunks_to_index)

    def hybrid_search(
        self,
        query: str,
        deal_id: str,
        top_k: int = 5,
        required_keywords: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Retrieve relevant chunks combining semantic dense cosine similarity and lexical match."""
        chunks = self.chunks_by_deal.get(deal_id, [])
        if not chunks:
            return []

        query_tokens = tokenize(query)
        query_vec = compute_dense_embedding(query)
        total_docs = len(chunks)

        # Pre-filter by required keywords if provided
        candidate_indices = set(range(len(chunks)))
        if required_keywords:
            for kw in required_keywords:
                matching_chunks = self.inverted_index.get(deal_id, {}).get(kw.lower(), set())
                candidate_indices.intersection_update(matching_chunks)

        if not candidate_indices:
            candidate_indices = set(range(len(chunks)))

        # Score candidate chunks
        scored_chunks = []
        for idx in candidate_indices:
            chunk = chunks[idx]

            # 1. Dense similarity
            dense_sim = cosine_similarity(query_vec, chunk.embedding)
            # Map [-1, 1] to [0, 1]
            dense_score = max(0.0, (dense_sim + 1.0) / 2.0)

            # 2. Lexical score (TF-IDF / BM25 term overlap)
            chunk_tokens = tokenize(chunk.text_content)
            chunk_len = len(chunk_tokens)
            lexical_score = 0.0
            if query_tokens and chunk_len > 0:
                match_count = sum(1 for tok in query_tokens if tok in chunk_tokens)
                term_ratio = match_count / len(query_tokens)
                lexical_score = term_ratio

            # 3. Hybrid score
            hybrid_score = (self.alpha * dense_score) + ((1.0 - self.alpha) * lexical_score)
            scored_chunks.append((hybrid_score, chunk))

        # Sort descending by hybrid score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]
