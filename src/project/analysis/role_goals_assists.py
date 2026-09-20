"""Plot average goals + assists per rated game, preserving SQL row order.

Run: python -m project.analysis.role_goals_assists --season 2025
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import text

from project.analysis.queries import connect_database


QUERY = """
SELECT role,
       AVG(source_goals_per_rated_match + assists_per_rated_match)
           AS avg_goals_and_assists_per_game
FROM player_role_statistics
WHERE role <> 'Por'
  AND performance_season = :season
GROUP BY role
ORDER BY avg_goals_and_assists_per_game DESC NULLS LAST
"""


def plot_role_averages(frame, season):
    """Use positional bars so the input row order is preserved exactly."""
    if frame.empty:
        raise ValueError("The query returned no roles.")
    values = frame["avg_goals_and_assists_per_game"].astype(float)
    fig, ax = plt.subplots(figsize=(11, 6))
    positions = list(range(len(frame)))
    bars = ax.bar(positions, values, color="#3274A1", width=0.7)
    ax.set_xticks(positions, frame["role"].tolist())
    ax.bar_label(bars, labels=[f"{v:.3f}" if pd.notna(v) else "No data"
                               for v in values], padding=5, fontsize=10)
    ax.set_title(f"Goals + assists per game by role · {season}–{str(season + 1)[-2:]}",
                 loc="left", fontsize=16, pad=20)
    ax.set_ylabel("Average goals + assists per game")
    ax.set_xlabel("Role")
    ax.set_ylim(bottom=0)
    ax.margins(y=0.16)
    ax.set_axisbelow(True)
    ax.yaxis.grid(alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    # fig.text(0.08, 0.025,
    #          "Equal weight per player · Multi-role players count in each eligible role · Goalkeepers excluded",
    #          fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--output", type=Path, default=Path("output/role-goals-assists.png"))
    args = parser.parse_args()
    engine = connect_database()
    try:
        with engine.connect() as connection:
            frame = pd.read_sql_query(text(QUERY), connection, params={"season": args.season})
    finally:
        engine.dispose()
    fig = plot_role_averages(frame, args.season)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, facecolor="white")
    fig.savefig(args.output.with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    print(frame.to_string(index=False))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
