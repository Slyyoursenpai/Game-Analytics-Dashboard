import plotly.express as px
import streamlit as st

from db import run_query

st.set_page_config(page_title="Reviews", layout="wide")
st.title("Reviews & Ratings")

# ------------------------------------------------------- Platform filter ---
platforms = run_query("SELECT DISTINCT platform FROM game WHERE platform IS NOT NULL ORDER BY platform")["platform"].tolist()
platform_opts = ["All"] + platforms
selected_platform = st.sidebar.selectbox("Platform", platform_opts, key="platform_filter")

# ----------------------------------------------------------- Game filter ---
if selected_platform == "All":
    game_list = run_query("SELECT game_id, title, genre, platform FROM game ORDER BY title")
else:
    game_list = run_query("SELECT game_id, title, genre, platform FROM game WHERE platform = :p ORDER BY title", {"p": selected_platform})
all_key = -1
game_opts = {"All Games": all_key}
if not game_list.empty:
    game_opts.update({f"{r['title']} ({r['genre']} — {r['platform']})": r["game_id"] for _, r in game_list.iterrows()})

selected_game = st.selectbox("Filter by game", list(game_opts.keys()))
gid = game_opts[selected_game]
is_all = gid == all_key

st.divider()

# ------------------------------------------------------ Rating distribution
st.subheader("Rating Distribution")
if is_all:
    if selected_platform == "All":
        rating_dist = run_query("""
            SELECT rating, COUNT(*) AS reviews
            FROM review
            WHERE rating IS NOT NULL
            GROUP BY rating
            ORDER BY rating
        """)
    else:
        rating_dist = run_query("""
            SELECT r.rating, COUNT(*) AS reviews
            FROM review r
            JOIN game g ON g.game_id = r.game_id
            WHERE r.rating IS NOT NULL AND g.platform = :p
            GROUP BY r.rating
            ORDER BY r.rating
        """, {"p": selected_platform})
else:
    rating_dist = run_query("""
        SELECT rating, COUNT(*) AS reviews
        FROM review
        WHERE rating IS NOT NULL AND game_id = :gid
        GROUP BY rating
        ORDER BY rating
    """, {"gid": gid})

if rating_dist.empty:
    st.info("No reviews yet. Insert rows into the `review` table to see them here.")
else:
    fig = px.bar(rating_dist, x="rating", y="reviews")
    fig.update_xaxes(dtick=1, range=[0.5, 10.5])
    st.plotly_chart(fig, width='stretch')

st.divider()

# --------------------------------------------------------- Trend over time -
st.subheader("Reviews Over Time")
st.caption("Review volume and average rating per day, from `review.reviewed_at`.")
if is_all:
    if selected_platform == "All":
        reviews_over_time = run_query("""
            SELECT DATE(reviewed_at) AS day, COUNT(*) AS reviews, AVG(rating) AS avg_rating
            FROM review
            WHERE rating IS NOT NULL
            GROUP BY day
            ORDER BY day
        """)
    else:
        reviews_over_time = run_query("""
            SELECT DATE(r.reviewed_at) AS day, COUNT(*) AS reviews, AVG(r.rating) AS avg_rating
            FROM review r
            JOIN game g ON g.game_id = r.game_id
            WHERE r.rating IS NOT NULL AND g.platform = :p
            GROUP BY day
            ORDER BY day
        """, {"p": selected_platform})
else:
    reviews_over_time = run_query("""
        SELECT DATE(reviewed_at) AS day, COUNT(*) AS reviews, AVG(rating) AS avg_rating
        FROM review
        WHERE rating IS NOT NULL AND game_id = :gid
        GROUP BY day
        ORDER BY day
    """, {"gid": gid})

if reviews_over_time.empty:
    st.info("No reviews yet.")
else:
    fig = px.line(reviews_over_time, x="day", y="avg_rating", markers=True, labels={"avg_rating": "Avg rating"})
    st.plotly_chart(fig, width='stretch')

st.divider()

# --------------------------------------------------------------- Avg by game ----
if is_all:
    st.subheader("Average Rating by Game")
    if selected_platform == "All":
        avg_by_game = run_query("""
            SELECT g.title, AVG(r.rating) AS avg_rating, COUNT(r.review_id) AS review_count
            FROM review r
            JOIN game g ON g.game_id = r.game_id
            WHERE r.rating IS NOT NULL
            GROUP BY g.title
            ORDER BY avg_rating DESC
        """)
    else:
        avg_by_game = run_query("""
            SELECT g.title, AVG(r.rating) AS avg_rating, COUNT(r.review_id) AS review_count
            FROM review r
            JOIN game g ON g.game_id = r.game_id
            WHERE r.rating IS NOT NULL AND g.platform = :p
            GROUP BY g.title
            ORDER BY avg_rating DESC
        """, {"p": selected_platform})
    if avg_by_game.empty:
        st.info("No reviews yet.")
    else:
        fig = px.bar(avg_by_game, x="title", y="avg_rating", hover_data=["review_count"])
        st.plotly_chart(fig, width='stretch')

    st.divider()

# -------------------------------------------------------------- Browser ---
st.subheader("Browse Reviews")
if selected_platform == "All":
    games_for_filter = run_query("""
        SELECT DISTINCT g.title
        FROM review r
        JOIN game g ON g.game_id = r.game_id
        ORDER BY g.title
    """)
else:
    games_for_filter = run_query("""
        SELECT DISTINCT g.title
        FROM review r
        JOIN game g ON g.game_id = r.game_id
        WHERE g.platform = :p
        ORDER BY g.title
    """, {"p": selected_platform})

if games_for_filter.empty:
    st.info("No reviews to browse yet.")
