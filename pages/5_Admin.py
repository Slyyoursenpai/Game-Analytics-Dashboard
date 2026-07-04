import random
import string
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

from db import run_query, write_query

st.set_page_config(page_title="Admin", layout="wide")
st.title("Admin Panel")

tab1, tab2 = st.tabs(["Add Game", "Generate Simulation Data"])

# =====================================================================
# TAB 1 — ADD GAME VIA RAWG
# =====================================================================
with tab1:
    rawg_key = st.secrets.get("RAWG_API_KEY")
    if not rawg_key:
        st.error("Add `RAWG_API_KEY` to `.streamlit/secrets.toml`. Get one free at https://rawg.io/signup")
    else:
        with st.form("add_game_form"):
            search_title = st.text_input("Game title")
            search_btn = st.form_submit_button("Search RAWG")

            if search_btn and search_title:
                with st.spinner("Searching RAWG ..."):
                    resp = requests.get(
                        "https://api.rawg.io/api/games",
                        params={"key": rawg_key, "search": search_title, "page_size": 5},
                        timeout=10,
                    )
                if resp.status_code != 200:
                    st.error(f"RAWG API error {resp.status_code}")
                    st.session_state.pop("rawg_data", None)
                else:
                    results = resp.json().get("results", [])
                    if not results:
                        st.warning("No games found. Try a different title.")
                        st.session_state.pop("rawg_data", None)
                    else:
                        st.session_state.rawg_data = results

            if "rawg_data" in st.session_state and st.session_state.rawg_data:
                results = st.session_state.rawg_data
                labels = [f"{g['name']}  ({g.get('released', '?')})" for g in results]
                idx = st.selectbox("Select the correct match", range(len(labels)), format_func=lambda i: labels[i])
                game = results[idx]

                col_a, col_b = st.columns([1, 2])
                with col_a:
                    if game.get("background_image"):
                        st.image(game["background_image"], width=220)
                with col_b:
                    st.markdown(f"**{game['name']}**")
                    st.write(f"Released: {game.get('released', '—')}")
                    st.write(f"RAWG rating: {game.get('rating', '—')} / 5")

                genres = [g["name"] for g in game.get("genres", [])]
                platforms = [p["platform"]["name"] for p in game.get("platforms", [])]

                genre = st.selectbox("Genre", genres if genres else ["Other"])
                platform = st.selectbox("Platform", platforms if platforms else ["PC"])
                base_price = st.number_input("Base price ($)", min_value=0.0, step=0.99, format="%.2f")

                save_btn = st.form_submit_button("Save Game", type="primary")
                if save_btn:
                    dup = run_query("SELECT game_id FROM game WHERE title = :t", {"t": game["name"]})
                    if not dup.empty:
                        st.error(f"**{game['name']}** already exists (game_id={dup['game_id'][0]}). Delete it first or choose a different title.")
                        st.stop()
                    img = game.get("background_image") or ""
                    write_query(
                        """INSERT INTO game (title, base_price, genre, platform, image_url)
                           VALUES (:t, :p, :g, :pl, :i)""",
                        {"t": game["name"], "p": base_price, "g": genre, "pl": platform, "i": img},
                    )
                    st.success(f"**{game['name']}** saved!")
                    st.cache_data.clear()
                    del st.session_state.rawg_data
                    st.rerun()

