import pandas as pd
import plotly.express as px
import streamlit as st

from db import run_query

st.set_page_config(page_title="Revenue & Games", layout="wide")
st.cache_data.clear()
st.title("Revenue & Games")

# -------------------------------------------------------- Game Detail -----
st.subheader("Game Detail")
st.caption("Select a game to see its full profile: revenue, engagement, ratings, and more.")

try:
    game_list = run_query("SELECT game_id, title, genre, platform, base_price, image_url FROM game ORDER BY title")
    has_image_col = True
except Exception:
    game_list = run_query("SELECT game_id, title, genre, platform, base_price FROM game ORDER BY title")
    has_image_col = False
    st.warning("The `image_url` column is not in your database yet. Run `ALTER TABLE game ADD COLUMN image_url VARCHAR(500);` against your Neon database to enable game cover images.")

if game_list.empty:
    st.info("No games yet. Insert rows into the `game` table first.")
else:
    game_titles = {f"{r['title']} ({r['genre']} — {r['platform']})": r["game_id"] for _, r in game_list.iterrows()}
    selected_title = st.selectbox("Choose a game", list(game_titles.keys()))
    gid = game_titles[selected_title]

    game_info = game_list[game_list["game_id"] == gid].iloc[0]

    col_img, col_metrics = st.columns([1, 4])
    with col_img:
        if has_image_col:
            img_url = game_info.get("image_url")
            if isinstance(img_url, str) and img_url:
                st.image(img_url, width=150)
            else:
                st.image("https://via.placeholder.com/150x200?text=No+Cover", width=150)

    def _fmt(v, fmt=".2f", prefix="", suffix=""):
        try:
            return f"{prefix}{float(v):{fmt}}{suffix}"
        except (TypeError, ValueError):
            return "—"

    with col_metrics:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Base Price", _fmt(game_info['base_price'], prefix="$"))
        c2.metric("Genre", game_info["genre"] or "—")
        c3.metric("Platform", game_info["platform"] or "—")

        g_revenue = run_query("""
            SELECT COALESCE(SUM(combined.amt), 0) AS revenue
            FROM (
                SELECT sale_price AS amt FROM game_sale WHERE game_id = :gid
                UNION ALL
                SELECT amount AS amt FROM purchase WHERE game_id = :gid
            ) AS combined
        """, {"gid": gid})
        c4.metric("Total Revenue", _fmt(g_revenue['revenue'][0], prefix="$", fmt=",.2f"))

        g_rating = run_query("SELECT AVG(rating) AS avg_rating FROM review WHERE game_id = :gid", {"gid": gid})
        avg_r = g_rating["avg_rating"][0]
        c5.metric("Avg Rating", _fmt(avg_r, fmt=".1f") if avg_r is not None else "—")

    g_sales_count = run_query("SELECT COUNT(*) AS n FROM game_sale WHERE game_id = :gid", {"gid": gid})
    g_sessions = run_query("""
        SELECT COUNT(*) AS total_sessions, AVG(session_duration) AS avg_duration
        FROM gameplay_session WHERE game_id = :gid
    """, {"gid": gid})
    g_review_count = run_query("SELECT COUNT(*) AS n FROM review WHERE game_id = :gid", {"gid": gid})

    c6, c7, c8 = st.columns(3)
    c6.metric("Units Sold", int(g_sales_count["n"][0]))
    avg_dur = g_sessions["avg_duration"][0]
    c7.metric("Avg Session", _fmt(avg_dur, fmt=".1f", suffix=" min") if avg_dur is not None else "—")
    c8.metric("Reviews", int(g_review_count["n"][0]))

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("Difficulty Breakdown")
        g_diff = run_query("""
            SELECT COALESCE(difficulty, 'Unspecified') AS difficulty, COUNT(*) AS sessions
            FROM gameplay_session WHERE game_id = :gid
            GROUP BY difficulty
            ORDER BY sessions DESC
        """, {"gid": gid})
        if g_diff.empty:
            st.info("No sessions for this game.")
        else:
            fig = px.pie(g_diff, names="difficulty", values="sessions", hole=0.45)
            st.plotly_chart(fig, width='stretch')

    with right_col:
        st.subheader("Deaths vs Level Reached")
        g_deaths = run_query("""
            SELECT death_count, level_reached, COALESCE(difficulty,'Unspecified') AS difficulty
            FROM gameplay_session WHERE game_id = :gid
        """, {"gid": gid})
        if g_deaths.empty:
            st.info("No sessions for this game.")
        else:
            fig = px.scatter(g_deaths, x="level_reached", y="death_count", color="difficulty",
                             labels={"level_reached": "Level reached", "death_count": "Deaths"})
            st.plotly_chart(fig, width='stretch')

    st.divider()

