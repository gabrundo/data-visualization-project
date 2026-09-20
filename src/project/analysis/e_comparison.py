"""Equal-player E-group comparison with grouped bars of raw metric means.

Run the existing parameterized SQL query and display the grouped bar chart with::

    uv run python -m project.analysis.e_comparison

Save without opening a window with::

    uv run python -m project.analysis.e_comparison --output output/e-role-bars.png --no-show

In a notebook, call fetch_e_comparison(engine, performance_season=2025),
then plot_e_comparison(players); display the returned figure inline.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from project.analysis.queries import connect_database, fetch_e_comparison


METRICS = {
    "mean_fv": "Average FV",
    "upside": "FV · 90th percentile",
    "availability": "Rated coverage",
    "consistency": "FV ≥ 6",
    "goals_per_match": "Goals / match",
    "assists_per_match": "Assists / match",
    # "bonus_rate": "Bonus rate",
    "card_rate": "Card rate",
}
GROUPS = ["Defensive E", "Other E"]
GROUP_LABELS = {"Defensive E": "Defensive E", "Other E": "Offensive E"}


def plot_e_comparison(players: pd.DataFrame):
    """Return figure, raw means and per-metric player counts.

    Average each metric within each group, with equal weight per player.
    Plot means in their original units, without ranking or reversing cards.
    Missing metrics remain missing and their contributing counts are returned.
    """
    if players.empty:
        raise ValueError("No E players meet the season and coverage filter.")
    if players["performance_season"].nunique() != 1:
        raise ValueError("Select exactly one performance season.")
    if players.duplicated(["player_id", "source_id"]).any():
        raise ValueError("Expected one row per player and source.")
    if set(players["role_group"]) != set(GROUPS):
        raise ValueError("Both E groups must contain eligible players.")
    values = players[list(METRICS)].astype(float)
    grouped = values.groupby(players["role_group"])
    raw = grouped.mean().reindex(GROUPS)
    counts = grouped.count().reindex(GROUPS)
    if (counts == 0).any().any():
        raise ValueError("A group has no observations for at least one metric; inspect samples.")
    positions = np.arange(len(METRICS))
    bar_width = 0.36
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.set_facecolor("white")
    ax.set_facecolor("white")
    sizes = players.groupby("role_group").size()
    for index, (group, color) in enumerate(zip(GROUPS, ["#1f77b4", "#666666"])):
        bars = ax.bar(
            positions + (index - 0.5) * bar_width,
            raw.loc[group].to_numpy(),
            width=bar_width,
            color=color,
            label=f"{GROUP_LABELS[group]} · {sizes[group]} players",
        )
        ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=8, color="#444444")
    ax.set_xticks(positions, METRICS.values(), fontsize=9, color="#444444")
    ax.set_ylabel("Mean value", fontsize=10, color="#444444")
    ax.set_ylim(bottom=0)
    ax.margins(y=0.15)
    ax.tick_params(axis="x", length=0, pad=10)
    ax.tick_params(axis="y", labelsize=9, colors="#888888")
    ax.yaxis.grid(color="#e5e5e5", linewidth=0.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#dddddd")
    ax.set_axisbelow(True)
    season = int(players["performance_season"].iloc[0])
    fig.text(0.08, 0.95, f"historic performance for E players, season: {season}–{str(season + 1)[-2:]}",
             fontsize=13, color="#444444")
    # fig.text(0.08, 0.915, "Mean metric values",
    #          fontsize=9, color="#777777")
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.10),
               ncol=2, frameon=False, fontsize=10, labelcolor="#444444")
    
    # note = ("Metrics retain their original units; compare groups within each metric. Lower card rate is better.\n"
    #         "Match rates use rated matches. Offensive E = E without Ds/Dd roles.")
    # if not players["coverage_status"].eq("complete").all():
    #     note += "\nWARNING: season imports are incomplete."
    # fig.text(0.5, 0.025, note, ha="center", fontsize=8, color="#777777",
    #          linespacing=1.5)
    fig.subplots_adjust(top=0.85, bottom=0.25, left=0.08, right=0.98)
    return fig, raw, counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--min-coverage", type=float, default=0.30)
    parser.add_argument("--output", type=Path, help="Save the chart as PNG, SVG or PDF.")
    parser.add_argument("--no-show", action="store_true", help="Do not open a plot window.")
    args = parser.parse_args()
    if args.no_show:
        plt.switch_backend("Agg")
    # Seasons use their start year: 2025 means 2025–26. The SQL query keeps
    # one row per player/source and requires rated_matches / 38 >= 0.30.
    engine = connect_database()
    try:
        players = fetch_e_comparison(
            engine,
            performance_season=args.season,
            min_rated_season_fraction=args.min_coverage,
        )
    finally:
        engine.dispose()

    fig, raw_means, contributing_players = plot_e_comparison(players)
    print("Raw metric means:\n", raw_means)
    print("\nContributing players per metric:\n", contributing_players)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.output, dpi=180, bbox_inches="tight", facecolor="white")
        raw_means.to_csv(args.output.with_name(args.output.stem + "-means.csv"))
        contributing_players.to_csv(args.output.with_name(args.output.stem + "-counts.csv"))
    if not args.no_show:
        plt.show()
    plt.close(fig)