# --------------------------------------------------------- Bulk fetch ----
    st.divider()
    st.subheader("Backfill Missing Covers")
    st.caption("Auto-fetch cover images from RAWG for all games that don't have one yet.")

    rawg_key = st.secrets.get("RAWG_API_KEY")
    if not rawg_key:
        st.error("RAWG_API_KEY not found in secrets.")
    else:
        missing = run_query("SELECT game_id, title FROM game WHERE image_url IS NULL OR image_url = '' ORDER BY title")
        if missing.empty:
            st.success("All games already have a cover image!")
        else:
            st.write(f"{len(missing)} game(s) missing a cover:")
            for _, row in missing.iterrows():
                st.write(f"- {row['title']}")

            if st.button(f"Fetch covers for {len(missing)} games", type="primary"):
                progress = st.progress(0, text="Starting …")
                status = st.empty()
                updated = 0
                failed = 0
                total = len(missing)

                for i, (_, row) in enumerate(missing.iterrows()):
                    progress.progress((i + 1) / total, text=f"Searching {row['title']} …")
                    try:
                        resp = requests.get(
                            "https://api.rawg.io/api/games",
                            params={"key": rawg_key, "search": row["title"], "page_size": 1},
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            results = resp.json().get("results", [])
                            if results and results[0].get("background_image"):
                                img = results[0]["background_image"]
                                write_query(
                                    "UPDATE game SET image_url = :i WHERE game_id = :gid",
                                    {"i": img, "gid": row["game_id"]},
                                )
                                updated += 1
                                status.info(f"✅ {row['title']} — cover found")
                            else:
                                failed += 1
                                status.warning(f"❌ {row['title']} — no cover on RAWG")
                        else:
                            failed += 1
                            status.warning(f"❌ {row['title']} — RAWG error {resp.status_code}")
                    except Exception as e:
                        failed += 1
                        status.warning(f"❌ {row['title']} — {e}")

                progress.progress(1.0, text="Done!")
                st.success(f"Updated {updated} game(s). Failed: {failed}.")
                st.cache_data.clear()
                st.rerun()

# =====================================================================
# TAB 2 — SYNTHETIC DATA GENERATOR
# =====================================================================
with tab2:
    st.subheader("Generate Simulation Data")
    st.caption("Fill your database with realistic test data to explore the dashboard.")

    existing_players = int(run_query("SELECT COUNT(*) AS n FROM player")["n"][0])
    existing_games = int(run_query("SELECT COUNT(*) AS n FROM game")["n"][0])

    c1, c2 = st.columns(2)
    c1.metric("Existing players", existing_players)
    c2.metric("Existing games", existing_games)

    num_players = st.slider("Number of new players", 0, 500, 50, step=10)
    sessions_per_player = st.slider("Sessions per player (approx)", 0, 100, 20, step=5)

    include_sales = st.checkbox("Generate game sales", True)
    include_sessions = st.checkbox("Generate gameplay sessions", True)
    include_reviews = st.checkbox("Generate reviews", True)
    include_purchases = st.checkbox("Generate in-game purchases", True)
    include_events = st.checkbox("Generate event logs", True)

    games_for_select = run_query("SELECT game_id, title, genre, platform FROM game ORDER BY title")
    if not games_for_select.empty:
        game_opts = {f"{r['title']} ({r['genre']} — {r['platform']})": r["game_id"] for _, r in games_for_select.iterrows()}
        selected_games = st.multiselect(
            "Target games (required)",
            options=list(game_opts.keys()),
        )
        selected_game_ids = [game_opts[t] for t in selected_games]
    else:
        selected_game_ids = []
        st.info("No games yet — add one via the **Add Game** tab first.")

    generate_btn = st.button("Generate Data", type="primary")

    if generate_btn:
        if not selected_game_ids:
            st.error("No games selected and no games exist. Add a game via the **Add Game** tab first.")
            st.stop()

        total_steps = 1 if num_players > 0 else 0
        if existing_players > 0 or num_players > 0:
            if include_sales: total_steps += 1
            if include_sessions: total_steps += 1
            if include_reviews: total_steps += 1
            if include_purchases: total_steps += 1
            if include_events: total_steps += 1

        progress = st.progress(0, text="Initialising …")
        status = st.empty()
        summary = {}

        step = 0

        # ---- 1. PLAYERS ----
        if num_players > 0:
            step += 1
            progress.progress(step / total_steps, text=f"Creating {num_players} players …")
            usernames = set()
            while len(usernames) < num_players:
                usernames.add(
                    "Player_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                )
            regions = ["North America", "Europe", "Asia", "South America", "Africa", "Oceania"]
            weights = [0.35, 0.30, 0.20, 0.08, 0.05, 0.02]
            player_params = [
                {"u": u, "r": random.choices(regions, weights=weights, k=1)[0]}
                for u in usernames
            ]
            n = write_query(
                "INSERT INTO player (username, region) VALUES (:u, :r) ON CONFLICT DO NOTHING",
                player_params,
            )
            summary["player"] = n
            status.info(f"Created {n} players")

        total_players = existing_players + (num_players if num_players > 0 else 0)
        game_ids = selected_game_ids
        player_ids = run_query("SELECT player_id FROM player")["player_id"].tolist()

        if total_players == 0:
            st.warning("No players available. Increase the player count or skip.")
            st.stop()

        # Safe lower bound — at least 1 player needed for dependent tables
        if len(player_ids) == 0:
            st.error("No players in the database. Create at least one player first.")
            st.stop()

        # ---- 2. GAME SALES ----
        if include_sales:
            step += 1
            progress.progress(step / total_steps, text="Generating game sales …")
            n_sales = min(len(player_ids) * 2, 500)
            sale_params = []
            for _ in range(n_sales):
                pid = random.choice(player_ids)
                gid = random.choice(game_ids)
                price = round(random.uniform(4.99, 69.99), 2)
                days_ago = random.randint(0, 120)
                date = (datetime.today() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                sale_params.append({"p": pid, "g": gid, "pr": price, "d": date})
            n = write_query(
                """INSERT INTO game_sale (player_id, game_id, sale_price, sale_date)
                   VALUES (:p, :g, :pr, :d)""",
                sale_params,
            )
            summary["game_sale"] = n
            status.info(f"Created {n} game sales")

        # ---- 3. GAMEPLAY SESSIONS ----
        if include_sessions:
            step += 1
            progress.progress(step / total_steps, text="Generating gameplay sessions …")

            existing_sessions = int(run_query("SELECT COUNT(*) AS n FROM gameplay_session")["n"][0])
            n_sessions = len(player_ids) * sessions_per_player
            difficulties = ["Easy", "Medium", "Hard", "Expert"]
            diff_weights = [0.20, 0.40, 0.25, 0.15]

            session_params = []
            for pid in player_ids:
                n_for_player = max(1, random.randint(
                    max(1, sessions_per_player - 5),
                    sessions_per_player + 5,
                ))
                for _ in range(n_for_player):
                    gid = random.choice(game_ids)
                    diff = random.choices(difficulties, weights=diff_weights, k=1)[0]
                    duration = random.randint(5, 180)
                    death_cap = {"Easy": 5, "Medium": 15, "Hard": 35, "Expert": 60}[diff]
                    deaths = random.randint(0, death_cap)
                    level = random.randint(1, 20)
                    days_ago = random.randint(0, 90)
                    dt = datetime.today() - timedelta(days=days_ago, minutes=random.randint(0, 1440))
                    session_params.append({
                        "p": pid, "g": gid, "d": duration,
                        "diff": diff, "dc": deaths, "lvl": level,
                        "ts": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    })

            n = write_query(
                """INSERT INTO gameplay_session
                      (player_id, game_id, session_duration, difficulty, death_count, level_reached, session_start)
                   VALUES (:p, :g, :d, :diff, :dc, :lvl, :ts)""",
                session_params,
            )
            summary["gameplay_session"] = n
            status.info(f"Created {n} gameplay sessions")

        # Retrieve session IDs if event logs are needed
        session_ids = None
        if include_events:
            session_ids = run_query("SELECT session_id FROM gameplay_session")["session_id"].tolist()

        # ---- 4. REVIEWS ----
        if include_reviews:
            step += 1
            progress.progress(step / total_steps, text="Generating reviews …")
            n_reviews = min(len(player_ids) * 2, 300)
            review_texts = [
                "Great game, really enjoying it!",
                "Needs some improvements but overall fun.",
                "Amazing graphics and gameplay.",
                "Too short, expected more content.",
                "Perfect game for casual players.",
                "The storyline is incredible.",
                "Good value for the price.",
                "Multiplayer mode is fantastic.",
                "Would recommend to friends.",
                "Decent game but could be better.",
                "Best game I have played this year.",
                "Controls are a bit clunky.",
                "Love the art style!",
                "Very addictive gameplay loop.",
                "A masterpiece of game design.",
            ]
            review_params = []
            used_reviews = set()
            for _ in range(n_reviews):
                pid = random.choice(player_ids)
                gid = random.choice(game_ids)
                key = (pid, gid)
                if key in used_reviews:
                    continue
                used_reviews.add(key)
                rating = random.choices(
                    range(1, 11),
                    weights=[1, 1, 2, 3, 5, 8, 12, 15, 18, 25],
                    k=1,
                )[0]
                text = random.choice(review_texts)
                days_ago = random.randint(0, 90)
                dt = datetime.today() - timedelta(days=days_ago, hours=random.randint(0, 24))
                review_params.append({
                    "p": pid, "g": gid, "r": rating, "t": text,
                    "ts": dt.strftime("%Y-%m-%d %H:%M:%S"),
                })
            if review_params:
                n = write_query(
                    """INSERT INTO review (player_id, game_id, rating, review_text, reviewed_at)
                       VALUES (:p, :g, :r, :t, :ts)""",
                    review_params,
                )
                summary["review"] = n
                status.info(f"Created {n} reviews")
            else:
                summary["review"] = 0

        # ---- 5. PURCHASES ----
        if include_purchases:
            step += 1
            progress.progress(step / total_steps, text="Generating purchases …")
            n_purchases = min(len(player_ids) * 3, 500)
            items = [
                ("Health Potion", 0.99), ("XP Boost", 2.99), ("Skin Pack", 4.99),
                ("DLC Expansion", 14.99), ("Battle Pass", 9.99), ("Loot Box", 1.99),
                ("Season Pass", 29.99), ("Cosmetic Pack", 3.99), ("Weapon Skin", 1.49),
                ("Emote Pack", 2.49),
            ]
            purchase_params = []
            for _ in range(n_purchases):
                pid = random.choice(player_ids)
                gid = random.choice(game_ids)
                item, amt = random.choice(items)
                days_ago = random.randint(0, 90)
                dt = datetime.today() - timedelta(days=days_ago, hours=random.randint(0, 24))
                purchase_params.append({
                    "p": pid, "g": gid, "item": item, "amt": amt,
                    "ts": dt.strftime("%Y-%m-%d %H:%M:%S"),
                })
            n = write_query(
                """INSERT INTO purchase (player_id, game_id, item_name, amount, purchased_at)
                   VALUES (:p, :g, :item, :amt, :ts)""",
                purchase_params,
            )
            summary["purchase"] = n
            status.info(f"Created {n} purchases")

        # ---- 6. EVENT LOGS ----
        if include_events and session_ids:
            step += 1
            progress.progress(step / total_steps, text="Generating event logs …")
            event_types = [
                "level_start", "enemy_killed", "item_collected", "level_complete",
                "player_died", "achievement_unlocked", "checkpoint_reached", "area_entered",
            ]
            event_params = []
            for sid in random.sample(session_ids, min(len(session_ids), 200)):
                n_events = random.randint(3, 15)
                base_time = datetime.today() - timedelta(days=random.randint(0, 30))
                for offset in range(n_events):
                    event_params.append({
                        "sid": sid,
                        "et": random.choice(event_types),
                        "ts": (base_time + timedelta(minutes=offset * random.randint(1, 10))).strftime("%Y-%m-%d %H:%M:%S"),
                    })
            if event_params:
                n = write_query(
                    """INSERT INTO event_log (session_id, event_type, event_timestamp)
                       VALUES (:sid, :et, :ts)""",
                    event_params,
                )
                summary["event_log"] = n
                status.info(f"Created {n} event logs")

        # ---- DONE — show summary ----
        progress.progress(1.0, text="Done!")
        status.success("Data generation complete!")
        st.cache_data.clear()

        st.divider()
        st.subheader("Insertion Summary")
        summary_data = []
        for table in ["player", "game_sale", "gameplay_session", "review", "purchase", "event_log"]:
            count = summary.get(table, 0)
            if count > 0 or table == "player":
                total = int(run_query(f"SELECT COUNT(*) AS n FROM {table}")["n"][0])
                summary_data.append({"Table": table, "Inserted": count, "Total now": total})
        st.dataframe(pd.DataFrame(summary_data), hide_index=True, width="stretch")

        if summary.get("gameplay_session", 0) > 0:
            stats = run_query("""
                SELECT COUNT(*) AS sessions,
                       AVG(session_duration)::numeric(10,1) AS avg_duration,
                       AVG(death_count)::numeric(10,1) AS avg_deaths,
                       AVG(level_reached)::numeric(10,1) AS avg_level
                FROM gameplay_session
            """)
            st.subheader("Session Snapshot")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total sessions", int(stats["sessions"][0]))
            c2.metric("Avg duration", f'{float(stats["avg_duration"][0]):.1f} min')
            c3.metric("Avg deaths", f'{float(stats["avg_deaths"][0]):.1f}')
            c4.metric("Avg level", f'{float(stats["avg_level"][0]):.1f}')
