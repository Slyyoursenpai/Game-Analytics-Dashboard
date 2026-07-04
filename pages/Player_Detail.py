import plotly.express as px
import streamlit as st

from db import run_query

st.set_page_config(page_title="Player Detail", layout="wide")
st.title("Player Detail")

# ------------------------------------------------------- Platform filter ---
platforms = run_query("SELECT DISTINCT platform FROM game WHERE platform IS NOT NULL ORDER BY platform")["platform"].tolist()
platform_opts = ["All"] + platforms
selected_platform = st.sidebar.selectbox("Platform", platform_opts, key="platform_filter")

# ------------------------------------------------------- Player selector ---
if selected_platform == "All":
    players_df = run_query("SELECT player_id, username, region FROM player ORDER BY username")
else:
    players_df = run_query("""
        SELECT DISTINCT p.player_id, p.username, p.region
        FROM player p
        JOIN game_sale gs ON gs.player_id = p.player_id
        JOIN game g ON g.game_id = gs.game_id
        WHERE g.platform = :p
        UNION
        SELECT DISTINCT p.player_id, p.username, p.region
        FROM player p
        JOIN gameplay_session gs2 ON gs2.player_id = p.player_id
        JOIN game g ON g.game_id = gs2.game_id
        WHERE g.platform = :p
        UNION
        SELECT DISTINCT p.player_id, p.username, p.region
        FROM player p
        JOIN purchase pu ON pu.player_id = p.player_id
        JOIN game g ON g.game_id = pu.game_id
        WHERE g.platform = :p
        UNION
        SELECT DISTINCT p.player_id, p.username, p.region
        FROM player p
        JOIN review r ON r.player_id = p.player_id
        JOIN game g ON g.game_id = r.game_id
        WHERE g.platform = :p
        ORDER BY username
    """, {"p": selected_platform})

if players_df.empty:
    st.info("No players found for the selected platform.")
    st.stop()

player_opts = {f"{r['username']} ({r['region']})": r["player_id"] for _, r in players_df.iterrows()}
selected_label = st.selectbox("Select a player", list(player_opts.keys()))
pid = player_opts[selected_label]

# ------------------------------------------------------- Game selector ---
player_games = run_query("""
    SELECT DISTINCT g.game_id, g.title, g.genre, g.platform
    FROM game g
    WHERE g.game_id IN (
        SELECT game_id FROM game_sale WHERE player_id = :pid
        UNION
        SELECT game_id FROM gameplay_session WHERE player_id = :pid
        UNION
        SELECT game_id FROM review WHERE player_id = :pid
        UNION
        SELECT game_id FROM purchase WHERE player_id = :pid
    )
    ORDER BY g.title
""", {"pid": pid})
game_opts = {"All Games": -1}
if not player_games.empty:
    game_opts.update({f"{r['title']} ({r['genre']} — {r['platform']})": r["game_id"] for _, r in player_games.iterrows()})
selected_game_label = st.selectbox("Filter by game", list(game_opts.keys()))
gid = game_opts[selected_game_label]
is_game_selected = gid != -1

# ------------------------------------------------------- Player profile ---
player_info = players_df[players_df["player_id"] == pid].iloc[0]

total_spend = run_query("""
    SELECT COALESCE(SUM(combined.amt), 0) AS total
    FROM (
        SELECT sale_price AS amt FROM game_sale WHERE player_id = :pid
        UNION ALL
        SELECT amount AS amt FROM purchase WHERE player_id = :pid
    ) AS combined
""", {"pid": pid})["total"][0]

total_playtime = run_query("SELECT COALESCE(SUM(session_duration), 0) AS total FROM gameplay_session WHERE player_id = :pid", {"pid": pid})["total"][0]

session_count = int(run_query("SELECT COUNT(*) AS n FROM gameplay_session WHERE player_id = :pid", {"pid": pid})["n"][0])

review_count = int(run_query("SELECT COUNT(*) AS n FROM review WHERE player_id = :pid", {"pid": pid})["n"][0])

purchase_count = int(run_query("SELECT COUNT(*) AS n FROM purchase WHERE player_id = :pid", {"pid": pid})["n"][0])

game_count = int(run_query("SELECT COUNT(DISTINCT game_id) AS n FROM game_sale WHERE player_id = :pid", {"pid": pid})["n"][0])

st.subheader(f"{player_info['username']}")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Region", player_info["region"] or "—")
c2.metric("Total Spend", f"${float(total_spend):,.2f}")
c3.metric("Playtime", f"{int(total_playtime):,} min")
c4.metric("Sessions", session_count)
c5.metric("Reviews", review_count)
c6.metric("Games Owned", game_count)

st.divider()

# --------------------------------------------------------- Tabs ----------
tab_sales, tab_purchases, tab_sessions, tab_reviews, tab_activity = st.tabs(
    ["Sales", "Purchases", "Sessions", "Reviews", "Activity"]
)

# ------------------------------------------------------ Sales tab --------
with tab_sales:
    platform_filter = "" if selected_platform == "All" else " AND g.platform = :p"
    game_filter = "" if not is_game_selected else " AND g.game_id = :gid"
    params: dict = {"pid": pid}
    if selected_platform != "All":
        params["p"] = selected_platform
    if is_game_selected:
        params["gid"] = gid
    sales = run_query(f"""
        SELECT g.title, g.platform, gs.sale_price, gs.sale_date
        FROM game_sale gs
        JOIN game g ON g.game_id = gs.game_id
        WHERE gs.player_id = :pid{platform_filter}{game_filter}
        ORDER BY gs.sale_date DESC
        LIMIT 100
    """, params)

    if sales.empty:
        st.info("No game sales found for this player.")
    else:
        st.dataframe(sales, width="stretch", hide_index=True)
        fig = px.histogram(sales, x="sale_date", labels={"sale_date": "Date", "count": "Purchases"})
        st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------ Purchases tab -----