# ------------------------------------------------------------ Catalog -----
st.subheader("Game Catalog")
games_df = run_query("SELECT game_id, title, genre, platform, base_price FROM game ORDER BY title")

if games_df.empty:
    st.info("No games added yet. Insert rows into the `game` table to see them here.")
else:
    genres = ["All"] + sorted(games_df["genre"].dropna().unique().tolist())
    platforms = ["All"] + sorted(games_df["platform"].dropna().unique().tolist())

    c1, c2 = st.columns(2)
    genre_filter = c1.selectbox("Genre", genres)
    platform_filter = c2.selectbox("Platform", platforms)

    filtered = games_df.copy()
    if genre_filter != "All":
        filtered = filtered[filtered["genre"] == genre_filter]
    if platform_filter != "All":
        filtered = filtered[filtered["platform"] == platform_filter]

    st.dataframe(filtered, width='stretch', hide_index=True)

st.subheader("Revenue Breakdown")
rev_groupby = st.selectbox("Group by", ["Genre", "Platform", "Region"])
if rev_groupby == "Genre":
    rev_data = run_query("""
        SELECT g.genre AS label, SUM(combined.amt) AS revenue
        FROM (
            SELECT game_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT game_id, amount AS amt FROM purchase
        ) AS combined
        JOIN game g ON g.game_id = combined.game_id
        WHERE g.genre IS NOT NULL
        GROUP BY g.genre
        ORDER BY revenue DESC
    """)
elif rev_groupby == "Platform":
    rev_data = run_query("""
        SELECT g.platform AS label, SUM(combined.amt) AS revenue
        FROM (
            SELECT game_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT game_id, amount AS amt FROM purchase
        ) AS combined
        JOIN game g ON g.game_id = combined.game_id
        WHERE g.platform IS NOT NULL
        GROUP BY g.platform
        ORDER BY revenue DESC
    """)
else:
    rev_data = run_query("""
        SELECT COALESCE(p.region, 'Unknown') AS label, SUM(combined.amt) AS revenue
        FROM (
            SELECT player_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT player_id, amount AS amt FROM purchase
        ) AS combined
        JOIN player p ON p.player_id = combined.player_id
        GROUP BY p.region
        ORDER BY revenue DESC
    """)
if rev_data.empty:
    st.info("No revenue data yet.")
else:
    fig = px.bar(rev_data, x="label", y="revenue", labels={"label": rev_groupby})
    st.plotly_chart(fig, width='stretch')

st.divider()

# -------------------------------------------------------- Revenue by game --
st.subheader("Revenue by Game")
rev_by_game = run_query(
    """
    SELECT g.title, SUM(combined.amt) AS revenue
    FROM (
        SELECT game_id, sale_price AS amt FROM game_sale
        UNION ALL
        SELECT game_id, amount AS amt FROM purchase
    ) AS combined
    JOIN game g ON g.game_id = combined.game_id
    GROUP BY g.title
    ORDER BY revenue DESC
    """
)
if rev_by_game.empty:
    st.info("No sales or purchases recorded yet.")
else:
    fig = px.bar(rev_by_game, x="title", y="revenue")
    st.plotly_chart(fig, width='stretch')

st.divider()

# ------------------------------------------------------- Top items --------
st.subheader("Top Purchased Items")
top_items = run_query(
    """
    SELECT item_name, COUNT(*) AS purchases, SUM(amount) AS revenue
    FROM purchase
    GROUP BY item_name
    ORDER BY revenue DESC
    LIMIT 10
    """
)
if top_items.empty:
    st.info("No in-game purchases recorded yet.")
else:
    st.dataframe(top_items, width='stretch', hide_index=True)

st.divider()

# --------------------------------------------------- Price vs rating ------
st.subheader("Price vs. Average Rating")
st.caption("Are pricier games rated better, worse, or no different?")
price_vs_rating = run_query(
    """
    SELECT g.title, g.base_price, AVG(r.rating) AS avg_rating
    FROM game g
    JOIN review r ON r.game_id = g.game_id
    GROUP BY g.title, g.base_price
    """
)
if price_vs_rating.empty:
    st.info("Add reviews to see how price relates to rating.")
