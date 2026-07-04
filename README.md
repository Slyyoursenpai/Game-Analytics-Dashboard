# Game Analytics Dashboard

A Streamlit dashboard for indie game studios / solo devs to track players,
sales, engagement, and reviews from a single Postgres database — built from
the **User Behavior Analytics Platform for Video Games** course project.

**Stack:** Python · Streamlit · SQLAlchemy · Postgres (Neon) · Plotly

## Folder structure

```
game-analytics-dashboard/
├── home.py                          # Overview page (entry point)
├── db.py                           # DB engine + cached query helper
├── schema.sql                      # CREATE TABLE statements (run once on Neon)
├── pages/
│   ├── 1_Revenue_and_Games.py
│   ├── 2_Players_and_Engagement.py
│   ├── 3_Reviews.py
│   └── 4_Live_Events.py
|   ├── Player_Details.py
|   └── 5_Admin.py
├── .streamlit/
│   ├── config.toml                 # theme
│   └── secrets.toml.example        # copy to secrets.toml, fill in your URL
├── requirements.txt
└── .gitignore
```

## 1. Create a free Postgres database (Neon)

1. Go to [neon.tech](https://neon.tech) and sign up (free tier).
2. Create a project — Neon gives you a database immediately, no extra setup.
3. Open **Connection Details** and copy the connection string. It looks like:
   ```
   postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require
   ```
4. In the Neon console, open the **SQL Editor**, paste the contents of
   `schema.sql` from this project, and run it. This creates all 7 tables
   (`game`, `player`, `game_sale`, `gameplay_session`, `review`, `purchase`,
   `event_log`) with the same structure as your original ERD.

## 2. Run it locally

```bash
cd game-analytics-dashboard
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and paste your real Neon connection string

streamlit run home.py
```

It'll open at `http://localhost:8501`. Every page will show "No data yet"
placeholders until you start inserting rows — that's expected, the app
doesn't ship with any fake data.

## 3. Adding your own data (quick reference)

Insert through the Neon SQL Editor, `psql`, or pgAdmin pointed at your Neon
connection string. Order matters because of foreign keys — `game` and
`player` first, then the rest:

```sql
INSERT INTO game (title, base_price, genre, platform, image_url)
VALUES ('Starbound Drift', 19.99, 'Roguelike', 'PC', "image_url");

INSERT INTO player (username, region)
VALUES ('moonrunner_22', 'Asia');

INSERT INTO game_sale (player_id, game_id, sale_price, sale_date)
VALUES (1, 1, 19.99, '2026-06-01');

INSERT INTO gameplay_session (player_id, game_id, session_duration, difficulty, death_count, level_reached, session_start)
VALUES (1, 1, 42, 'Normal', 3, 5, now());

INSERT INTO purchase (player_id, game_id, item_name, amount, purchased_at)
VALUES (1, 1, 'Cosmetic Skin Pack', 4.99, now());

INSERT INTO review (player_id, game_id, rating, review_text, reviewed_at)
VALUES (1, 1, 8, 'Tight controls, great pacing.', now());

INSERT INTO event_log (session_id, event_type, event_timestamp)
VALUES (1, 'level_complete', now());
```

**Tip:** `session_start`, `purchased_at`, and `reviewed_at` all default to
`now()`, so you can drop them from the INSERT entirely and just backdate
manually (e.g. `'2026-06-01 14:30:00'`) when you want historical-looking data
for the time-series charts.

## Notes on the schema

- Every table that needs a date now has one: `game_sale.sale_date`,
  `gameplay_session.session_start`, `purchase.purchased_at`,
  `review.reviewed_at`, and `event_log.event_timestamp` — all
  `TIMESTAMP/DATE DEFAULT now()`, so existing INSERT statements that omit
  them still work.
- This unlocks real-time series: **Revenue Over Time** (Overview) now
  combines sales + purchases by day, **Sessions Over Time** and
  **Player Retention** (Players & Engagement) use `session_start` directly,
  and **Reviews Over Time** (Reviews) tracks rating trend by day.
- The retention chart mirrors the original mockup's "Day 1/7/30" bars: it's
  the % of players with at least one session N+ days after their first
  recorded session. With only a handful of players it'll look noisy/sparse —
  that's normal until there's more data.
- AI-assisted churn prediction and sentiment analysis were called out as
  *future growth* in your original deck, not MVP — intentionally left out
  here so the app stays simple and every chart is backed by a real column.
- Admin page allows adding of games and populating tables with randomized data as well as a cover image using the RAWG API so manual SQL queries to populate tables can be avoided

## Possible next steps

- A churn-risk score (e.g. days since last session per player) now that
  `session_start` exists.
- Simple keyword/sentiment tagging on `review.review_text`.
- Cohort-by-acquisition-channel retention, if you ever add a `source` column.
