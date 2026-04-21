# genre_utils.py
import logging
import random
from api import get_movies_by_genre

# Build once per call; avoids O(num_genres) scan per movie
def _invert_genres(genre_dict):
    return {gid: gname for gname, gid in genre_dict.items()}

def get_movies_for_genres(
    selected_genres,
    genre_dict,
    max_pages=2,
    per_genre_limit=20,
    total_limit=80,
    diversify=True,
    seed=42,
):
    rng = random.Random(seed)
    movies = []
    seen = set()
    id_to_name = _invert_genres(genre_dict)

    sort_pool = [
        "popularity.desc",
        "vote_average.desc",  # use vote_count.gte in api.py to avoid junky low-vote items
        "primary_release_date.desc",
    ]

    for genre in selected_genres:
        gid = genre_dict.get(genre)
        if not gid:
            continue

        genre_count = 0

        # Shuffle sort orders per genre to avoid deterministic same-list results.
        sorts = sort_pool[:]
        if diversify:
            rng.shuffle(sorts)

        for page in range(1, max_pages + 1):
            sort_by = sorts[(page - 1) % len(sorts)] if diversify else "popularity.desc"

            results = get_movies_by_genre(gid, page=page, sort_by=sort_by)
            if not results:
                break

            added_this_page = 0
            for m in results:
                mid = m.get("id")
                if not mid or mid in seen or not m.get("overview"):
                    continue

                m["genre_names"] = [id_to_name.get(x) for x in m.get("genre_ids", []) if id_to_name.get(x)]
                movies.append(m)
                seen.add(mid)
                genre_count += 1
                added_this_page += 1

                if len(movies) >= total_limit or genre_count >= per_genre_limit:
                    break

            # Stop early if the page barely adds new items (overlap / saturation).
            if added_this_page < 3:
                break

            if len(movies) >= total_limit or genre_count >= per_genre_limit:
                break

    logging.info("Genre fetch: %s movies (unique)", len(movies))
    return movies