else:
    fig = px.scatter(
        price_vs_rating,
        x="base_price",
        y="avg_rating",
        text="title",
        labels={"base_price": "Base price ($)", "avg_rating": "Avg rating"},
    )
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, width='stretch')

st.divider()

st.subheader("Price vs Sales Volume")
st.caption("Do cheaper games sell more units?")
price_sales = run_query("""
    SELECT g.title, g.base_price, COUNT(gs.sale_id) AS units_sold
    FROM game g
    LEFT JOIN game_sale gs ON gs.game_id = g.game_id
    GROUP BY g.title, g.base_price
    ORDER BY units_sold DESC
""")
if price_sales.empty:
    st.info("No sales data yet.")
else:
    fig = px.scatter(
        price_sales,
        x="base_price",
        y="units_sold",
        text="title",
        labels={"base_price": "Base price ($)", "units_sold": "Units sold"},
    )
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, width='stretch')

st.divider()

st.subheader("Cross-Metric Comparisons")
st.caption("How do reviews, sales volume, and revenue relate to each other per game?")

c1, c2, c3 = st.columns(3)

with c1:
    review_sales = run_query("""
        SELECT g.title, COUNT(DISTINCT r.review_id) AS review_count, COUNT(DISTINCT gs.sale_id) AS units_sold
        FROM game g
        LEFT JOIN review r ON r.game_id = g.game_id
        LEFT JOIN game_sale gs ON gs.game_id = g.game_id
        GROUP BY g.title
    """)
    if review_sales.empty or review_sales["review_count"].sum() == 0:
        st.info("Add reviews and sales to see this relationship.")
    else:
        fig = px.scatter(review_sales, x="units_sold", y="review_count",
                         labels={"units_sold": "Units sold", "review_count": "Reviews"},
                         hover_name="title")
        st.plotly_chart(fig, width='stretch')

with c2:
    review_revenue = run_query("""
        SELECT g.title, COUNT(DISTINCT r.review_id) AS review_count, SUM(combined.amt) AS revenue
        FROM game g
        LEFT JOIN review r ON r.game_id = g.game_id
        LEFT JOIN (
            SELECT game_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT game_id, amount AS amt FROM purchase
        ) AS combined ON combined.game_id = g.game_id
        GROUP BY g.title
    """)
    if review_revenue.empty or review_revenue["review_count"].sum() == 0:
        st.info("Add reviews and revenue to see this relationship.")
    else:
        fig = px.scatter(review_revenue, x="revenue", y="review_count",
                         labels={"revenue": "Revenue ($)", "review_count": "Reviews"},
                         hover_name="title")
        st.plotly_chart(fig, width='stretch')

with c3:
    sales_revenue = run_query("""
        SELECT g.title, COUNT(DISTINCT gs.sale_id) AS units_sold, SUM(combined.amt) AS revenue
        FROM game g
        LEFT JOIN game_sale gs ON gs.game_id = g.game_id
        LEFT JOIN (
            SELECT game_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT game_id, amount AS amt FROM purchase
        ) AS combined ON combined.game_id = g.game_id
        GROUP BY g.title
    """)
    if sales_revenue.empty or sales_revenue["units_sold"].sum() == 0:
        st.info("Add sales data to see this relationship.")
    else:
        fig = px.scatter(sales_revenue, x="units_sold", y="revenue",
                         labels={"units_sold": "Units sold", "revenue": "Revenue ($)"},
                         hover_name="title")
        st.plotly_chart(fig, width='stretch')

st.divider()

st.subheader("Player Conversion Funnel")
st.caption("How many players progress through each stage?")
total_players = int(run_query("SELECT COUNT(*) AS n FROM player")["n"][0])
buyers = int(run_query("SELECT COUNT(DISTINCT player_id) AS n FROM game_sale")["n"][0])
purchasers = int(run_query("SELECT COUNT(DISTINCT player_id) AS n FROM purchase")["n"][0])
reviewers = int(run_query("SELECT COUNT(DISTINCT player_id) AS n FROM review")["n"][0])

if total_players > 0:
    funnel_df = pd.DataFrame({
        "stage": ["All Players", "Bought a Game", "Made In-Game Purchase", "Left a Review"],
        "count": [total_players, buyers, purchasers, reviewers],
    })
    funnel_df["% of All Players"] = (funnel_df["count"] / total_players * 100).round(1)
    st.dataframe(funnel_df, width='stretch', hide_index=True)
    fig = px.funnel(funnel_df, x="count", y="stage")
    st.plotly_chart(fig, width='stretch')
else:
    st.info("No players yet.")
