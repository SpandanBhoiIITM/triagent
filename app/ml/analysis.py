"""
Clustering (find recurring issue themes) + semantic search (retrieval).

Interview points:
- KMeans on TF-IDF vectors groups similar tickets. Top terms per cluster
  become the "theme name".
- Semantic search here uses TF-IDF cosine similarity. Upgrade path:
  sentence-transformers embeddings + a vector index (FAISS). Explaining
  WHY you'd upgrade (TF-IDF misses synonyms, embeddings capture meaning)
  is the interview gold, not the library name.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity


def cluster_tickets(texts, n_clusters=4):
    """Returns list of {theme, ticket_indices, size} dicts."""
    if len(texts) < n_clusters:
        n_clusters = max(1, len(texts) // 2)

    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(texts)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    terms = np.array(vectorizer.get_feature_names_out())
    clusters = []
    for i in range(n_clusters):
        indices = [j for j, lab in enumerate(labels) if lab == i]
        # top 3 terms closest to the cluster center = theme name
        center = km.cluster_centers_[i]
        top_terms = terms[np.argsort(center)[::-1][:3]]
        clusters.append({
            "theme": ", ".join(top_terms),
            "ticket_indices": indices,
            "size": len(indices),
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


def semantic_search(query, texts, top_k=5):
    """Returns indices of the top_k most similar texts to the query."""
    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(texts + [query])
    query_vec = X[-1]
    doc_vecs = X[:-1]
    scores = cosine_similarity(query_vec, doc_vecs)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [int(i) for i in top_indices if scores[i] > 0]