else:
    titles = ["All"] + games_for_filter["title"].tolist()
    c1, c2 = st.columns([2, 1])
    game_filter = c1.selectbox("Filter by game", titles)
    min_rating = c2.slider("Minimum rating", 1, 10, 1)

    query = """
        SELECT g.title, p.username, r.rating, r.review_text
        FROM review r
        JOIN game g ON g.game_id = r.game_id
        JOIN player p ON p.player_id = r.player_id
        WHERE r.rating >= :min_rating
    """
    params: dict = {"min_rating": min_rating}
    if game_filter != "All":
        query += " AND g.title = :title"
        params["title"] = game_filter
    if not is_all:
        query += " AND g.game_id = :gid"
        params["gid"] = gid
    if is_all and selected_platform != "All":
        query += " AND g.platform = :p"
        params["p"] = selected_platform
    query += " ORDER BY r.rating DESC"

    df = run_query(query, params)
    st.dataframe(df, width='stretch', hide_index=True)

st.divider()

# --------------------------------------------------- Rating vs Session Duration
st.subheader("Rating vs Session Duration")
st.caption("Do players who play longer sessions give higher ratings?")
if is_all:
    if selected_platform == "All":
        rating_session = run_query("""
            SELECT r.rating, AVG(gs.session_duration) AS avg_session_duration
            FROM review r
            JOIN gameplay_session gs ON gs.player_id = r.player_id AND gs.game_id = r.game_id
            WHERE gs.session_duration IS NOT NULL
            GROUP BY r.rating
            ORDER BY r.rating
        """)
    else:
        rating_session = run_query("""
            SELECT r.rating, AVG(gs.session_duration) AS avg_session_duration
            FROM review r
            JOIN gameplay_session gs ON gs.player_id = r.player_id AND gs.game_id = r.game_id
            JOIN game g ON g.game_id = r.game_id
            WHERE gs.session_duration IS NOT NULL AND g.platform = :p
            GROUP BY r.rating
            ORDER BY r.rating
        """, {"p": selected_platform})
else:
    rating_session = run_query("""
        SELECT r.rating, AVG(gs.session_duration) AS avg_session_duration
        FROM review r
        JOIN gameplay_session gs ON gs.player_id = r.player_id AND gs.game_id = r.game_id
        WHERE gs.session_duration IS NOT NULL AND r.game_id = :gid
        GROUP BY r.rating
        ORDER BY r.rating
    """, {"gid": gid})

if rating_session.empty:
    st.info("Add reviews and sessions to see this relationship.")
else:
    fig = px.bar(rating_session, x="rating", y="avg_session_duration",
                 labels={"avg_session_duration": "Avg session duration (min)"})
    fig.update_xaxes(dtick=1, range=[0.5, 10.5])
    st.plotly_chart(fig, width='stretch')

st.divider()

# --------------------------------------------------------- Top Reviewers ---
st.subheader("Top Reviewers & Power Users")
st.caption("Players who review the most, with their playtime and session count.")
if selected_platform == "All":
    power_users = run_query("""
        SELECT p.username,
               COUNT(DISTINCT r.review_id) AS reviews_written,
               COUNT(DISTINCT gs.session_id) AS total_sessions,
               COALESCE(SUM(gs.session_duration), 0) AS total_minutes
        FROM player p
        LEFT JOIN review r ON r.player_id = p.player_id
        LEFT JOIN gameplay_session gs ON gs.player_id = p.player_id
        GROUP BY p.username
        HAVING COUNT(DISTINCT r.review_id) > 0
        ORDER BY reviews_written DESC
        LIMIT 10
    """)
else:
    power_users = run_query("""
        SELECT p.username,
               COUNT(DISTINCT r.review_id) AS reviews_written,
               COUNT(DISTINCT gs.session_id) AS total_sessions,
               COALESCE(SUM(gs.session_duration), 0) AS total_minutes
        FROM player p
        LEFT JOIN review r ON r.player_id = p.player_id
        LEFT JOIN gameplay_session gs ON gs.player_id = p.player_id
        LEFT JOIN game g ON g.game_id = r.game_id
        WHERE g.platform = :p
        GROUP BY p.username
        HAVING COUNT(DISTINCT r.review_id) > 0
        ORDER BY reviews_written DESC
        LIMIT 10
    """, {"p": selected_platform})
if power_users.empty:
    st.info("No reviewers yet.")
else:
    st.dataframe(power_users, width='stretch', hide_index=True)

st.divider()

# ---------------------------------------------------- Avg Rating by Genre ---
if is_all:
    st.subheader("Average Rating by Genre")
    st.caption("Which genres score highest with players?")
    if selected_platform == "All":
        genre_rating = run_query("""
            SELECT g.genre, AVG(r.rating) AS avg_rating, COUNT(r.review_id) AS review_count
            FROM review r
            JOIN game g ON g.game_id = r.game_id
            WHERE g.genre IS NOT NULL
            GROUP BY g.genre
            ORDER BY avg_rating DESC
        """)
    else:
        genre_rating = run_query("""
            SELECT g.genre, AVG(r.rating) AS avg_rating, COUNT(r.review_id) AS review_count
            FROM review r
            JOIN game g ON g.game_id = r.game_id
            WHERE g.genre IS NOT NULL AND g.platform = :p
            GROUP BY g.genre
            ORDER BY avg_rating DESC
        """, {"p": selected_platform})
    if genre_rating.empty:
        st.info("No reviews yet.")
    else:
        fig = px.bar(genre_rating, x="genre", y="avg_rating", hover_data=["review_count"],
                     labels={"avg_rating": "Avg rating"})
        st.plotly_chart(fig, width='stretch')
