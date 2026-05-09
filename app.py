import streamlit as st
import pickle
import pandas as pd
import requests
import time
from datetime import datetime

st.set_page_config(page_title="Movie Recommendation System", layout="wide")

API_KEY = "b7b225fe27d156952bd1354bb8b4b0ce"


# DISK CACHED API CALL
@st.cache_resource(show_spinner=False)
def cached_request(url):
    try:
        response = requests.get(url)
        return response.json()
    except:
        return {}


def safe_tmdb_list(url):
    data = cached_request(url)
    return data.get("results", []) if isinstance(data, dict) else []


# TMDB HELPERS
def search_movie(title):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={title}"
    data = cached_request(url)
    results = data.get("results", [])
    return results[0] if results else {"poster_path": None, "overview": "", "vote_average": 0}


def get_tmdb_details(movie_id, fallback_title):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US"
    data = cached_request(url)
    return data if "status_code" not in data else search_movie(fallback_title)


def get_trailer(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={API_KEY}"
    data = cached_request(url)
    for v in data.get("results", []):
        if v.get("type") == "Trailer":
            return f"https://www.youtube.com/watch?v={v['key']}"
    return None


def poster_url(path):
    return f"https://image.tmdb.org/t/p/w500{path}" if path else "https://via.placeholder.com/500x750?text=No+Poster"


# GENRE MAP
GENRE_MAP = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    18: "Drama",
    14: "Fantasy",
    27: "Horror",
    10749: "Romance",
    53: "Thriller",
}


# --------------------------------------------------------
# ADVANCED SEARCH HISTORY + FAVORITES
# --------------------------------------------------------
if "search_history" not in st.session_state:
    st.session_state.search_history = []  # [{title, time}]

if "favorites" not in st.session_state:
    st.session_state.favorites = []


def time_ago(timestamp):
    secs = int(time.time() - timestamp)
    if secs < 60: return f"{secs}s ago"
    if secs < 3600: return f"{secs//60}m ago"
    if secs < 86400: return f"{secs//3600}h ago"
    return f"{secs//86400}d ago"


def add_to_history(title):
    st.session_state.search_history = [
        h for h in st.session_state.search_history if h["title"] != title
    ]
    st.session_state.search_history.append({"title": title, "time": time.time()})
    st.session_state.search_history = st.session_state.search_history[-10:]


def remove_from_history(title):
    st.session_state.search_history = [
        h for h in st.session_state.search_history if h["title"] != title
    ]


def add_to_favorites(title):
    if title not in st.session_state.favorites:
        st.session_state.favorites.append(title)


def remove_favorite(title):
    st.session_state.favorites = [
        f for f in st.session_state.favorites if f != title
    ]


# --------------------------------------------------------
# RECOMMENDATION ENGINE
# --------------------------------------------------------
def recommend(movie):
    movie_index = movies[movies["title"] == movie].index[0]
    distances = similarity[movie_index]

    top_matches = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:10]

    results = []
    for idx, score in top_matches:
        results.append({
            "title": movies.iloc[idx].title,
            "movie_id": movies.iloc[idx].movie_id
        })

    return results


# --------------------------------------------------------
# LOAD DATA
# --------------------------------------------------------
movies_dict = pickle.load(open("movie_dict.pkl", "rb"))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open("similarity.pkl", "rb"))


# --------------------------------------------------------
# HEADER
# --------------------------------------------------------
st.markdown("<h1 style='text-align:center;'>🎬 Movie Recommendation System</h1>", unsafe_allow_html=True)


# --------------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------------
st.sidebar.header("🔍 Filters")

genre_filter = st.sidebar.multiselect("Select Genres (Optional)", list(GENRE_MAP.values()))
min_rating = st.sidebar.slider("Minimum Rating", 0.0, 10.0, 5.0)
year_range = st.sidebar.slider("Release Year", 1950, 2026, (2000, 2026))


# --------------------------------------------------------
# SIDEBAR SEARCH HISTORY
# --------------------------------------------------------
st.sidebar.subheader("📜 Search History")

