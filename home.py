import streamlit as st

overview = st.Page("app.py", title="Overview", icon=":material/home:")
revenue  = st.Page("pages/1_Revenue_and_Games.py", title="Revenue & Games", icon=":material/sports_esports:")
players  = st.Page("pages/2_Players_and_Engagement.py", title="Players & Engagement", icon=":material/groups:")
player_detail = st.Page("pages/Player_Detail.py", title="Player Detail", icon=":material/person:")
reviews  = st.Page("pages/3_Reviews.py", title="Reviews", icon=":material/star:")
events   = st.Page("pages/4_Live_Events.py", title="Live Events", icon=":material/bolt:")
admin    = st.Page("pages/5_Admin.py", title="Admin", icon=":material/admin_panel_settings:")

pg = st.navigation([overview, revenue, players, player_detail, reviews, events, admin])
pg.run()
