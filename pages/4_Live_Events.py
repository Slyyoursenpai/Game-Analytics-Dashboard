import plotly.express as px
import streamlit as st

from db import run_query

st.set_page_config(page_title="Live Events", layout="wide")
st.title("Live Events & Activity")
st.caption(
    "Raw telemetry from `event_log` — finer-grained than session-level activity, "
    "good for spotting specific in-game moments."
)

# ------------------------------------------------------- Platform filter ---
platforms = run_query("SELECT DISTINCT platform FROM game WHERE platform IS NOT NULL ORDER BY platform")["platform"].tolist()
platform_opts = ["All"] + platforms
selected_platform = st.sidebar.selectbox("Platform", platform_opts, key="platform_filter")

# --------------------------------------------------------- Game filter -----
if selected_platform == "All":
    game_list = run_query("SELECT game_id, title, genre, platform FROM game ORDER BY title")
else:
    game_list = run_query("SELECT game_id, title, genre, platform FROM game WHERE platform = :p ORDER BY title", {"p": selected_platform})
if game_list.empty:
    st.info("No games yet. Add games first to see their event data.")
    st.stop()

game_titles = {f"{r['title']} ({r['genre']} — {r['platform']})": r["game_id"] for _, r in game_list.iterrows()}
selected_title = st.selectbox("Filter by game", list(game_titles.keys()))
gid = game_titles[selected_title]

st.caption(f"Showing activity for **{selected_title}**")

st.divider()

# ------------------------------------------------------- Events over time --
st.subheader("Events Over Time")
events_over_time = run_query(
    """
    SELECT DATE(e.event_timestamp) AS day, COUNT(*) AS events
    FROM event_log e
    JOIN gameplay_session gs ON gs.session_id = e.session_id
    WHERE gs.game_id = :gid
    GROUP BY day
    ORDER BY day
    """,
    {"gid": gid},
)
if events_over_time.empty:
    st.info("No events logged for this game yet.")
else:
    fig = px.line(events_over_time, x="day", y="events", markers=True)
    st.plotly_chart(fig, width='stretch')

st.divider()

# --------------------------------------------------- Active players -------
st.subheader("Active Players Over Time")
st.caption("Distinct players with a session each day.")
active_players = run_query(
    """
    SELECT DATE(session_start) AS day, COUNT(DISTINCT player_id) AS active_players
    FROM gameplay_session
    WHERE game_id = :gid
    GROUP BY day
    ORDER BY day
    """,
    {"gid": gid},
)
if active_players.empty:
    st.info("No gameplay sessions logged for this game yet.")
else:
    fig = px.bar(active_players, x="day", y="active_players")
    st.plotly_chart(fig, width='stretch')

st.divider()

c1, c2 = st.columns(2)

with c1:
    st.subheader("Event Type Breakdown")
    df = run_query(
        """
        SELECT e.event_type, COUNT(*) AS occurrences
        FROM event_log e
        JOIN gameplay_session gs ON gs.session_id = e.session_id
        WHERE gs.game_id = :gid
        GROUP BY e.event_type
        ORDER BY occurrences DESC
        """,
        {"gid": gid},
    )
    if df.empty:
        st.info("No events for this game yet.")
    else:
        fig = px.pie(df, names="event_type", values="occurrences", hole=0.45)
        st.plotly_chart(fig, width='stretch')

with c2:
    st.subheader("Recent Events")
    df = run_query(
        """
        SELECT e.event_timestamp, e.event_type, p.username
        FROM event_log e
        JOIN gameplay_session gs ON gs.session_id = e.session_id
        JOIN player p ON p.player_id = gs.player_id
        WHERE gs.game_id = :gid
        ORDER BY e.event_timestamp DESC
        LIMIT 20
        """,
        {"gid": gid},
    )
    if df.empty:
        st.info("No events for this game yet.")
    else:
        st.dataframe(df, width='stretch', hide_index=True)

st.divider()

c3, c4 = st.columns(2)

with c3:
    st.subheader("Activity by Hour of Day")
    st.caption("When are players most active? Based on event timestamps.")
    hour_df = run_query(
        """
        SELECT EXTRACT(HOUR FROM e.event_timestamp) AS hour, COUNT(*) AS events
        FROM event_log e
        JOIN gameplay_session gs ON gs.session_id = e.session_id
        WHERE gs.game_id = :gid
        GROUP BY hour
        ORDER BY hour
        """,
        {"gid": gid},
    )
    if not hour_df.empty:
        hour_df["hour"] = hour_df["hour"].astype(int)
        fig = px.bar(hour_df, x="hour", y="events",
                     labels={"hour": "Hour (24h)", "events": "Events"})
        fig.update_xaxes(dtick=1, range=[-0.5, 23.5])
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No events logged for this game yet.")

with c4:
    st.subheader("Event-Type Funnel")
    st.caption("Most to least common event types — drop-off reveals bottlenecks.")
    funnel_df = run_query(
        """
        SELECT e.event_type, COUNT(*) AS occurrences
        FROM event_log e
        JOIN gameplay_session gs ON gs.session_id = e.session_id
        WHERE gs.game_id = :gid
        GROUP BY e.event_type
        ORDER BY occurrences DESC
        """,
        {"gid": gid},
    )
    if not funnel_df.empty:
        fig = px.funnel(funnel_df, x="occurrences", y="event_type")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No events logged for this game yet.")