if st.session_state.search_history:
    for item in reversed(st.session_state.search_history):
        title = item["title"]
        t = time_ago(item["time"])

        col1, col2, col3 = st.sidebar.columns([6, 1, 1])

        if col1.button(title, key=f"hist_{title}"):
            selected_movie = title

        if col2.button("✕", key=f"del_{title}"):
            remove_from_history(title)

        if title in st.session_state.favorites:
            if col3.button("★", key=f"fav_{title}"):
                remove_favorite(title)
        else:
            if col3.button("☆", key=f"fav_add_{title}"):
                add_to_favorites(title)

        st.sidebar.caption(f"⏱ {t}")

    if st.sidebar.button("🧹 Clear All"):
        st.session_state.search_history = []
else:
    st.sidebar.info("No searches yet.")


# --------------------------------------------------------
# FAVORITES
# --------------------------------------------------------
st.sidebar.subheader("⭐ Favorites")

if st.session_state.favorites:
    for fav in st.session_state.favorites:
        if st.sidebar.button(fav, key=f"favlist_{fav}"):
            selected_movie = fav
else:
    st.sidebar.caption("No favorites yet.")


# --------------------------------------------------------
# MOVIE DROPDOWN
# --------------------------------------------------------
selected_movie = st.selectbox("Select a movie:", movies["title"].values)


# --------------------------------------------------------
# RECOMMENDATION RESULTS
# --------------------------------------------------------
if st.button("Recommend"):

    add_to_history(selected_movie)

    initial_results = recommend(selected_movie)
    filtered = []

    for r in initial_results:
        details = get_tmdb_details(r["movie_id"], r["title"])

        genre_ids = details.get("genres", [])
        genres = [GENRE_MAP.get(g["id"], "") for g in genre_ids] if isinstance(genre_ids, list) else []

        year = int(details.get("release_date", "2000")[:4]) if details.get("release_date") else 2000
        rating = round(details.get("vote_average", 0), 1)

        if rating < min_rating: continue
        if not (year_range[0] <= year <= year_range[1]): continue
        if genre_filter and not any(g in genres for g in genre_filter): continue

        filtered.append({
            "title": r["title"],
            "poster": poster_url(details.get("poster_path")),
            "rating": rating,
            "overview": details.get("overview", "")[:150] + "...",
            "year": year,
            "genres": genres,
            "id": r["movie_id"]
        })

    # Guarantee minimum 5 movies
    if len(filtered) < 5:
        for r in initial_results:
            if len(filtered) >= 5:
                break
            details = get_tmdb_details(r["movie_id"], r["title"])
            filtered.append({
                "title": r["title"],
                "poster": poster_url(details.get("poster_path")),
                "rating": round(details.get("vote_average", 0), 1),
                "overview": details.get("overview", "")[:150] + "...",
                "id": r["movie_id"]
            })

    st.markdown("## 🎯 Recommendations For You")

    cols = st.columns(5)
    for i, r in enumerate(filtered[:10]):
        with cols[i % 5]:
            st.image(r["poster"])
            st.markdown(f"### {r['title']}")
            st.markdown(f"⭐ **{r['rating']}/10**")
            st.write(r["overview"])

            # FIXED UNIQUE TRAILER BUTTON
            unique_key = f"tr_{r['id']}_{i}"
            if st.button("▶️ Trailer", key=unique_key):
                trailer = get_trailer(r["id"])
                if trailer:
                    st.video(trailer)
                else:
                    st.info("No trailer available.")


# --------------------------------------------------------
# TRENDING NOW
# --------------------------------------------------------
st.markdown("## 🔥 Trending Now")

trending_url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={API_KEY}"
trending = safe_tmdb_list(trending_url)

filtered_trend = []
for m in trending:
    movie_genres = m.get("genre_ids", [])
    genres = [GENRE_MAP.get(g, "") for g in movie_genres]

    if not genre_filter or any(g in genres for g in genre_filter):
        filtered_trend.append(m)

if filtered_trend:
    cols = st.columns(min(10, len(filtered_trend)))
    for i, movie in enumerate(filtered_trend[:10]):
        cols[i].image(poster_url(movie.get("poster_path")), width=140)
        cols[i].write(movie.get("title"))
else:
    st.warning("No trending movies found for selected genres.")