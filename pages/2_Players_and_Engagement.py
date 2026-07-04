import pandas as pd
import plotly.express as px
import streamlit as st

from db import run_query

st.set_page_config(page_title="Players & Engagement", layout="wide")

# ------------------------------------------------------- Platform filter ---
platforms = run_query("SELECT DISTINCT platform FROM game WHERE platform IS NOT NULL ORDER BY platform")["platform"].tolist()
platform_opts = ["All"] + platforms
selected_platform = st.sidebar.selectbox("Platform", platform_opts, key="platform_filter")

st.title("Players & Engagement")

# ----------------------------------------------------------- Directory ----
st.subheader("Player Directory")
players_df = run_query(
    "SELECT player_id, username, COALESCE(region,'Unknown') AS region FROM player ORDER BY username"
)

if players_df.empty:
    st.info("No players yet.")
else:
    regions = ["All"] + sorted(players_df["region"].unique().tolist())
    region_filter = st.selectbox("Region", regions)
    filtered = players_df if region_filter == "All" else players_df[players_df["region"] == region_filter]
    st.dataframe(filtered, width='stretch', hide_index=True)

st.divider()

# ------------------------------------------------------ Sessions over time -
st.subheader("Sessions Over Time")
st.caption("Daily session count from `gameplay_session.session_start`.")

if selected_platform == "All":
    sessions_over_time = run_query("""
        SELECT DATE(session_start) AS day, COUNT(*) AS sessions
        FROM gameplay_session
        GROUP BY day ORDER BY day
    """)
else:
    sessions_over_time = run_query("""
        SELECT DATE(gs.session_start) AS day, COUNT(*) AS sessions
        FROM gameplay_session gs
        JOIN game g ON g.game_id = gs.game_id
        WHERE g.platform = :p
        GROUP BY day ORDER BY day
    """, {"p": selected_platform})
if sessions_over_time.empty:
    st.info("No gameplay sessions logged yet.")
else:
    fig = px.line(sessions_over_time, x="day", y="sessions", markers=True)
    st.plotly_chart(fig, width='stretch')

st.divider()

# ----------------------------------------------------------- Retention ----
st.subheader("Player Retention")
st.caption("% of players still showing activity at least N days after their first recorded session.")

if selected_platform == "All":
    retention_raw = run_query("SELECT player_id, DATE(session_start) AS day FROM gameplay_session")
else:
    retention_raw = run_query("""
        SELECT gs.player_id, DATE(gs.session_start) AS day
        FROM gameplay_session gs
        JOIN game g ON g.game_id = gs.game_id
        WHERE g.platform = :p
    """, {"p": selected_platform})
if retention_raw.empty:
    st.info("No gameplay sessions logged yet.")
else:
    retention_raw["day"] = pd.to_datetime(retention_raw["day"])
    cohort_day = retention_raw.groupby("player_id")["day"].min().rename("cohort_day")
    merged = retention_raw.merge(cohort_day, on="player_id")
    merged["offset"] = (merged["day"] - merged["cohort_day"]).dt.days
    total_players = retention_raw["player_id"].nunique()
    milestones = [0, 1, 3, 7, 14, 30]
    rows = []
    for m in milestones:
        retained = merged.loc[merged["offset"] >= m, "player_id"].nunique()
        rows.append({"milestone": f"Day {m}", "retention_pct": 100 * retained / total_players})
    retention_df = pd.DataFrame(rows)
    fig = px.bar(retention_df, x="milestone", y="retention_pct", labels={"retention_pct": "% retained"})
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(fig, width='stretch')

st.divider()

# ----------------------------------------------------- Session metrics ----
c1, c2 = st.columns(2)

