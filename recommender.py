import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from api import search_movie, get_similar_movies
from genre_utils import get_movies_for_genres


def _norm_title(t: str) -> str:
    t = (t or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _year_token(m: dict) -> str:
    rd = (m.get("release_date") or "").strip()
    y = rd[:4] if len(rd) >= 4 else ""
    return f"year_{y}" if y.isdigit() else ""


def _movie_text(m: dict) -> str:
    # Weight title + genres higher by repeating them (cheap + effective).
    title = (m.get("title") or "").strip()
    overview = (m.get("overview") or "").strip()
    genres = " ".join(m.get("genre_names", []) or [])
    ytok = _year_token(m)

    # Repetition = field weighting
    return f"{title} {title} {genres} {genres} {overview} {ytok}".strip()


def _quality_prior(m: dict) -> float:
    """
    Small bounded prior in [0, ~1.0] based on TMDB vote stats.
    Helps avoid weird low-vote picks when text similarity ties.
    """
    va = float(m.get("vote_average") or 0.0)          # typically 0-10
    vc = float(m.get("vote_count") or 0.0)

    va_n = np.clip(va / 10.0, 0.0, 1.0)
    vc_n = np.log1p(vc) / np.log1p(5000.0)            # saturates slowly
    return 0.65 * va_n + 0.35 * np.clip(vc_n, 0.0, 1.0)


def recommend_movies(
    favorites,
    genre_dict,
    top_n=10,
    relevance_weight=0.70,          # renamed from lambda_div for clarity
    candidate_limit=250,
    per_genre_limit=40,
    max_pages=3,
    use_similar_expansion=True,
    similar_expansion_favs=3,       # hard cap API calls
    quality_weight=0.12,            # 0 disables the prior
):
    # 1) Resolve favorites (cached in api.py)
    fav_data = []
    seen_titles = set()
    for title in favorites:
        nt = _norm_title(title)
        if not nt or nt in seen_titles:
            continue
        seen_titles.add(nt)
        m = search_movie(title)
        if m:
            fav_data.append(m)

    if not fav_data:
        return []

    # 2) Collect liked genre names
    liked_genre_names = set()
    for m in fav_data:
        mids = set(m.get("genre_ids", []) or [])
        for gname, gid in genre_dict.items():
            if gid in mids:
                liked_genre_names.add(gname)

    # 3) Candidate pool: genre discover (diversified) + small similar-expansion
    candidates = get_movies_for_genres(
        selected_genres=list(liked_genre_names),
        genre_dict=genre_dict,
        max_pages=max_pages,
        per_genre_limit=per_genre_limit,
        total_limit=candidate_limit,
        diversify=True,
    )

    if use_similar_expansion:
        seen_ids = {m.get("id") for m in candidates if m.get("id")}
        for fm in fav_data[:similar_expansion_favs]:
            mid = fm.get("id")
            if not mid:
                continue
            recs = get_similar_movies(mid, page=1) or []
            for r in recs[:30]:
                rid = r.get("id")
                if rid and rid not in seen_ids and r.get("overview"):
                    candidates.append(r)
                    seen_ids.add(rid)
                if len(candidates) >= candidate_limit:
                    break
            if len(candidates) >= candidate_limit:
                break

    if not candidates:
        return []

    # Remove favorites from candidates
    fav_ids = {m.get("id") for m in fav_data if m.get("id")}
    candidates = [m for m in candidates if m.get("id") not in fav_ids]

    if not candidates:
        return []

    # 4) Vectorize once (better TF-IDF settings) [web:135]
    docs = [_movie_text(m) for m in candidates]
    query = " ".join(_movie_text(m) for m in fav_data)

    tfidf = TfidfVectorizer(
        stop_words="english",
        max_features=8000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_df=0.90,
        norm="l2",
    )
    X = tfidf.fit_transform(docs)
    q_vec = tfidf.transform([query])

    rel = cosine_similarity(q_vec, X).ravel()
    cand_sim = cosine_similarity(X)

    # Add small quality prior (no extra calls)
    if quality_weight and quality_weight > 0:
        qp = np.array([_quality_prior(m) for m in candidates], dtype=float)
        rel = rel + quality_weight * qp

    # 5) Greedy MMR + genre cap (as you had)
    selected_idx = []
    used = np.zeros(len(candidates), dtype=bool)

    primary_genre = []
    for m in candidates:
        gids = m.get("genre_ids", []) or []
        primary_genre.append(gids[0] if gids else None)

    genre_counts = {}
    max_per_primary_genre = max(2, top_n // 3)

    first = int(np.argmax(rel))
    selected_idx.append(first)
    used[first] = True
    if primary_genre[first] is not None:
        genre_counts[primary_genre[first]] = 1

    while len(selected_idx) < min(top_n, len(candidates)):
        max_sim_to_selected = cand_sim[:, selected_idx].max(axis=1)

        best_i = None
        best_score = -1e9

        for i in range(len(candidates)):
            if used[i]:
                continue
            pg = primary_genre[i]
            if pg is not None and genre_counts.get(pg, 0) >= max_per_primary_genre:
                continue

            # MMR: relevance vs similarity-to-selected tradeoff [web:62][web:140]
            score = relevance_weight * rel[i] - (1.0 - relevance_weight) * max_sim_to_selected[i]
            if score > best_score:
                best_score = score
                best_i = i

        if best_i is None:
            break

        selected_idx.append(best_i)
        used[best_i] = True
        pg = primary_genre[best_i]
        if pg is not None:
            genre_counts[pg] = genre_counts.get(pg, 0) + 1

    out = []
    for i in selected_idx:
        m = candidates[i]
        m["ml_score"] = float(rel[i])
        out.append(m)
    return out
