"""Equal-player E-group comparison with a shared percentile-rank radar scale."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


METRICS = {
    "mean_fv": "Mean FV",
    "availability": "Rated coverage\n(availability proxy)",
    "goals_per_match": "Goals / rated match",
    "assists_per_match": "Assists / rated match",
    "bonus_rate": "Bonus rate",
    "card_rate": "Low card rate",
    "consistency": "Consistency\nFV ≥ 6",
    "upside": "Upside\nFV P90",
}
GROUPS = ["Defensive E", "Other E"]


def plot_e_comparison(players: pd.DataFrame):
    """Return figure, raw means and per-metric player counts.

    Rank each metric across the combined filtered E pool, reversing cards.
    Average these ranks within each group, with equal weight per player.
    Missing metrics remain missing and their contributing counts are returned.
    These ranks describe this comparison pool, not absolute performance.
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
    ranks = pd.DataFrame(index=players.index)
    for metric in METRICS:
        # Midpoint percentile ranks keep tied/constant values centered fairly.
        rank = values[metric].rank(ascending=metric != "card_rate", method="average")
        ranks[metric] = 100 * (rank - 0.5) / values[metric].count()
    scores = ranks.groupby(players["role_group"]).mean().reindex(GROUPS)
    angles = np.linspace(0, 2 * np.pi, len(METRICS), endpoint=False)
    closed_angles = np.r_[angles, angles[0]]
    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw={"projection": "polar"})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    sizes = players.groupby("role_group").size()
    for group, color in zip(GROUPS, ["#0072B2", "#D55E00"]):
        points = scores.loc[group].to_numpy()
        closed = np.r_[points, points[0]]
        ax.plot(closed_angles, closed, color=color, linewidth=2,
                label=f"{group} (n={sizes[group]})")
        ax.fill(closed_angles, closed, color=color, alpha=0.10)
    ax.set_xticks(angles, METRICS.values(), fontsize=10)
    ax.tick_params(axis="x", pad=18)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    season = int(players["performance_season"].iloc[0])
    ax.set_title(f"E-role profiles · {season}–{str(season + 1)[-2:]}\n"
                 "Mean player percentile rank within the filtered E pool", pad=35)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), frameon=False)
    note = "Outward = better · Equal weight per player · Cards reversed\nRaw means and contributing counts accompany this chart."
    if not players["coverage_status"].eq("complete").all():
        note += "\nWARNING: season imports are incomplete."
    fig.text(0.5, 0.03, note, ha="center", fontsize=10)
    fig.subplots_adjust(top=0.79, bottom=0.18, left=0.17, right=0.80)
    return fig, raw, counts