with c1:
    st.subheader("Avg. Session Duration by Game")
    if selected_platform == "All":
        df = run_query("""
            SELECT g.title, AVG(gs.session_duration) AS avg_duration
            FROM gameplay_session gs
            JOIN game g ON g.game_id = gs.game_id
            WHERE gs.session_duration IS NOT NULL
            GROUP BY g.title ORDER BY avg_duration DESC
        """)
    else:
        df = run_query("""
            SELECT g.title, AVG(gs.session_duration) AS avg_duration
            FROM gameplay_session gs
            JOIN game g ON g.game_id = gs.game_id
            WHERE gs.session_duration IS NOT NULL AND g.platform = :p
            GROUP BY g.title ORDER BY avg_duration DESC
        """, {"p": selected_platform})
    if df.empty:
        st.info("No gameplay sessions logged yet.")
    else:
        fig = px.bar(df, x="title", y="avg_duration", labels={"avg_duration": "Avg duration (min)"})
        st.plotly_chart(fig, width='stretch')

with c2:
    st.subheader("Avg Playtime by Genre")
    if selected_platform == "All":
        df = run_query("""
            SELECT g.genre, AVG(gs.session_duration) AS avg_duration
            FROM gameplay_session gs
            JOIN game g ON g.game_id = gs.game_id
            WHERE gs.session_duration IS NOT NULL AND g.genre IS NOT NULL
            GROUP BY g.genre ORDER BY avg_duration DESC
        """)
    else:
        df = run_query("""
            SELECT g.genre, AVG(gs.session_duration) AS avg_duration
            FROM gameplay_session gs
            JOIN game g ON g.game_id = gs.game_id
            WHERE gs.session_duration IS NOT NULL AND g.genre IS NOT NULL AND g.platform = :p
            GROUP BY g.genre ORDER BY avg_duration DESC
        """, {"p": selected_platform})
    if df.empty:
        st.info("No sessions logged yet.")
    else:
        fig = px.bar(df, x="genre", y="avg_duration", labels={"avg_duration": "Avg duration (min)"})
        st.plotly_chart(fig, width='stretch')

st.divider()

# --------------------------------------------------------- Top spenders ---
st.subheader("Top Players by Spend")
if selected_platform == "All":
    df = run_query("""
        SELECT p.username, SUM(combined.amt) AS total_spend
        FROM (
            SELECT player_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT player_id, amount AS amt FROM purchase
        ) AS combined
        JOIN player p ON p.player_id = combined.player_id
        GROUP BY p.username ORDER BY total_spend DESC LIMIT 10
    """)
else:
    df = run_query("""
        SELECT p.username, SUM(combined.amt) AS total_spend
        FROM (
            SELECT gs.player_id, gs.sale_price AS amt
            FROM game_sale gs JOIN game g ON g.game_id = gs.game_id
            WHERE g.platform = :p
            UNION ALL
            SELECT pu.player_id, pu.amount AS amt
            FROM purchase pu JOIN game g ON g.game_id = pu.game_id
            WHERE g.platform = :p
        ) AS combined
        JOIN player p ON p.player_id = combined.player_id
        GROUP BY p.username ORDER BY total_spend DESC LIMIT 10
    """, {"p": selected_platform})
if df.empty:
    st.info("No purchases or sales recorded yet.")
else:
    st.dataframe(df, width='stretch', hide_index=True)

st.divider()

# --------------------------------------------------------- Top playtime --
st.subheader("Top Players by Playtime")
if selected_platform == "All":
    df = run_query("""
        SELECT p.username, SUM(gs.session_duration) AS total_minutes
        FROM gameplay_session gs
        JOIN player p ON p.player_id = gs.player_id
        WHERE gs.session_duration IS NOT NULL
        GROUP BY p.username ORDER BY total_minutes DESC LIMIT 10
    """)
else:
    df = run_query("""
        SELECT p.username, SUM(gs.session_duration) AS total_minutes
        FROM gameplay_session gs
        JOIN game g ON g.game_id = gs.game_id
        JOIN player p ON p.player_id = gs.player_id
        WHERE gs.session_duration IS NOT NULL AND g.platform = :p
        GROUP BY p.username ORDER BY total_minutes DESC LIMIT 10
    """, {"p": selected_platform})