with tab_purchases:
    platform_filter = "" if selected_platform == "All" else " AND g.platform = :p"
    game_filter = "" if not is_game_selected else " AND g.game_id = :gid"
    params: dict = {"pid": pid}
    if selected_platform != "All":
        params["p"] = selected_platform
    if is_game_selected:
        params["gid"] = gid
    purchases = run_query(f"""
        SELECT g.title, g.platform, pu.item_name, pu.amount, pu.purchased_at
        FROM purchase pu
        JOIN game g ON g.game_id = pu.game_id
        WHERE pu.player_id = :pid{platform_filter}{game_filter}
        ORDER BY pu.purchased_at DESC
        LIMIT 100
    """, params)

    if purchases.empty:
        st.info("No in-game purchases found for this player.")
    else:
        st.dataframe(purchases, width="stretch", hide_index=True)
        fig = px.bar(purchases, x="item_name", y="amount", color="title",
                     labels={"item_name": "Item", "amount": "Price ($)"})
        st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------ Sessions tab -----
with tab_sessions:
    platform_filter = "" if selected_platform == "All" else " AND g.platform = :p"
    game_filter = "" if not is_game_selected else " AND g.game_id = :gid"
    params: dict = {"pid": pid}
    if selected_platform != "All":
        params["p"] = selected_platform
    if is_game_selected:
        params["gid"] = gid
    sessions = run_query(f"""
        SELECT g.title, g.platform, gs.session_duration, gs.difficulty, gs.death_count, gs.level_reached, gs.session_start
        FROM gameplay_session gs
        JOIN game g ON g.game_id = gs.game_id
        WHERE gs.player_id = :pid{platform_filter}{game_filter}
        ORDER BY gs.session_start DESC
        LIMIT 100
    """, params)

    if sessions.empty:
        st.info("No gameplay sessions found for this player.")
    else:
        st.dataframe(sessions, width="stretch", hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.pie(sessions, names="difficulty", title="Difficulty Preference", hole=0.45)
            st.plotly_chart(fig, width="stretch")
        with c2:
            fig = px.scatter(sessions, x="level_reached", y="death_count", color="difficulty",
                             labels={"level_reached": "Level", "death_count": "Deaths"},
                             title="Deaths vs Level")
            st.plotly_chart(fig, width="stretch")

        fig = px.line(sessions.sort_values("session_start"), x="session_start", y="session_duration",
                      labels={"session_start": "Date", "session_duration": "Duration (min)"},
                      title="Session Duration Over Time")
        st.plotly_chart(fig, width="stretch")

    if not is_game_selected:
        playtime_by_game = run_query("""
            SELECT g.title, SUM(gs.session_duration) AS total_minutes
            FROM gameplay_session gs
            JOIN game g ON g.game_id = gs.game_id
            WHERE gs.player_id = :pid
            GROUP BY g.title
            ORDER BY total_minutes DESC
        """, {"pid": pid})
        if not playtime_by_game.empty:
            fig = px.bar(playtime_by_game, x="title", y="total_minutes",
                         labels={"title": "Game", "total_minutes": "Playtime (min)"},
                         title="Playtime by Game")
            st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------ Reviews tab ------
with tab_reviews:
    platform_filter = "" if selected_platform == "All" else " AND g.platform = :p"
    game_filter = "" if not is_game_selected else " AND g.game_id = :gid"
    params: dict = {"pid": pid}
    if selected_platform != "All":
        params["p"] = selected_platform
    if is_game_selected:
        params["gid"] = gid
    reviews = run_query(f"""
        SELECT g.title, g.platform, r.rating, r.review_text, r.reviewed_at
        FROM review r
        JOIN game g ON g.game_id = r.game_id
        WHERE r.player_id = :pid{platform_filter}{game_filter}
        ORDER BY r.reviewed_at DESC
        LIMIT 50
    """, params)

    if reviews.empty:
        st.info("No reviews found for this player.")
    else:
        st.dataframe(reviews, width="stretch", hide_index=True)
        fig = px.histogram(reviews, x="rating", nbins=10, labels={"rating": "Rating"})
        fig.update_xaxes(dtick=1, range=[0.5, 10.5])
        st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------ Activity tab -----
with tab_activity:
    platform_filter = "" if selected_platform == "All" else " AND g.platform = :p"
    game_filter = "" if not is_game_selected else " AND g.game_id = :gid"
    params: dict = {"pid": pid}
    if selected_platform != "All":
        params["p"] = selected_platform
    if is_game_selected:
        params["gid"] = gid
    activity = run_query(f"""
        SELECT e.event_timestamp, e.event_type, g.title, g.platform
        FROM event_log e
        JOIN gameplay_session gs ON gs.session_id = e.session_id
        JOIN game g ON g.game_id = gs.game_id
        WHERE gs.player_id = :pid{platform_filter}{game_filter}
        ORDER BY e.event_timestamp DESC
        LIMIT 200
    """, params)

    if activity.empty:
        st.info("No activity found for this player.")
    else:
        st.dataframe(activity, width="stretch", hide_index=True)

        fig = px.histogram(activity, x="event_type", labels={"event_type": "Event Type", "count": "Occurrences"},
                           title="Event Type Distribution")
        st.plotly_chart(fig, width="stretch")

        fig = px.histogram(activity, x="event_timestamp", labels={"event_timestamp": "Time", "count": "Events"},
                           title="Activity Over Time")
        st.plotly_chart(fig, width="stretch")
