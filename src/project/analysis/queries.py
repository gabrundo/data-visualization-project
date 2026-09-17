"""Read analysis views into pandas DataFrames for notebooks and charts.

Create one engine with connect_database() and reuse it across queries.
Seasons are start years: 2025 means 2025–26. Eligibility and team membership
always come from the current roster configured by the SQL views.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from project.etl.import_players import ROOT, ROLES, database_engine


def connect_database(env_file: str | Path | None = None) -> Engine:
    """Build a lazy SQLAlchemy engine using the project's connection settings.

    Defaults to the repository's .env, independently of the notebook's working
    directory. Environment variables override that file. The first query opens
    the actual connection; call engine.dispose() when finished with the engine.
    """
    return database_engine(Path(env_file) if env_file is not None else ROOT / ".env")


def fetch_role_metrics(
    engine: Engine,
    role: str,
    performance_season: int,
    *,
    min_rated_season_fraction: float = 0.0,
) -> pd.DataFrame:
    """Fetch one season for one exact Mantra role, ordered by median FV.

    The threshold is exclusive, matching the original query: 0.4 means rated
    matches / 38 > 0.4, not a fraction of fixtures imported so far. The default
    excludes players with no rated matches. All view columns are returned,
    including player IDs, coverage, sample sizes, and candidate_score.
    Missing values stay missing; they are not replaced with zero.
    """
    if role not in ROLES:
        raise ValueError(f"Unknown Mantra role {role!r}. Choose from {sorted(ROLES)}.")
    if not 0 <= min_rated_season_fraction <= 1:
        raise ValueError("min_rated_season_fraction must be between 0 and 1.")

    query = text("""
        SELECT *
        FROM player_role_statistics
        WHERE role = :role
          AND performance_season = :season
          AND rated_season_fraction > :min_fraction
        ORDER BY median_fv DESC NULLS LAST, fv_matches DESC, player_id, source_id
    """)
    with engine.connect() as connection:
        return pd.read_sql_query(query, connection, params={
            "role": role,
            "season": performance_season,
            "min_fraction": min_rated_season_fraction,
        })


E_COMPARISON_QUERY = """
    SELECT player_id, source_id, player_name, current_team, roles,
           eligibility_season, performance_season,
           CASE WHEN roles && ARRAY['Ds', 'Dd']::text[]
                THEN 'Defensive E' ELSE 'Other E' END AS role_group,
           mean_fv,
           rated_season_fraction AS availability,
           source_goals_per_rated_match AS goals_per_match,
           assists_per_rated_match AS assists_per_match,
           bonus_rate, card_rate,
           fv_ge6_rate AS consistency,
           fv_p90 AS upside,
           rated_matches, fv_matches, fv_season_fraction,
           goal_sample, assist_sample, bonus_sample, card_sample,
           coverage_status, imported_fixtures, complete_matchdays, evidence_status
    FROM player_season_metrics
    WHERE performance_season = :season
      AND rated_season_fraction >= :min_fraction
      AND 'E' = ANY(roles)
    ORDER BY role_group, mean_fv DESC NULLS LAST, player_id, source_id
"""


def fetch_e_comparison(
    engine: Engine,
    performance_season: int = 2025,
    *,
    min_rated_season_fraction: float = 0.30,
) -> pd.DataFrame:
    """Return disjoint E groups after an inclusive rated-match coverage filter.

    Ds/Dd membership takes precedence over any additional roles. Availability
    is only rated matches / season games; consistency is P(FV >= 6).
    Event rates exclude observations with unknown event values.
    """
    if not 0 <= min_rated_season_fraction <= 1:
        raise ValueError("min_rated_season_fraction must be between 0 and 1.")
    with engine.connect() as connection:
        return pd.read_sql_query(text(E_COMPARISON_QUERY), connection, params={
            "season": performance_season,
            "min_fraction": min_rated_season_fraction,
        })


GROUP_METRICS_QUERY = """
    SELECT m.*, groups.group_key,
           array_to_string(ARRAY(SELECT role FROM unnest(m.roles) AS role
                                 ORDER BY role), '/') AS role_combination
    FROM player_season_metrics m
    JOIN (VALUES
        ('dc', ARRAY['Dc', 'B']::text[]),
        ('fullbacks', ARRAY['Dd', 'Ds', 'E']::text[]),
        ('m', ARRAY['M']::text[]),
        ('c', ARRAY['C']::text[]),
        ('attack', ARRAY['W', 'T', 'A']::text[]),
        ('pc', ARRAY['Pc']::text[])
    ) AS groups(group_key, eligible_roles)
      ON m.roles && groups.eligible_roles
    WHERE m.performance_season = :season
      AND m.rated_season_fraction >= :min_fraction
    ORDER BY groups.group_key, m.mean_fv DESC NULLS LAST,
             m.rated_matches DESC, m.player_name, m.player_id, m.source_id
"""


def fetch_group_metrics(
    engine: Engine,
    performance_season: int = 2025,
    *,
    min_rated_season_fraction: float = 0.30,
) -> pd.DataFrame:
    """Fetch six overlapping outfield pools, once per player/source/group.

    Coverage is rated matches / season games with an inclusive threshold.
    Full role combinations are alphabetically ordered for stable display.
    All core metrics and evidence fields are retained; missing stays missing.
    """
    if not 0 <= min_rated_season_fraction <= 1:
        raise ValueError("min_rated_season_fraction must be between 0 and 1.")
    with engine.connect() as connection:
        return pd.read_sql_query(text(GROUP_METRICS_QUERY), connection, params={
            "season": performance_season,
            "min_fraction": min_rated_season_fraction,
        })


def fetch_player_history(engine: Engine, player_id: int) -> pd.DataFrame:
    """Fetch all configured seasons for an internal player_id (not Excel ID).

    Uses player_season_metrics to avoid duplicating multi-role players. Empty
    seasons are retained for coverage checks and gaps in historical charts.
    Includes season_weighted_score; candidate_score requires a specific role
    and is available through fetch_role_metrics instead.
    """
    query = text("""
        SELECT *
        FROM player_season_metrics
        WHERE player_id = :player_id
        ORDER BY performance_season, source_id
    """)
    with engine.connect() as connection:
        return pd.read_sql_query(query, connection, params={"player_id": player_id})


if __name__ == "__main__":
    engine = connect_database()
    try:
        df = fetch_role_metrics(
            engine, role="M", performance_season=2025,
            min_rated_season_fraction=0.4,
        )
        print(df[["player_name", "current_team", "rated_matches", "median_fv"]].head(20))
    finally:
        engine.dispose()