if df.empty:
    st.info("No gameplay sessions logged yet.")
else:
    st.dataframe(df, width='stretch', hide_index=True)

st.divider()

# -------------------------------------------------------- LTV scatter --------
st.subheader("Lifetime Value: Spend vs Playtime")
st.caption("Each dot is a player — do big spenders also play the most?")

if selected_platform == "All":
    ltv_df = run_query("""
        SELECT p.username,
               COALESCE(SUM(spend.amt), 0) AS total_spend,
               COALESCE(SUM(gs.session_duration), 0) AS total_minutes
        FROM player p
        LEFT JOIN (
            SELECT player_id, sale_price AS amt FROM game_sale
            UNION ALL
            SELECT player_id, amount AS amt FROM purchase
        ) AS spend ON spend.player_id = p.player_id
        LEFT JOIN gameplay_session gs ON gs.player_id = p.player_id
        GROUP BY p.username
    """)
else:
    ltv_df = run_query("""
        SELECT p.username,
               COALESCE(SUM(spend.amt), 0) AS total_spend,
               COALESCE(SUM(gs.session_duration), 0) AS total_minutes
        FROM player p
        LEFT JOIN (
            SELECT gs2.player_id, gs2.sale_price AS amt
            FROM game_sale gs2 JOIN game g1 ON g1.game_id = gs2.game_id
            WHERE g1.platform = :p
            UNION ALL
            SELECT pu.player_id, pu.amount AS amt
            FROM purchase pu JOIN game g2 ON g2.game_id = pu.game_id
            WHERE g2.platform = :p
        ) AS spend ON spend.player_id = p.player_id
        LEFT JOIN (
            SELECT gs3.player_id, gs3.session_duration
            FROM gameplay_session gs3 JOIN game g3 ON g3.game_id = gs3.game_id
            WHERE g3.platform = :p
        ) AS gs ON gs.player_id = p.player_id
        GROUP BY p.username
    """, {"p": selected_platform})
if ltv_df.empty or (ltv_df["total_spend"].sum() == 0 and ltv_df["total_minutes"].sum() == 0):
    st.info("Add sales, purchases, and sessions to see the LTV scatter plot.")
else:
    fig = px.scatter(
        ltv_df,
        x="total_minutes",
        y="total_spend",
        text="username",
        labels={"total_minutes": "Total playtime (min)", "total_spend": "Total spend ($)"},
    )
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, width='stretch')

st.divider()

# -------------------------------------------------------- Churn risk ---------
st.subheader("Churn Risk")
st.caption("Days since each player's last session — high numbers = at risk.")

if selected_platform == "All":
    churn_df = run_query("""
        SELECT p.username,
               MAX(DATE(gs.session_start)) AS last_session_date,
               CURRENT_DATE - MAX(DATE(gs.session_start)) AS days_since_last_session
        FROM player p
        LEFT JOIN gameplay_session gs ON gs.player_id = p.player_id
        GROUP BY p.username
        ORDER BY days_since_last_session DESC NULLS LAST
    """)
else:
    churn_df = run_query("""
        SELECT p.username,
               MAX(DATE(gs.session_start)) AS last_session_date,
               CURRENT_DATE - MAX(DATE(gs.session_start)) AS days_since_last_session
        FROM player p
        LEFT JOIN (
            SELECT gs2.player_id, gs2.session_start
            FROM gameplay_session gs2 JOIN game g ON g.game_id = gs2.game_id
            WHERE g.platform = :p
        ) AS gs ON gs.player_id = p.player_id
        GROUP BY p.username
        ORDER BY days_since_last_session DESC NULLS LAST
    """, {"p": selected_platform})
if churn_df.empty:
    st.info("No sessions logged yet.")
else:
    churn_df["days_since_last_session"] = churn_df["days_since_last_session"].fillna(-1).astype(int)
    churn_df = churn_df.replace(-1, "No sessions")
    st.dataframe(churn_df, width='stretch', hide_index=True)
