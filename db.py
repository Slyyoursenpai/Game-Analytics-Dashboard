"""
Shared database helpers for the Streamlit app.

Every page imports `run_query` from here instead of opening its own
connection — keeps one pooled engine for the whole app and caches
results briefly so flipping between pages doesn't re-hit Postgres
on every rerun.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


@st.cache_resource(show_spinner=False)
def get_engine():
    """Create (once) and reuse a SQLAlchemy engine for the whole app session."""
    try:
        db_url = st.secrets["DATABASE_URL"]
    except Exception:
        st.error(
            "**No database connection configured.**\n\n"
            "Add a `DATABASE_URL` to `.streamlit/secrets.toml` locally, "
            "or to your app's *Secrets* on Streamlit Community Cloud. "
            "See `secrets.toml.example` and the README for the exact format."
        )
        st.stop()
    return create_engine(db_url, pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a read-only SQL query and return the result as a DataFrame.

    Use SQLAlchemy-style named params, e.g.:
        run_query("SELECT * FROM game WHERE genre = :genre", {"genre": "RPG"})
    """
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def write_query(sql: str, params: dict | list[dict] | None = None) -> int:
    """Execute a write query (INSERT/UPDATE/DELETE).

    Accepts a single param dict or a list of param dicts for batch inserts.
    Returns the number of affected rows.
    """
    engine = get_engine()
    with engine.connect() as conn:
        if isinstance(params, list) and params:
            result = conn.execute(text(sql), params)
        else:
            result = conn.execute(text(sql), params or {})
        conn.commit()
        return result.rowcount
