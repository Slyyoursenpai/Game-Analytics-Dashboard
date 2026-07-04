-- Game Analytics Platform — schema for Neon (or any Postgres)
-- Mirrors the ERD from the mid-term report: game, player, game_sale,
-- gameplay_session, review, purchase, event_log.
-- Run this once against a fresh database before connecting the app.

BEGIN;

CREATE TABLE IF NOT EXISTS game (
    game_id     SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    base_price  NUMERIC(10,2) NOT NULL,
    genre       VARCHAR(100),
    platform    VARCHAR(100),
    image_url   VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS player (
    player_id   SERIAL PRIMARY KEY,
    username    VARCHAR(100) NOT NULL UNIQUE,
    region      VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS game_sale (
    sale_id     SERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES player(player_id),
    game_id     INTEGER NOT NULL REFERENCES game(game_id),
    sale_price  NUMERIC(10,2) NOT NULL,
    sale_date   DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS gameplay_session (
    session_id       SERIAL PRIMARY KEY,
    player_id        INTEGER NOT NULL REFERENCES player(player_id),
    game_id          INTEGER NOT NULL REFERENCES game(game_id),
    session_duration INTEGER,
    difficulty       VARCHAR(50),
    death_count      INTEGER DEFAULT 0,
    level_reached    INTEGER DEFAULT 1,
    session_start    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review (
    review_id   SERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES player(player_id),
    game_id     INTEGER NOT NULL REFERENCES game(game_id),
    rating      SMALLINT CHECK (rating >= 1 AND rating <= 10),
    review_text TEXT,
    reviewed_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS purchase (
    purchase_id  SERIAL PRIMARY KEY,
    player_id    INTEGER NOT NULL REFERENCES player(player_id),
    game_id      INTEGER NOT NULL REFERENCES game(game_id),
    item_name    VARCHAR(255) NOT NULL,
    amount       NUMERIC(10,2) NOT NULL,
    purchased_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_log (
    event_id        SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES gameplay_session(session_id),
    event_type      VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMP NOT NULL DEFAULT now()
);

COMMIT;

-- Helpful indexes for the dashboard's joins/group-bys.
CREATE INDEX IF NOT EXISTS idx_game_sale_game_id ON game_sale(game_id);
CREATE INDEX IF NOT EXISTS idx_game_sale_player_id ON game_sale(player_id);
CREATE INDEX IF NOT EXISTS idx_purchase_game_id ON purchase(game_id);
CREATE INDEX IF NOT EXISTS idx_purchase_player_id ON purchase(player_id);
CREATE INDEX IF NOT EXISTS idx_review_game_id ON review(game_id);
CREATE INDEX IF NOT EXISTS idx_session_player_id ON gameplay_session(player_id);
CREATE INDEX IF NOT EXISTS idx_session_game_id ON gameplay_session(game_id);
CREATE INDEX IF NOT EXISTS idx_event_log_session_id ON event_log(session_id);
CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_session_start ON gameplay_session(session_start);
CREATE INDEX IF NOT EXISTS idx_purchase_purchased_at ON purchase(purchased_at);
CREATE INDEX IF NOT EXISTS idx_review_reviewed_at ON review(reviewed_at);
