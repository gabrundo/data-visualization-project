"""Scatterplots focused on each outfield role pool's fantasy-vote range."""

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
import seaborn as sns


GROUPS = {
    "dc": "Centre backs · Dc / B",
    "fullbacks": "Fullbacks · Dd / Ds / E",
    "m": "Defensive midfielders · M",
    "c": "Central midfielders · C",
    "attack": "Attacking players · W / T / A",
    "pc": "Strikers · Pc",
}
SORT_COLUMNS = ["mean_fv", "rated_matches", "player_name", "player_id", "source_id"]
TABLE_COLUMNS = [
    "player_id", "player_name", "current_team", "role_combination",
    "eligibility_season", "performance_season", "mean_fv",
    "rated_season_fraction", "rated_matches", "fv_matches", "fv_season_fraction",
    "fv_ge6_rate", "fv_p90", "source_goals_per_rated_match",
    "assists_per_rated_match", "bonus_rate", "card_rate",
    "goal_sample", "assist_sample", "bonus_sample", "card_sample",
    "evidence_status", "coverage_status",
]


def group_table(players: pd.DataFrame, group_key: str) -> pd.DataFrame:
    """Return all group members, sorted like the top-ten chart annotations."""
    if group_key not in GROUPS:
        raise ValueError(f"Unknown group: {group_key}")
    return players.loc[players["group_key"].eq(group_key)].sort_values(
        SORT_COLUMNS, ascending=[False, False, True, True, True], na_position="last",
    ).reset_index(drop=True)


def plot_outfield_comparison(
    players: pd.DataFrame,
    *,
    performance_season: int = 2025,
    min_rated_season_fraction: float = 0.30,
) -> dict:
    """Return six figures with group-specific FV limits and common role colors.

    Input is the output of fetch_group_metrics with the same parameters.
    Labels identify up to ten highest-mean-FV plottable players per group.
    Right-margin labels and leader lines keep names from covering the points.
    """
    if not 0 <= min_rated_season_fraction <= 1:
        raise ValueError("min_rated_season_fraction must be between 0 and 1.")
    if not players.empty:
        if not players["performance_season"].eq(performance_season).all():
            raise ValueError("Select exactly one performance season matching the title.")
        if players.duplicated(["player_id", "source_id", "group_key"]).any():
            raise ValueError("Expected one row per player/source/group.")
        if not players["rated_season_fraction"].ge(min_rated_season_fraction).all():
            raise ValueError("Input contains players below the stated coverage filter.")
        if not players["group_key"].isin(GROUPS).all():
            raise ValueError("Input contains an unknown group.")

    combinations = sorted(players["role_combination"].dropna().unique())
    colors = sns.color_palette("husl", n_colors=len(combinations))
    # Spread neighboring role labels around the hue circle instead of giving
    # related combinations nearly indistinguishable adjacent shades.
    color_order = sorted(range(len(colors)), key=lambda i: (i * 0.61803398875) % 1)
    palette = dict(zip(combinations, [colors[i] for i in color_order]))
    max_coverage = players["rated_season_fraction"].max()
    x_limits = (0, max(1.0, float(max_coverage)) + 0.03) if pd.notna(max_coverage) else (0, 1.03)
    figures = {}
    for key, title in GROUPS.items():
        table = group_table(players, key)
        plotted = table.dropna(subset=["mean_fv", "rated_season_fraction"])
        valid_fv = plotted["mean_fv"].astype(float)
        if valid_fv.empty:
            y_limits = (4.0, 10.0)
        else:
            padding = max(0.05, (valid_fv.max() - valid_fv.min()) * 0.10)
            y_limits = (valid_fv.min() - padding, valid_fv.max() + padding)
        fig, ax = plt.subplots(figsize=(13, 8))
        fig.subplots_adjust(left=0.08, right=0.69, top=0.83, bottom=0.32)
        ax.set(xlim=x_limits, ylim=y_limits, xlabel="Rated-season coverage (rated matches / season games)",
               ylabel="Mean FV")
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax.grid(alpha=0.2)
        ax.set_axisbelow(True)
        ax.axvline(min_rated_season_fraction, color="0.6", linestyle=":", linewidth=1)
        for combination in sorted(plotted["role_combination"].unique()):
            subset = plotted.loc[plotted["role_combination"].eq(combination)]
            ax.scatter(subset["rated_season_fraction"], subset["mean_fv"],
                       color=palette[combination], label=combination, s=48, alpha=0.85,
                       edgecolors="white", linewidths=0.5)
        top = plotted.head(10)
        for label_y, row in zip(np.linspace(0.96, 0.05, len(top)), top.itertuples()):
            ax.annotate(row.player_name, xy=(row.rated_season_fraction, row.mean_fv),
                        xytext=(1.04, label_y), textcoords="axes fraction",
                        va="center", fontsize=10, color="0.15",
                        arrowprops={"arrowstyle": "-", "color": "0.65", "lw": 0.7},
                        annotation_clip=False)
        if plotted.empty:
            message = "No players meet the filter" if table.empty else "No players have a valid mean FV"
            ax.text(0.5, 0.5, message, ha="center", transform=ax.transAxes)
        else:
            ax.legend(title="Full current role combination", loc="upper center",
                      bbox_to_anchor=(0.5, -0.17), ncol=4, frameon=False, fontsize=9)
        fig.suptitle(f"{title}\n{performance_season}–{str(performance_season + 1)[-2:]} performance"
                     f" · rated coverage ≥ {min_rated_season_fraction:.0%}", fontsize=16, y=0.96)
        ax.set_title(f"{len(table)} eligible players · {len(plotted)} plotted · "
                     f"{len(table) - len(plotted)} missing coordinates", loc="left", fontsize=10, pad=12)
        note = "Names: ten highest mean FV · Current role eligibility · FV axis fitted to each group\n"
        note += "Rated coverage is observed contribution, not appearance probability."
        if not table.empty and not table["coverage_status"].eq("complete").all():
            note += "\nWARNING: season fixture imports are incomplete."
        fig.text(0.08, 0.025, note, fontsize=9, va="bottom")
        figures[key] = fig
    return figures
