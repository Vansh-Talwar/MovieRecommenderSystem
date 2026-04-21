import streamlit as st
from api import (
    get_genres,
    search_movie,
    get_similar_movies,
    get_movies_by_genre,
    get_trending_movies,
)
from recommender import recommend_movies


st.set_page_config(page_title="Movie Recommender", page_icon="🎥")
st.title("🎥 Movie Recommender System")


# Load once per app (get_genres is cached in api.py; this call is cheap afterwards). [web:47]
genre_dict = get_genres() or {}


def display_movies(movies, show_score=False, max_display=10):
    if not movies:
        st.info("No movies to display.")
        return

    for movie in movies[:max_display]:
        title = movie.get("title", "Unknown")
        overview = movie.get("overview", "No overview available.")
        release_date = movie.get("release_date", "N/A")
        poster_path = movie.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w300{poster_path}" if poster_path else None
        score = movie.get("ml_score", movie.get("score"))

        col1, col2 = st.columns([1, 3])
        with col1:
            if poster_url:
                st.image(poster_url, use_container_width=True)
            else:
                st.write("No image")
        with col2:
            st.markdown(f"### {title} ({release_date[:4] if release_date != 'N/A' else 'Unknown'})")
            st.write(overview)
            if show_score and score is not None:
                st.write(f"Score: {score:.2f}")
            st.markdown("---")


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Search Movies",
    "Similar Movies",
    "ML-Based Recommender",
    "Explore by Genre",
    "Trending Movies",
])


with tab1:
    movie_name = st.text_input("Enter Movie To Search", placeholder="e.g., Inception")
    if st.button("Search Movie"):
        if not movie_name.strip():
            st.error("Please enter a movie name.")
        else:
            with st.spinner(f"Searching for '{movie_name}'..."):
                movie_data = search_movie(movie_name)
            if not movie_data:
                st.warning("No movies found.")
            else:
                st.subheader(f"Result for: {movie_name}")
                display_movies([movie_data])


with tab2:
    movie_input = st.text_input("Enter a movie to find similar ones", placeholder="e.g., Interstellar")
    if st.button("Find Similar Movies"):
        if not movie_input.strip():
            st.error("Please enter a movie name.")
        else:
            with st.spinner(f"Searching '{movie_input}'..."):
                movie_data = search_movie(movie_input)
            if not movie_data:
                st.warning("No movie found with that name.")
            else:
                movie_id = movie_data.get("id")
                st.success(f"Found: {movie_data.get('title', 'Unknown')}")
                with st.spinner("Loading recommendations..."):
                    similar_results = get_similar_movies(movie_id, page=1)
                display_movies(similar_results)


with tab3:
    st.subheader("Personalized Recommender")
    st.markdown("Enter your favorite movies (up to 3)")
    fav_movies = [st.text_input(f"Favorite Movie {i+1}") for i in range(3)]
    fav_movies = [m.strip() for m in fav_movies if m.strip()]
    top_n = st.slider("Number of recommendations:", min_value=5, max_value=20, value=10)

    if st.button("Get Personalized Recommendations", key="ml_rec"):
        if not fav_movies:
            st.error("Please enter at least 1 favorite movie.")
        elif not genre_dict:
            st.error("Genres not loaded; cannot recommend right now.")
        else:
            with st.spinner("Generating recommendations..."):
                # recommend_movies does not need extra caching here; it already benefits from cached API calls. [web:47]
                results = recommend_movies(fav_movies, genre_dict, top_n=top_n)
            if not results:
                st.info("No recommendations found. Try different favorites.")
            else:
                display_movies(results, show_score=True, max_display=top_n)


with tab4:
    st.subheader("Explore by Genre")
    if genre_dict:
        selected_genre = st.selectbox("Select a Genre:", list(genre_dict.keys()))
        page = st.slider("Select Page (1-20):", min_value=1, max_value=20, value=1)
        if st.button("Show Movies by Genre"):
            gid = genre_dict[selected_genre]
            with st.spinner("Loading movies..."):
                movies = get_movies_by_genre(gid, page=page)  # cached in api.py [web:47]
            display_movies(movies)
    else:
        st.error("Could not load genres.")


with tab5:
    period = st.selectbox("Select Trending Period:", ["day", "week"])
    if st.button("Show Trending Movies"):
        with st.spinner("Loading trending..."):
            movies = get_trending_movies(period=period, page=1)  # cached in api.py [web:47]
        display_movies(movies)
