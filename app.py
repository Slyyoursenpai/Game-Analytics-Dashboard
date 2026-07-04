import plotly.express as px
import streamlit as st

from db import run_query

st.set_page_config(page_title="Game Analytics | Overview", layout="wide")

# ------------------------------------------------------- Platform filter ---
platforms = run_query("SELECT DISTINCT platform FROM game WHERE platform IS NOT NULL ORDER BY platform")["platform"].tolist()
platform_opts = ["All"] + platforms
selected_platform = st.sidebar.selectbox("Platform", platform_opts, key="platform_filter")

st.title("Game Analytics Dashboard")
st.caption("Player behavior, sales, and engagement insights for indie studios and solo devs.")

# ---------------------------------------------------------------- KPIs ----
players = int(run_query("SELECT COUNT(*) AS n FROM player")["n"][0])
games_count = int(run_query("SELECT COUNT(*) AS n FROM game")["n"][0])

sale_rev = float(run_query("SELECT COALESCE(SUM(sale_price),0) AS rev FROM game_sale")["rev"][0])
purchase_rev = float(run_query("SELECT COALESCE(SUM(amount),0) AS rev FROM purchase")["rev"][0])
total_rev = sale_rev + purchase_rev

avg_rating_raw = run_query("SELECT AVG(rating) AS r FROM review")["r"][0]
avg_rating = float(avg_rating_raw) if avg_rating_raw is not None else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Players", f"{players:,}")
col2.metric("Games", f"{games_count:,}")
col3.metric("Total Revenue", f"${total_rev:,.2f}")
col4.metric("Avg Rating", f"{avg_rating:.1f} / 10" if avg_rating is not None else "—")

if selected_platform != "All":
    st.caption(f"Showing data for **{selected_platform}** only. Charts below are filtered by platform.")

st.divider()

# ----------------------------------------------------------- Charts row ---
left, right = st.columns(2)

with left:
    st.subheader("Revenue Over Time")
    st.caption("Direct sales + in-game purchases, combined by day.")
    if selected_platform == "All":
        rev_by_date = run_query("""
            SELECT day, SUM(amt) AS revenue
            FROM (
                SELECT sale_date AS day, sale_price AS amt FROM game_sale
                UNION ALL
                SELECT DATE(purchased_at) AS day, amount AS amt FROM purchase
            ) AS combined
            GROUP BY day ORDER BY day
        """)
    else:
        rev_by_date = run_query("""
            SELECT day, SUM(amt) AS revenue
            FROM (
                SELECT gs.sale_date AS day, gs.sale_price AS amt
                FROM game_sale gs
                JOIN game g ON g.game_id = gs.game_id
                WHERE g.platform = :p
                UNION ALL
                SELECT DATE(pu.purchased_at) AS day, pu.amount AS amt
                FROM purchase pu
                JOIN game g ON g.game_id = pu.game_id
                WHERE g.platform = :p
            ) AS combined
            GROUP BY day ORDER BY day
        """, {"p": selected_platform})
    if rev_by_date.empty:
        st.info("No sales recorded yet.")
    else:
        fig = px.area(rev_by_date, x="day", y="revenue")
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')

with right:
    st.subheader("Top Games by Revenue")
    st.caption("Direct sales + in-game purchases, combined per title.")
    if selected_platform == "All":
        top_games = run_query("""
            SELECT g.title, SUM(combined.amt) AS revenue
            FROM (
                SELECT game_id, sale_price AS amt FROM game_sale
                UNION ALL
                SELECT game_id, amount AS amt FROM purchase
            ) AS combined
            JOIN game g ON g.game_id = combined.game_id
            GROUP BY g.title
            ORDER BY revenue DESC LIMIT 10
        """)
    else:
        top_games = run_query("""
            SELECT g.title, SUM(combined.amt) AS revenue
            FROM (
                SELECT game_id, sale_price AS amt FROM game_sale
                UNION ALL
                SELECT game_id, amount AS amt FROM purchase
            ) AS combined
            JOIN game g ON g.game_id = combined.game_id
            WHERE g.platform = :p
            GROUP BY g.title
            ORDER BY revenue DESC LIMIT 10
        """, {"p": selected_platform})
    if top_games.empty:
        st.info("No revenue data yet.")
    else:
        fig = px.bar(top_games, x="revenue", y="title", orientation="h")
        fig.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')

st.divider()

st.subheader("Players by Region")
region_df = run_query("SELECT COALESCE(region, 'Unknown') AS region, COUNT(*) AS players FROM player GROUP BY region ORDER BY players DESC")
if region_df.empty:
    st.info("No players yet.")
else:
    fig = px.pie(region_df, names="region", values="players", hole=0.45)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width='stretch')

st.divider()
st.caption(
    "Use the sidebar to dig into **Revenue & Games**, **Players & Engagement**, "
    "**Reviews**, and **Live Events**."
)
